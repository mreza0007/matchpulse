import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import db_service
import scheduler_service


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def competition(key, *, active=True, live=True, events=True):
    return {
        "competition_key": key,
        "season_key": "2026-2027",
        "status": "active" if active else "archived",
        "is_active": active,
        "supports_live": live,
        "supports_events": events,
    }


def match(key="premier_league", match_id="mp_match_shared", status="live"):
    return {
        "id": match_id,
        "competition_key": key,
        "season_key": "2026-2027",
        "status": status,
        "is_live": status == "live",
        "is_finished": status == "finished",
        "kickoff_utc": (NOW - timedelta(hours=1)).isoformat(),
        "home_team_id": "mp_team_home",
        "away_team_id": "mp_team_away",
        "home_fa": "خانه",
        "away_fa": "میهمان",
        "home_en": "Home",
        "away_en": "Away",
        "home_score": 2,
        "away_score": 1,
        "score": {"home": 2, "away": 1},
    }


def favorite(competition_key="premier_league", team_id="mp_team_home"):
    return {
        "competition_key": competition_key,
        "team_id": team_id,
        "id": team_id,
        "name_en": "Home",
    }


class GenericLiveNotificationTests(unittest.TestCase):
    def setUp(self):
        scheduler_service.pending_final_confirmations.clear()
        scheduler_service.scheduler_state.update({
            "bot_app": object(),
            "favorite_teams": None,
            "get_daily_matches": None,
            "get_live_match": None,
            "get_scoped_events": None,
            "get_competitions": None,
            "seeded_existing_live_notifications": True,
            "pending_startup_event_seed": set(),
            "suppressed_notifications": set(),
        })

    def configure_discovery(self, groups):
        scheduler_service.scheduler_state["get_competitions"] = lambda: [
            competition("premier_league"),
            competition("uefa_nations_league_a"),
            competition("worldcup2026", active=False, live=False, events=False),
        ]
        daily = Mock(return_value={"groups": groups, "source_errors": []})
        scheduler_service.scheduler_state["get_daily_matches"] = daily
        return daily

    def test_generic_discovery_includes_club_and_nations_once_and_excludes_archive_and_postponed(self):
        premier = match("premier_league", "mp_match_club")
        nations = match("uefa_nations_league_a", "mp_match_nations")
        archived = match("worldcup2026", "mp_match_worldcup")
        postponed = match("premier_league", "mp_match_postponed", "postponed")
        daily = self.configure_discovery([
            {"competition": {"key": "premier_league", "season_key": "2026-2027"}, "matches": [premier, postponed]},
            {"competition": {"key": "uefa_nations_league_a", "season_key": "2026-2027"}, "matches": [nations]},
            {"competition": {"key": "worldcup2026", "season_key": "2026"}, "matches": [archived]},
        ])
        discovered = scheduler_service.discover_generic_notification_matches(now=NOW)
        self.assertEqual(
            {item["id"] for item in discovered},
            {"mp_match_club", "mp_match_nations"},
        )
        self.assertEqual(daily.call_count, 2)

    def test_favorites_are_competition_scoped_and_national_team_ids_work(self):
        nations = match("uefa_nations_league_a", "mp_match_nations")
        favorites = {
            10: [favorite("uefa_nations_league_a")],
            20: [favorite("premier_league")],
            30: [favorite("uefa_nations_league_a", "mp_team_other")],
        }
        self.assertEqual(
            scheduler_service.favorite_user_ids_for_match(favorites, nations),
            [10],
        )

    def test_event_identity_is_stable_across_reordering_and_covers_all_types(self):
        fixture = match()
        events = [
            {"id": "mp_event_goal", "type": "goal", "team_side": "home", "minute": 12, "player_name": "A"},
            {"id": "mp_event_yellow", "type": "yellow_card", "team_side": "away", "minute": 20},
            {"id": "mp_event_red", "type": "second_yellow_red", "team_side": "away", "minute": 30},
            {"id": "mp_event_sub", "type": "substitution", "team_side": "home", "minute": 40},
            {"id": "mp_event_half", "type": "halftime", "minute": 45},
        ]
        first = [scheduler_service.event_notification(event, fixture)[:2] for event in events]
        second = [scheduler_service.event_notification(event, fixture)[:2] for event in reversed(events)]
        self.assertEqual(set(first), set(second))
        self.assertEqual(
            {item[0] for item in first},
            {"goal", "yellow_card", "red_card", "substitution", "halftime"},
        )
        self.assertNotIn("None", scheduler_service.build_substitution_message(fixture, events[3]))

    def test_one_cycle_fetches_live_and_events_once_then_fans_out_only_to_favorites(self):
        fixture = match("uefa_nations_league_a", "mp_match_nations")
        self.configure_discovery([
            {"competition": {"key": "uefa_nations_league_a", "season_key": "2026-2027"}, "matches": [fixture]},
        ])
        live = Mock(return_value={"match": {**fixture, "live_phase": "halftime"}})
        events = Mock(return_value={"events": [
            {"id": "mp_event_goal_1", "type": "goal", "team_side": "home", "minute": 12},
            {"id": "mp_event_goal_2", "type": "penalty_goal", "team_side": "away", "minute": 22},
            {"id": "mp_event_yellow", "type": "yellow_card", "team_side": "away", "minute": 24},
            {"id": "mp_event_red", "type": "red_card", "team_side": "away", "minute": 30},
            {"id": "mp_event_sub", "type": "substitution", "team_side": "home", "minute": 35, "player_in_name": "In", "player_out_name": "Out"},
        ]})
        scheduler_service.scheduler_state["get_live_match"] = live
        scheduler_service.scheduler_state["get_scoped_events"] = events
        sent = []

        def record_send(_bot, telegram_id, _match, notification_type, event_key, _text):
            sent.append((telegram_id, notification_type, event_key))
            return True

        with (
            patch("scheduler_service.get_all_favorite_teams_from_db", return_value={
                10: [favorite("uefa_nations_league_a")],
                20: [favorite("premier_league")],
            }),
            patch("scheduler_service.get_all_users", return_value=[
                {"telegram_id": 10, "language_code": "fa"},
                {"telegram_id": 20, "language_code": "en"},
            ]),
            patch("scheduler_service.send_live_notification_once", side_effect=record_send),
        ):
            scheduler_service.check_generic_live_match_notifications_once()

        self.assertEqual(live.call_count, 1)
        self.assertEqual(events.call_count, 1)
        self.assertEqual({item[0] for item in sent}, {10})
        self.assertEqual(
            [item[1] for item in sent].count("goal"),
            2,
        )
        self.assertEqual(
            {item[1] for item in sent},
            {"match_started", "halftime", "goal", "yellow_card", "red_card", "substitution"},
        )

    def test_repeated_poll_and_provider_reorder_do_not_resend_events(self):
        fixture = match()
        self.configure_discovery([
            {"competition": {"key": "premier_league", "season_key": "2026-2027"}, "matches": [fixture]},
        ])
        scheduler_service.scheduler_state["get_live_match"] = lambda *_args: {"match": fixture}
        event_rows = [
            {"id": "mp_event_goal_1", "type": "goal", "team_side": "home", "minute": 10},
            {"id": "mp_event_goal_2", "type": "goal", "team_side": "away", "minute": 20},
            {"id": "mp_event_yellow", "type": "yellow_card", "team_side": "away", "minute": 30},
        ]
        events = Mock(side_effect=[
            {"events": event_rows},
            {"events": list(reversed(event_rows))},
        ])
        scheduler_service.scheduler_state["get_scoped_events"] = events
        scheduler_service.scheduler_state["favorite_teams"] = {10: [favorite()]}
        seen = set()
        delivered = []

        def persistent_send(_bot, telegram_id, current, notification_type, event_key, _text):
            identity = (
                telegram_id,
                scheduler_service.notification_match_reference(current),
                notification_type,
                event_key,
            )
            if identity in seen:
                return False
            seen.add(identity)
            delivered.append(identity)
            return True

        with (
            patch("scheduler_service.get_all_users", return_value=[{"telegram_id": 10}]),
            patch("scheduler_service.send_live_notification_once", side_effect=persistent_send),
        ):
            scheduler_service.check_generic_live_match_notifications_once()
            scheduler_service.check_generic_live_match_notifications_once()

        self.assertEqual(events.call_count, 2)
        self.assertEqual(
            [item[2] for item in delivered].count("goal"),
            2,
        )
        self.assertEqual(
            [item[2] for item in delivered].count("yellow_card"),
            1,
        )
        self.assertEqual(
            [item[2] for item in delivered].count("match_started"),
            1,
        )

    def test_startup_seeds_kickoff_events_and_halftime_without_sending(self):
        fixture = {**match(), "supports_events": True, "live_phase": "halftime"}
        scheduler_service.scheduler_state["get_live_match"] = lambda *_args: {"match": fixture}
        scheduler_service.scheduler_state["get_scoped_events"] = lambda *_args: {"events": [
            {"id": "mp_event_goal", "type": "goal", "team_side": "home"},
            {"id": "mp_event_yellow", "type": "yellow_card", "team_side": "away"},
            {"id": "mp_event_sub", "type": "substitution", "team_side": "home"},
        ]}
        persisted = set()

        def already(user, reference, notification_type, event_key):
            return (user, reference, notification_type, event_key) in persisted

        def mark(user, reference, notification_type, event_key):
            persisted.add((user, reference, notification_type, event_key))
            return True

        with (
            patch("scheduler_service.has_live_notification_been_sent", side_effect=already),
            patch("scheduler_service.mark_live_notification_sent", side_effect=mark),
            patch("scheduler_service.send_live_notification_once") as send,
        ):
            scheduler_service.seed_generic_live_notification_state(
                [fixture], {10: [favorite()]}
            )
        send.assert_not_called()
        self.assertEqual(
            {item[2] for item in persisted},
            {"match_started", "halftime", "goal", "yellow_card", "substitution"},
        )
        self.assertTrue(scheduler_service.scheduler_state["seeded_existing_live_notifications"])

    def test_persistent_lookup_uses_competition_season_and_canonical_match(self):
        fixture = match("uefa_nations_league_a", "mp_match_nations")
        with (
            patch("scheduler_service.has_live_notification_been_sent", return_value=True) as already,
            patch("scheduler_service.mark_live_notification_sent") as mark,
        ):
            result = scheduler_service.send_live_notification_once(
                object(), 10, fixture, "goal", "event:mp_event_goal", "text"
            )
        self.assertFalse(result)
        already.assert_called_once_with(
            10,
            "uefa_nations_league_a:2026-2027:mp_match_nations",
            "goal",
            "event:mp_event_goal",
        )
        mark.assert_not_called()

    def test_scoped_live_notification_marker_survives_a_new_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "notifications.sqlite"
            with patch.object(db_service, "DB_PATH", db_path):
                db_service.init_db()
                reference = "uefa_nations_league_a:2026-2027:mp_match_nations"
                self.assertTrue(
                    db_service.mark_live_notification_sent(
                        10, reference, "goal", "event:mp_event_goal"
                    )
                )
                self.assertTrue(
                    db_service.has_live_notification_been_sent(
                        10, reference, "goal", "event:mp_event_goal"
                    )
                )
                self.assertFalse(
                    db_service.has_live_notification_been_sent(
                        10,
                        "premier_league:2026-2027:mp_match_nations",
                        "goal",
                        "event:mp_event_goal",
                    )
                )

    def test_fulltime_requires_two_matching_finished_observations(self):
        fixture = match(status="finished")
        favorites = {10: [favorite()]}
        sent = []
        with (
            patch("scheduler_service.match_is_recently_finished", return_value=True),
            patch("scheduler_service.send_live_notification_once", side_effect=lambda *args: sent.append(args) or True),
        ):
            scheduler_service.process_generic_final_confirmations(
                [fixture], object(), favorites, {10: {"language_code": "en"}}
            )
            self.assertEqual(sent, [])
            scheduler_service.process_generic_final_confirmations(
                [fixture], object(), favorites, {10: {"language_code": "en"}}
            )
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][3:5], ("fulltime", "phase:fulltime"))
        self.assertIn("Full Time", sent[0][5])
        self.assertIn("2 - 1", sent[0][5])

    def test_default_off_rollout_keeps_legacy_dispatch_until_explicitly_enabled(self):
        with (
            patch.dict(os.environ, {}, clear=False),
            patch("scheduler_service.check_legacy_live_match_notifications_once") as legacy,
            patch("scheduler_service.check_generic_live_match_notifications_once") as generic,
        ):
            os.environ.pop("ENABLE_GENERIC_LIVE_NOTIFICATIONS", None)
            scheduler_service.check_live_match_notifications_once()
            legacy.assert_called_once()
            generic.assert_not_called()
            os.environ["ENABLE_GENERIC_LIVE_NOTIFICATIONS"] = "true"
            scheduler_service.check_live_match_notifications_once()
            generic.assert_called_once()


if __name__ == "__main__":
    unittest.main()
