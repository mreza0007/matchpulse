import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import db_service
import scheduler_service
from event_semantics import confirmed_disallowed_goal
from reminder_lifecycle_service import is_active_reminder, lifecycle_snapshot, refresh_active_reminders
from services.generic_football_adapter import normalize_match_event
from services.worldcup_adapter import normalize_event_type

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def match(minutes=120, **changes):
    return {"id": "mp_match_lifecycle", "match_id": "mp_match_lifecycle",
        "competition_key": "premier_league", "season_key": "2026-2027",
        "status": "upcoming", "kickoff_utc": (NOW + timedelta(minutes=minutes)).isoformat(), **changes}


class EventDecisionTests(unittest.TestCase):
    def test_numeric_var_is_neutral_without_confirmed_decision(self):
        for event in ({"eventType": 5}, {"eventType": 6},
                      {"eventType": 5, "description": "گل کمک داور ویدیویی"}):
            self.assertEqual(normalize_event_type(event), "var")
            self.assertFalse(confirmed_disallowed_goal(event))

    def test_confirmed_decisions_are_not_scoring_even_with_scoring_flag(self):
        for text in ("گل مردود شده", "گل رد شده", "Goal disallowed after VAR review", "Disallowed goal"):
            event = {"type": "goal", "description": text, "is_scoring_event": True}
            self.assertEqual(normalize_match_event(event)[0]["type"], "disallowed_goal")
            self.assertFalse(scheduler_service.is_scoring_event(event))
            self.assertEqual(scheduler_service.live_event_type(event), "disallowed_goal")

    def test_other_normalized_types_and_minutes_are_untouched(self):
        for event_type in ("goal", "own_goal", "missed_penalty", "red_card", "second_yellow_red", "substitution"):
            event = normalize_match_event({"type": event_type, "minute": "120+3", "player_in_name": "In", "player_out_name": "Out"})[0]
            self.assertEqual(event["type"], event_type)
            self.assertEqual(event["display_minute"], "120+3")
        self.assertTrue(scheduler_service.is_scoring_event({"type": "own_goal"}))
        self.assertFalse(scheduler_service.is_scoring_event({"type": "var", "is_scoring_event": True}))


class ReminderLifecycleTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db_patch = patch.object(db_service, "DB_PATH", Path(directory.name) / "test.sqlite")
        db_patch.start()
        self.addCleanup(db_patch.stop)
        db_service.init_db()

    def save(self, snapshot):
        db_service.save_reminder_to_db(100, snapshot, snapshot["competition_key"], snapshot["season_key"])

    def refresh(self, authoritative):
        records = db_service.get_reminders_from_db(100)
        with patch("competition_data_service.get_matches_for_season", return_value=authoritative):
            return refresh_active_reminders(100, records, NOW)

    def test_active_upcoming_and_future_trigger_policy(self):
        self.assertTrue(is_active_reminder(match(), NOW))
        for minutes in (60, 59, 0, -1):
            self.assertFalse(is_active_reminder(match(minutes), NOW))
        self.assertNotIn("reminder_state", lifecycle_snapshot(match(55), NOW))
        self.assertEqual(lifecycle_snapshot(match(54), NOW)["reminder_state"], "retired")

    def test_terminal_states_retire_persistently_without_deletion(self):
        self.addCleanup(scheduler_service.scheduler_state.update, bot_app=None, reminders=None)
        for status in ("live", "finished", "postponed", "cancelled"):
            with self.subTest(status=status):
                self.save(match())
                self.assertEqual(self.refresh([match(status=status)]), [])
                stored = db_service.get_reminders_from_db(100)
                self.assertEqual(len(stored), 1)
                self.assertEqual(stored[0]["reminder_state"], "retired")
                self.assertFalse(stored[0]["notified"])
                scheduler_service.scheduler_state.update(bot_app=object(), reminders={100: stored})
                with patch("scheduler_service.get_matches_for_season") as fetch, patch("scheduler_service.send_once") as send:
                    scheduler_service.check_manual_reminders(NOW)
                    fetch.assert_not_called()
                    send.assert_not_called()
                db_service.delete_reminder_from_db(100, "mp_match_lifecycle", "premier_league", "2026-2027")

    def test_missing_kickoff_and_expired_trigger_retire(self):
        for authoritative in (match(kickoff_utc=None), match(-1), match(54)):
            self.save(match())
            self.assertEqual(self.refresh([authoritative]), [])
            self.assertEqual(db_service.get_reminders_from_db(100)[0]["reminder_state"], "retired")
            db_service.delete_reminder_from_db(100, "mp_match_lifecycle", "premier_league", "2026-2027")

    def test_provider_failure_and_missing_match_do_not_mutate_history(self):
        self.save(match())
        original = db_service.get_reminders_from_db(100)
        self.assertEqual(self.refresh([]), [])
        with patch("competition_data_service.get_matches_for_season", side_effect=RuntimeError("private provider error")):
            self.assertEqual(refresh_active_reminders(100, original, NOW), [])
        self.assertEqual(db_service.get_reminders_from_db(100), original)

    def test_fired_and_worldcup_history_are_preserved(self):
        self.save(match())
        db_service.mark_reminder_notified(100, "mp_match_lifecycle", "premier_league", "2026-2027")
        legacy = match(competition_key="worldcup2026", season_key="2026", id="42", match_id="42")
        self.save(legacy)
        self.assertEqual(self.refresh([match()]), [])
        self.assertEqual(len(db_service.get_reminders_from_db(100)), 2)
        self.assertTrue(db_service.get_reminders_from_db(100)[0]["notified"])
        self.assertTrue(db_service.delete_reminder_from_db(100, "42", "worldcup2026", "2026"))

    def test_retirement_scope_and_explicit_renewal_preserve_row(self):
        self.save(match())
        self.save(match(competition_key="la_liga"))
        retired = lifecycle_snapshot(match(status="postponed"), NOW)
        db_service.update_reminder_snapshot(100, "mp_match_lifecycle", "premier_league", "2026-2027", retired)
        self.assertEqual(db_service.get_reminders_from_db(100, "la_liga", "2026-2027")[0]["status"], "upcoming")
        self.assertTrue(db_service.save_reminder_to_db(100, match(), "premier_league", "2026-2027"))
        self.assertEqual(len(db_service.get_reminders_from_db(100)), 2)
        self.assertNotIn("reminder_state", db_service.get_reminders_from_db(100)[0])
        self.assertFalse(db_service.save_reminder_to_db(100, match(), "premier_league", "2026-2027"))

    def test_legacy_terminal_snapshot_cannot_deliver(self):
        for status in ("live", "finished", "postponed", "cancelled"):
            with patch("scheduler_service.send_once") as send:
                result = scheduler_service.send_manual_reminder(object(), 100,
                    match(60, competition_key="worldcup2026", season_key="2026", status=status),
                    (100, "worldcup2026", "2026", "42"), NOW)
                self.assertFalse(result)
                send.assert_not_called()

    def test_active_api_refresh_and_historical_read_are_separate(self):
        from fastapi.testclient import TestClient
        import main
        self.addCleanup(main.reminders.clear)
        self.save(match())
        client = TestClient(main.api)
        with patch("competition_data_service.get_matches_for_season", return_value=[match(status="postponed")]) as fetch:
            response = client.get("/reminders/100?view=active")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["reminders"], [])
            fetch.assert_called_once()
        self.assertEqual(client.get("/reminders/100").json()["count"], 1)
        self.assertEqual(client.get("/reminders/100").json()["reminders"][0]["reminder_state"], "retired")

    def test_creation_rejects_past_trigger_and_fired_identity(self):
        from fastapi.testclient import TestClient
        from reminder_service import prepare_reminder_snapshot, ReminderEligibilityError
        import main
        self.addCleanup(main.reminders.clear)
        request = {"competition_key": "premier_league", "season_key": "2026-2027", "match_id": "mp_match_lifecycle"}
        with patch("reminder_service.get_match_for_season", return_value=match(60)):
            with self.assertRaises(ReminderEligibilityError):
                prepare_reminder_snapshot(request, NOW)
        self.save(match())
        db_service.mark_reminder_notified(100, "mp_match_lifecycle", "premier_league", "2026-2027")
        with patch("reminder_service.get_match_for_season", return_value=match()):
            response = TestClient(main.api).post("/reminder", json={"telegram_id": 100, **request})
        self.assertEqual(response.status_code, 409)
        self.assertTrue(db_service.get_reminders_from_db(100)[0]["notified"])

    def test_expired_legacy_reminder_retires_without_provider_or_deletion(self):
        self.addCleanup(scheduler_service.scheduler_state.update, bot_app=None, reminders=None)
        self.save(match(-1, id="42", match_id="42", competition_key="worldcup2026", season_key="2026"))
        scheduler_service.scheduler_state.update(bot_app=object(), reminders={100: db_service.get_reminders_from_db(100)})
        with patch("scheduler_service.get_matches_for_season") as fetch, patch("scheduler_service.send_once") as send:
            scheduler_service.check_manual_reminders(NOW)
            fetch.assert_not_called()
            send.assert_not_called()
        record = db_service.get_reminders_from_db(100)[0]
        self.assertEqual(record["reminder_state"], "retired")
        self.assertFalse(record["notified"])
