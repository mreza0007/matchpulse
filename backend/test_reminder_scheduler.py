import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import competition_service
import db_service
import scheduler_service


NOW = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)


def kickoff(minutes):
    return (NOW + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def generic_match(
    match_id="shared",
    minutes=60,
    status="upcoming",
    **overrides,
):
    match = {
        "id": match_id,
        "status": status,
        "is_live": status == "live",
        "is_finished": status == "finished",
        "kickoff_utc": kickoff(minutes),
        "home_team": "Home",
        "away_team": "Away",
    }
    match.update(overrides)
    return match


def stored_reminder(
    competition_key="premier_league",
    season_key="2026-2027",
    match_id="shared",
    notified=False,
    **overrides,
):
    match = {
        **generic_match(match_id=match_id),
        "competition_key": competition_key,
        "season_key": season_key,
        "match_id": match_id,
        "notified": notified,
    }
    match.update(overrides)
    return match


class ReminderSchedulerTests(unittest.TestCase):
    def setUp(self):
        scheduler_service.scheduler_state["bot_app"] = object()
        scheduler_service.scheduler_state["reminders"] = {}

    def tearDown(self):
        scheduler_service.scheduler_state["bot_app"] = None
        scheduler_service.scheduler_state["reminders"] = None

    def run_cycle(self, reminders, provider, *, send=True, update=True):
        scheduler_service.scheduler_state["reminders"] = reminders
        update_options = (
            {"side_effect": update}
            if isinstance(update, Exception)
            else {"return_value": update}
        )
        with (
            patch(
                "scheduler_service.get_matches_for_season",
                side_effect=provider,
            ) as fetch,
            patch(
                "scheduler_service.update_reminder_snapshot",
                **update_options,
            ) as update_snapshot,
            patch(
                "scheduler_service.has_sent_notification",
                return_value=False,
            ),
            patch(
                "scheduler_service.send_once",
                return_value=send,
            ) as send_once,
            patch(
                "scheduler_service.mark_reminder_notified",
                return_value=True,
            ) as mark_notified,
        ):
            scheduler_service.check_manual_reminders(now=NOW)
        return fetch, update_snapshot, send_once, mark_notified

    def test_scheduler_keys_are_competition_and_season_scoped(self):
        premier = scheduler_service.reminder_identity(
            10, stored_reminder()
        )
        la_liga = scheduler_service.reminder_identity(
            10, stored_reminder(competition_key="la_liga")
        )
        next_season = scheduler_service.reminder_identity(
            10, stored_reminder(season_key="2027-2028")
        )

        keys = {
            scheduler_service.manual_reminder_key(identity)
            for identity in (premier, la_liga, next_season)
        }
        self.assertEqual(len(keys), 3)

    def test_delivery_marks_the_exact_scoped_tuple(self):
        reminder = stored_reminder()
        _fetch, _update, send_once, mark_notified = self.run_cycle(
            {10: [reminder]},
            lambda *_args, **_kwargs: [generic_match()],
        )

        send_once.assert_called_once()
        mark_notified.assert_called_once_with(
            10, "shared", "premier_league", "2026-2027"
        )
        self.assertTrue(reminder["notified"])

    def test_already_notified_is_never_refetched_or_resent(self):
        fetch, _update, send_once, mark_notified = self.run_cycle(
            {10: [stored_reminder(notified=True)]},
            lambda *_args, **_kwargs: [generic_match()],
        )
        fetch.assert_not_called()
        send_once.assert_not_called()
        mark_notified.assert_not_called()

    def test_unchanged_authoritative_kickoff_delivers_in_window(self):
        reminder = stored_reminder()
        _fetch, update_snapshot, send_once, mark_notified = self.run_cycle(
            {10: [reminder]},
            lambda *_args, **_kwargs: [generic_match(minutes=60)],
        )
        update_snapshot.assert_not_called()
        send_once.assert_called_once()
        mark_notified.assert_called_once()

    def test_postponed_kickoff_updates_snapshot_without_stale_send(self):
        reminder = stored_reminder(minutes=60)
        _fetch, update_snapshot, send_once, mark_notified = self.run_cycle(
            {10: [reminder]},
            lambda *_args, **_kwargs: [generic_match(minutes=180)],
        )
        update_snapshot.assert_called_once()
        self.assertEqual(reminder["kickoff_utc"], kickoff(180))
        send_once.assert_not_called()
        mark_notified.assert_not_called()

    def test_moved_earlier_kickoff_controls_eligibility(self):
        reminder = stored_reminder(minutes=180)
        _fetch, _update, send_once, mark_notified = self.run_cycle(
            {10: [reminder]},
            lambda *_args, **_kwargs: [generic_match(minutes=50)],
        )
        self.assertEqual(reminder["kickoff_utc"], kickoff(50))
        send_once.assert_not_called()
        mark_notified.assert_not_called()

    def test_missing_or_invalid_refreshed_kickoff_is_retained_not_sent(self):
        for label, kickoff_value in (
            ("missing", None),
            ("invalid", "not-a-date"),
            ("naive", "2030-01-01T13:00:00"),
            ("past", "2030-01-01T11:59:59Z"),
        ):
            with self.subTest(label=label):
                reminder = stored_reminder()
                refreshed = generic_match(kickoff_utc=kickoff_value)
                _fetch, update_snapshot, send_once, mark_notified = self.run_cycle(
                    {10: [reminder]},
                    lambda *_args, value=refreshed, **_kwargs: [value],
                )
                update_snapshot.assert_called_once()
                self.assertEqual(reminder["kickoff_utc"], kickoff_value)
                send_once.assert_not_called()
                mark_notified.assert_not_called()

    def test_live_finished_and_cancelled_matches_are_not_sent(self):
        for status in ("live", "finished", "cancelled"):
            with self.subTest(status=status):
                reminder = stored_reminder()
                _fetch, _update, send_once, mark_notified = self.run_cycle(
                    {10: [reminder]},
                    lambda *_args, value=generic_match(status=status), **_kwargs: [value],
                )
                send_once.assert_not_called()
                mark_notified.assert_not_called()

    def test_missing_match_is_not_updated_sent_or_marked(self):
        _fetch, update_snapshot, send_once, mark_notified = self.run_cycle(
            {10: [stored_reminder()]},
            lambda *_args, **_kwargs: [
                generic_match(match_id="other", external_match_id="shared")
            ],
        )
        update_snapshot.assert_not_called()
        send_once.assert_not_called()
        mark_notified.assert_not_called()

    def test_provider_failure_isolated_by_scope(self):
        reminders = {
            10: [stored_reminder(competition_key="premier_league")],
            20: [stored_reminder(competition_key="la_liga")],
        }

        def provider(competition_key, _season_key, status):
            self.assertEqual(status, "all")
            if competition_key == "premier_league":
                raise RuntimeError("secret provider detail")
            return [generic_match()]

        fetch, _update, send_once, mark_notified = self.run_cycle(
            reminders, provider
        )
        self.assertEqual(fetch.call_count, 2)
        send_once.assert_called_once()
        self.assertEqual(send_once.call_args.args[1], 20)
        mark_notified.assert_called_once_with(
            20, "shared", "la_liga", "2026-2027"
        )
        self.assertFalse(reminders[10][0]["notified"])

    def test_refresh_fetches_once_per_competition_and_season(self):
        reminders = {
            10: [stored_reminder()],
            20: [stored_reminder()],
        }
        fetch, update_snapshot, send_once, _mark = self.run_cycle(
            reminders,
            lambda *_args, **_kwargs: [generic_match()],
        )
        fetch.assert_called_once_with(
            "premier_league", "2026-2027", status="all"
        )
        update_snapshot.assert_not_called()
        self.assertEqual(send_once.call_count, 2)

    def test_telegram_failure_does_not_mark_notified(self):
        reminder = stored_reminder()
        _fetch, _update, _send, mark_notified = self.run_cycle(
            {10: [reminder]},
            lambda *_args, **_kwargs: [generic_match()],
            send=False,
        )
        mark_notified.assert_not_called()
        self.assertFalse(reminder["notified"])

    def test_generic_formatting_tolerates_missing_optional_fields(self):
        text = scheduler_service.build_generic_match_message(
            generic_match(), "Reminder"
        )
        self.assertIn("Home", text)
        self.assertIn("Away", text)
        self.assertNotIn("None", text)

    def test_formatting_failure_does_not_send_or_mark(self):
        reminder = stored_reminder()
        with patch(
            "scheduler_service.build_generic_match_message",
            side_effect=ValueError("format detail"),
        ):
            _fetch, _update, send_once, mark_notified = self.run_cycle(
                {10: [reminder]},
                lambda *_args, **_kwargs: [generic_match()],
            )
        send_once.assert_not_called()
        mark_notified.assert_not_called()
        self.assertFalse(reminder["notified"])


    def test_worldcup_uses_stored_snapshot_without_provider_lookup(self):
        reminder = stored_reminder(
            competition_key="worldcup2026",
            season_key="2026",
            match_id="31",
            date_iran="2030-01-01",
            time_iran="13:00",
            stadium="Archive Stadium",
            city="Archive City",
        )
        fetch, _update, send_once, mark_notified = self.run_cycle(
            {99: [reminder]},
            lambda *_args, **_kwargs: self.fail("provider must not be called"),
        )
        fetch.assert_not_called()
        send_once.assert_called_once()
        mark_notified.assert_called_once_with(
            99, "31", "worldcup2026", "2026"
        )

    def test_delivery_window_boundaries_are_inclusive_only_at_edges(self):
        match = generic_match(minutes=60)
        self.assertTrue(
            scheduler_service.reminder_in_delivery_window(
                match, now=NOW - timedelta(minutes=5)
            )
        )
        self.assertTrue(
            scheduler_service.reminder_in_delivery_window(
                match, now=NOW + timedelta(minutes=5)
            )
        )
        self.assertFalse(
            scheduler_service.reminder_in_delivery_window(
                match,
                now=NOW - timedelta(minutes=5, seconds=1),
            )
        )
        self.assertFalse(
            scheduler_service.reminder_in_delivery_window(
                match,
                now=NOW + timedelta(minutes=5, seconds=1),
            )
        )
        self.assertFalse(
            scheduler_service.reminder_in_delivery_window(
                generic_match(minutes=0), now=NOW
            )
        )

    def test_snapshot_write_failure_keeps_stale_snapshot_unnotified(self):
        reminder = stored_reminder(minutes=60)
        _fetch, update_snapshot, send_once, mark_notified = self.run_cycle(
            {10: [reminder]},
            lambda *_args, **_kwargs: [generic_match(minutes=180)],
            update=RuntimeError("storage detail"),
        )
        update_snapshot.assert_called_once()
        self.assertEqual(reminder["kickoff_utc"], kickoff(60))
        send_once.assert_not_called()
        mark_notified.assert_not_called()
        self.assertFalse(reminder["notified"])

    def test_malformed_scope_does_not_block_another_scope(self):
        reminders = {
            10: [stored_reminder(competition_key="premier_league")],
            20: [stored_reminder(competition_key="la_liga")],
        }

        def provider(competition_key, _season_key, **_kwargs):
            if competition_key == "premier_league":
                return {"matches": [generic_match()]}
            return [generic_match()]

        fetch, _update, send_once, mark_notified = self.run_cycle(
            reminders, provider
        )
        self.assertEqual(fetch.call_count, 2)
        send_once.assert_called_once()
        self.assertEqual(send_once.call_args.args[1], 20)
        mark_notified.assert_called_once_with(
            20, "shared", "la_liga", "2026-2027"
        )
        self.assertFalse(reminders[10][0]["notified"])

    def test_mark_notified_failure_is_logged_and_dedupe_prevents_retry(self):
        reminder = stored_reminder()
        identity = scheduler_service.reminder_identity(10, reminder)
        expected_key = scheduler_service.manual_reminder_key(identity)
        with (
            patch(
                "scheduler_service.has_sent_notification",
                side_effect=[False, True],
            ),
            patch(
                "scheduler_service.send_once",
                return_value=True,
            ) as send_once,
            patch(
                "scheduler_service.mark_reminder_notified",
                side_effect=RuntimeError("storage detail"),
            ) as mark_notified,
            patch("builtins.print") as log,
        ):
            first = scheduler_service.send_manual_reminder(
                object(), 10, reminder, identity, now=NOW
            )
            second = scheduler_service.send_manual_reminder(
                object(), 10, reminder, identity, now=NOW
            )

        self.assertFalse(first)
        self.assertFalse(second)
        send_once.assert_called_once()
        mark_notified.assert_called_once()
        self.assertFalse(reminder["notified"])
        log.assert_any_call(
            f"Failed to mark manual reminder notified: {expected_key}"
        )
        log.assert_any_call(f"Skipped duplicate notification: {expected_key}")

    def test_public_capabilities_remain_disabled(self):
        for competition in competition_service.get_competitions():
            self.assertIs(competition["supports_reminders"], False)


class ReminderSchedulerStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "reminders.sqlite"
        self.db_patch = patch.object(db_service, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        db_service.init_db()

    def test_scoped_snapshot_update_changes_only_exact_tuple(self):
        scopes = [
            (1, "premier_league", "2026-2027"),
            (1, "la_liga", "2026-2027"),
            (1, "premier_league", "2027-2028"),
            (2, "premier_league", "2026-2027"),
        ]
        for telegram_id, competition_key, season_key in scopes:
            match = generic_match(home_team="Old")
            db_service.save_reminder_to_db(
                telegram_id, match, competition_key, season_key
            )
        db_service.mark_reminder_notified(
            1, "shared", "premier_league", "2026-2027"
        )

        changed = db_service.update_reminder_snapshot(
            1,
            "shared",
            "premier_league",
            "2026-2027",
            generic_match(home_team="Refreshed", notified=False),
        )
        self.assertTrue(changed)

        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        rows = conn.execute(
            """
            SELECT telegram_id, competition_key, season_key,
                   match_data, notified
            FROM reminders
            ORDER BY telegram_id, competition_key, season_key
            """
        ).fetchall()
        refreshed = [
            row for row in rows
            if row[:3] == (1, "premier_league", "2026-2027")
        ][0]
        self.assertEqual(json.loads(refreshed[3])["home_team"], "Refreshed")
        self.assertEqual(refreshed[4], 1)
        for row in rows:
            if row is not refreshed and row[:3] != refreshed[:3]:
                self.assertEqual(json.loads(row[3])["home_team"], "Old")
                self.assertEqual(row[4], 0)

    def test_related_user_lookup_is_scoped(self):
        db_service.save_reminder_to_db(
            10, generic_match(), "premier_league", "2026-2027"
        )
        db_service.save_reminder_to_db(
            20, generic_match(), "la_liga", "2026-2027"
        )
        with patch("db_service.get_all_favorite_teams_from_db", return_value={}):
            users = db_service.get_relevant_users_for_match({
                **generic_match(),
                "competition_key": "premier_league",
                "season_key": "2026-2027",
            })
        self.assertEqual(users, [10])


if __name__ == "__main__":
    unittest.main()
