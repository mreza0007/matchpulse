import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import db_service
import scheduler_service as scheduler
from live_notification_policy import classify_key_moment
from services.generic_football_adapter import normalize_match_event


def match(competition="premier_league"):
    return {"id": "mp_match_shared", "competition_key": competition, "season_key": "2026-2027",
        "status": "live", "is_live": True, "supports_events": True,
        "kickoff_utc": "2026-10-03T12:00:00Z", "home_team_id": "mp_team_home", "away_team_id": "mp_team_away",
        "home_en": "Home", "away_en": "Away", "home_fa": "خانه", "away_fa": "مهمان", "home_score": 1, "away_score": 0}


def event(kind="goal", **extra):
    return {"id": "mp_event_shared", "type": kind, "minute": 23, "team_side": "home", "player_name": "Player", **extra}


class KeyMomentPolicyTests(unittest.TestCase):
    def test_routine_events_and_stray_scoring_booleans_never_push(self):
        for kind in ("yellow_card", "substitution", "corner", "offside", "foul", "other"):
            self.assertIsNone(classify_key_moment(event(kind, is_scoring_event=True)))
        for code in (1, 3, 5, 6, 9):
            self.assertIsNone(classify_key_moment({"eventType": code, "is_scoring_event": True}))

    def test_three_scoring_types_and_two_dismissal_types(self):
        for kind in ("goal", "own_goal", "penalty_goal"):
            self.assertEqual(classify_key_moment(event(kind)), "goal")
        for kind in ("red_card", "second_yellow_red"):
            self.assertEqual(classify_key_moment(event(kind)), "red_card")

    def test_penalty_awarded_missed_and_saved_require_explicit_semantics(self):
        for kind in ("missed_penalty", "penalty_missed", "penalty_saved"):
            self.assertEqual(classify_key_moment(event(kind)), "penalty_missed")
        for text in ("Penalty awarded", "پنالتی اعلام شد"):
            self.assertEqual(classify_key_moment(event("other", description=text)), "penalty_awarded")
        for text in ("Penalty missed", "Penalty saved", "پنالتی مهار شد"):
            self.assertEqual(classify_key_moment(event("other", description=text)), "penalty_missed")
        for text in ("Penalty", "Penalty possible", "Penalty awarded?"):
            self.assertIsNone(classify_key_moment(event("penalty_event", description=text)))

    def test_known_and_unknown_var_review_subjects(self):
        for text, kind in (("VAR goal review", "goal"), ("VAR review for penalty", "penalty"),
            ("Red card under VAR review", "red_card"), ("بررسی گل با VAR", "goal")):
            self.assertEqual(classify_key_moment(event("var", description=text)), "var_review_" + kind)
        self.assertEqual(classify_key_moment(event("var", description="goal")), "var_review_goal")
        for text in ("VAR", "VAR review", "Checking decision", "unknown"):
            self.assertIsNone(classify_key_moment(event("var", description=text)))

    def test_definitive_decisions_in_both_languages(self):
        for kind, texts in {
            "goal_disallowed": ("Goal disallowed after VAR review", "گل مردود شده"),
            "goal_confirmed": ("VAR: Goal confirmed", "گل تأیید شد"),
            "penalty_awarded": ("Penalty awarded after VAR review", "پنالتی اعلام شد"),
            "penalty_overturned": ("Penalty overturned", "پنالتی لغو شد"),
            "red_card_upheld": ("Red card upheld", "کارت قرمز تأیید شد"),
            "red_card_cancelled": ("Red card canceled", "کارت قرمز لغو شد"),
        }.items():
            for text in texts:
                self.assertEqual(classify_key_moment(event("var", description=text)), kind, text)

    def test_ambiguous_and_conflicting_var_decisions_stay_silent(self):
        for text in ("Possible goal disallowed", "Goal confirmed?", "Penalty decision pending", "Red card review outcome unknown"):
            self.assertIsNone(classify_key_moment(event("var", description=text)))
        self.assertIsNone(classify_key_moment(event("var", description="Goal confirmed", raw_type_label="Goal disallowed")))

    def test_definitive_outcome_supersedes_retained_review_label_for_same_subject(self):
        self.assertEqual(classify_key_moment(event("var", description="Goal disallowed",
            raw_type_label="VAR goal review")), "goal_disallowed")
        self.assertEqual(classify_key_moment(event("var", description="Penalty awarded",
            raw_type_label="VAR penalty review")), "penalty_awarded")
        self.assertIsNone(classify_key_moment(event("var", description="Goal disallowed",
            raw_type_label="VAR penalty review")))

    def test_disallowed_and_pending_goals_are_never_scoring(self):
        for data in (event("goal", description="Goal disallowed"), event("disallowed_goal"),
                     event("goal", description="Possible goal disallowed"), event("goal", is_scoring_event=False)):
            self.assertFalse(scheduler.is_scoring_event({**data, **({} if data.get("is_scoring_event") is False else {"is_scoring_event": True})}))

    def test_actual_wrapper_description_is_preserved_without_private_fields(self):
        normalized = normalize_match_event({"id": "mp_event_real_shape", "normalized_type": "var", "raw_type": 5,
            "description_fa": "گل مردود شده", "provider": "private", "decisionTitle": "not public"})[0]
        self.assertEqual(normalized["description"], "گل مردود شده")
        self.assertEqual(classify_key_moment(normalized), "goal_disallowed")
        self.assertNotIn("decisionTitle", normalized)
        self.assertNotIn("provider", normalized)

    def test_full_timeline_types_are_not_removed(self):
        data = [event("yellow_card"), event("substitution"), event("goal")]
        timeline = [normalize_match_event(row)[0] for row in data]
        self.assertEqual([row["type"] for row in timeline], ["yellow_card", "substitution", "goal"])
        self.assertEqual(len(data), 3)

    def test_messages_are_localized_without_raw_decision_payloads(self):
        for lang, expected in (("en", "Penalty awarded"), ("fa", "پنالتی اعلام شد")):
            notification = scheduler.event_notification(event("other", description="Penalty awarded", raw_event={"private": "secret"}), match(), lang)
            self.assertIn(expected, notification[2])
            self.assertNotIn("secret", notification[2])


class KeyMomentPersistenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        database = patch.object(db_service, "DB_PATH", Path(directory.name) / "test.sqlite")
        database.start(); self.addCleanup(database.stop)
        db_service.init_db()
        self.favorites = {10: [{"competition_key": "premier_league", "team_id": "mp_team_home", "name_en": "Home"}],
                          20: [{"competition_key": "la_liga", "team_id": "mp_team_home", "name_en": "Home"}]}
        loop = Mock(); loop.is_closed.return_value = False
        state = patch.dict(scheduler.scheduler_state, {"bot_app": object(), "event_loop": loop,
            "favorite_teams": self.favorites, "seeded_existing_live_notifications": True,
            "pending_startup_event_seed": set(), "suppressed_notifications": set()})
        state.start(); self.addCleanup(state.stop)
        scheduler.delivered_pending_persistence.clear()
        self.addCleanup(scheduler.delivered_pending_persistence.clear)
        for target, options in (
            ("scheduler_service.notification_dry_run", {"return_value": False}),
            ("scheduler_service.live_notifications_enabled", {"return_value": True}),
            ("scheduler_service.send_telegram_message", {"new": Mock(return_value="mocked-coroutine")}),
            ("scheduler_service.get_all_users", {"return_value": [{"telegram_id": 10, "language_code": "en"}]}),
            ("scheduler_service.get_all_favorite_teams_from_db", {"return_value": self.favorites}),
        ):
            mocked = patch(target, **options); mocked.start(); self.addCleanup(mocked.stop)
        sending = patch("scheduler_service.asyncio.run_coroutine_threadsafe", return_value=Mock())
        self.send = sending.start(); self.addCleanup(sending.stop)

    def dispatch(self, row, current=None):
        return scheduler.dispatch_event_notification(object(), 10, current or match(), row, favorites=self.favorites[10])

    def test_repeat_poll_and_new_database_connection_do_not_repeat_goal(self):
        self.assertTrue(self.dispatch(event()))
        self.assertFalse(self.dispatch(event()))
        scheduler.scheduler_state["suppressed_notifications"].clear()
        self.assertFalse(self.dispatch(event(player_name="Corrected name", home_score=2)))
        self.assertEqual(self.send.call_count, 1)

    def test_review_and_final_outcome_each_send_once_for_same_event_id(self):
        for text in ("VAR goal review", "VAR goal review", "Goal disallowed", "Goal disallowed"):
            self.dispatch(event("var", description=text))
        self.assertEqual(self.send.call_count, 2)
        self.assertFalse(self.dispatch(event("var", description="Goal disallowed")))

    def test_idless_corrections_do_not_resend_same_scoring_state(self):
        self.dispatch(event(id=None, description="Goal", home_score=1))
        self.dispatch(event(id=None, description="Updated scorer details", home_score=2))
        self.assertEqual(self.send.call_count, 1)

    def test_same_id_different_competitions_stays_isolated(self):
        self.dispatch(event())
        self.dispatch(event(), match("la_liga"))
        self.assertEqual(self.send.call_count, 2)

    def test_provider_correction_in_same_payload_uses_latest_exact_id_only(self):
        timeline = [event(), event("var", description="Goal disallowed")]
        for row in scheduler.current_push_events(timeline):
            self.dispatch(row)
        self.assertEqual(self.send.call_count, 1)
        self.assertTrue(db_service.has_live_notification_been_sent(10,
            scheduler.notification_match_reference(match()), "goal_disallowed", "event:mp_event_shared"))
        self.assertFalse(db_service.has_live_notification_been_sent(10,
            scheduler.notification_match_reference(match()), "goal", "event:mp_event_shared"))
        self.assertEqual(len(timeline), 2)

    def test_cross_generic_legacy_and_favorite_goal_paths_send_once(self):
        fixture = match()
        with patch("scheduler_service.discover_generic_notification_matches", return_value=[fixture]), \
             patch("scheduler_service.refreshed_live_match", return_value=fixture), \
             patch("scheduler_service.scoped_match_events", return_value=[event()]), \
             patch("scheduler_service.load_matches", return_value=[fixture]), \
             patch("scheduler_service.load_events", return_value=[event()]), \
             patch("scheduler_service.get_relevant_users_for_match", return_value=[10]):
            scheduler.check_generic_live_match_notifications_once()
            scheduler.check_legacy_live_match_notifications_once()
            scheduler.check_favorite_goal_notifications()
        # Two existing kickoff namespaces remain unchanged; exactly one goal.
        with closing(db_service.get_connection()) as conn:
            count = conn.execute("SELECT COUNT(*) FROM live_notification_log WHERE notification_type='goal'").fetchone()[0]
        self.assertEqual(count, 1)

    def test_favorite_helper_never_widens_competition_recipients(self):
        with patch("scheduler_service.load_matches", return_value=[match()]), patch("scheduler_service.load_events", return_value=[event()]):
            scheduler.check_favorite_goal_notifications()
        self.assertEqual(self.send.call_count, 1)
        with closing(db_service.get_connection()) as conn:
            users = conn.execute("SELECT DISTINCT telegram_id FROM live_notification_log").fetchall()
        self.assertEqual(users, [(10,)])

    def test_startup_seeds_all_supported_moments_without_sending(self):
        fixture = match()
        rows = [event("goal"), event("red_card", id="mp_event_red"),
                event("var", id="mp_event_review", description="VAR penalty review"),
                event("other", id="mp_event_award", description="Penalty awarded"),
                event("substitution", id="mp_event_sub")]
        with patch("scheduler_service.refreshed_live_match", return_value=fixture), patch("scheduler_service.scoped_match_events", return_value=rows):
            scheduler.seed_generic_live_notification_state([fixture], self.favorites)
        for row in rows:
            self.dispatch(row)
        self.send.assert_not_called()

    def test_send_failure_leaves_persistent_marker_unset_and_allows_retry(self):
        self.send.return_value.result.side_effect = RuntimeError("mock send failure")
        self.assertFalse(self.dispatch(event()))
        self.assertFalse(db_service.has_live_notification_been_sent(10,
            scheduler.notification_match_reference(match()), "goal", "event:mp_event_shared"))
        self.send.return_value.result.side_effect = None
        self.assertTrue(self.dispatch(event()))

    def test_send_success_marker_failure_retries_storage_without_resending(self):
        real_mark = db_service.mark_live_notification_sent
        with patch("scheduler_service.mark_live_notification_sent", side_effect=RuntimeError("storage failed")):
            self.assertFalse(self.dispatch(event()))
        with patch("scheduler_service.mark_live_notification_sent", side_effect=real_mark):
            self.assertFalse(self.dispatch(event()))
        self.assertEqual(self.send.call_count, 1)
        self.assertTrue(db_service.has_live_notification_been_sent(10,
            scheduler.notification_match_reference(match()), "goal", "event:mp_event_shared"))

    def test_idless_alias_write_failure_is_not_a_second_send(self):
        real_mark = db_service.mark_live_notification_sent
        def fail_alias(*identity):
            if identity[-1].startswith("moment:"):
                raise RuntimeError("alias storage unavailable")
            return real_mark(*identity)
        with patch("scheduler_service.mark_live_notification_sent", side_effect=fail_alias):
            self.assertTrue(self.dispatch(event(id=None, description="Goal")))
        self.assertFalse(self.dispatch(event(id=None, description="Corrected description")))
        self.assertEqual(self.send.call_count, 1)

    def test_old_legacy_goal_marker_suppresses_new_shared_path(self):
        fixture = {**match("worldcup2026"), "id": "31", "season_key": "2026"}
        favorite = {"competition_key": "worldcup2026", "team_id": "mp_team_home", "name_en": "Home"}
        old_key = scheduler.legacy_favorite_goal_keys(10, fixture, event(), [favorite])[0]
        db_service.mark_notification_sent(old_key, user_id=10, match_id="31")
        self.assertFalse(scheduler.dispatch_event_notification(object(), 10, fixture, event(), favorites=[favorite]))
        self.send.assert_not_called()
        self.assertTrue(db_service.has_live_notification_been_sent(10,
            scheduler.notification_match_reference(fixture), "goal", "event:mp_event_shared"))

    def test_startup_event_provider_failure_seeds_first_recovered_payload(self):
        fixture = match()
        with patch("scheduler_service.refreshed_live_match", return_value=fixture), \
             patch("scheduler_service.scoped_match_events", side_effect=RuntimeError("unavailable")):
            scheduler.seed_generic_live_notification_state([fixture], self.favorites)
        self.assertIn(scheduler.notification_match_reference(fixture), scheduler.scheduler_state["pending_startup_event_seed"])
        with patch("scheduler_service.discover_generic_notification_matches", return_value=[fixture]), \
             patch("scheduler_service.refreshed_live_match", return_value=fixture), \
             patch("scheduler_service.scoped_match_events", return_value=[event()]):
            scheduler.check_generic_live_match_notifications_once()
        self.send.assert_not_called()
        self.assertFalse(self.dispatch(event()))
        self.assertTrue(self.dispatch(event(id="mp_event_new")))

    def test_legacy_startup_seeds_reminder_recipients_without_favorites(self):
        with patch("scheduler_service.get_all_favorite_teams_from_db", return_value={}), \
             patch("scheduler_service.get_relevant_users_for_match", return_value=[10]), \
             patch("scheduler_service.load_matches", return_value=[match()]), \
             patch("scheduler_service.load_events", return_value=[event()]):
            scheduler.scheduler_state["seeded_existing_live_notifications"] = False
            scheduler.seed_existing_match_notification_state()
        self.send.assert_not_called()
        self.assertFalse(self.dispatch(event()))

    def test_key_moments_do_not_bypass_disabled_live_notifications(self):
        with patch("scheduler_service.live_notifications_enabled", return_value=False), \
             patch("scheduler_service.check_generic_live_match_notifications_once") as generic, \
             patch("scheduler_service.check_legacy_live_match_notifications_once") as legacy:
            scheduler.check_live_match_notifications_once()
            scheduler.check_favorite_goal_notifications()
        generic.assert_not_called()
        legacy.assert_not_called()
        self.send.assert_not_called()

    def test_concurrent_notification_paths_share_one_delivery(self):
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda _: self.dispatch(event()), range(6)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(self.send.call_count, 1)

    def test_legacy_match_provider_failure_defers_startup_seed(self):
        scheduler.scheduler_state["seeded_existing_live_notifications"] = False
        scheduler.scheduler_state["get_matches"] = Mock(side_effect=RuntimeError("private provider detail"))
        scheduler.seed_existing_match_notification_state()
        self.assertFalse(scheduler.scheduler_state["seeded_existing_live_notifications"])
        self.send.assert_not_called()
        scheduler.scheduler_state["get_matches"] = Mock(return_value=[match()])
        with patch("scheduler_service.get_relevant_users_for_match", return_value=[10]), \
             patch("scheduler_service.load_events", return_value=[event()]):
            scheduler.seed_existing_match_notification_state()
        self.assertTrue(scheduler.scheduler_state["seeded_existing_live_notifications"])
        self.assertFalse(self.dispatch(event()))

    def test_legacy_finished_startup_seeds_actual_final_delivery_marker(self):
        fixture = {**match(), "status": "finished", "is_live": False, "is_finished": True}
        with patch("scheduler_service.load_matches", return_value=[fixture]), \
             patch("scheduler_service.load_events", return_value=[]), \
             patch("scheduler_service.get_relevant_users_for_match", return_value=[10]):
            scheduler.scheduler_state["seeded_existing_live_notifications"] = False
            scheduler.seed_existing_match_notification_state()
        self.assertTrue(db_service.has_sent_notification("final:mp_match_shared:10"))
        self.send.assert_not_called()
