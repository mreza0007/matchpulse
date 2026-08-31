import json
from datetime import datetime, timezone
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import competition_data_service
import competition_service
import db_service
import main
from reminder_service import (
    ReminderEligibilityError,
    validate_reminder_eligibility,
)


FUTURE_MATCH = {
    "id": "mp_match_1",
    "status": "upcoming",
    "is_upcoming": True,
    "is_live": False,
    "is_finished": False,
    "kickoff_utc": "2099-09-01T12:00:00Z",
    "home_team": "Server Home",
    "away_team": "Server Away",
    "round": "Week 99",
}


class ReminderV2ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "reminders.sqlite"
        self.db_patch = patch.object(db_service, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.capability_patch = patch(
            "reminder_service.get_competition",
            side_effect=self.reminder_enabled_competition,
        )
        self.capability_patch.start()
        self.addCleanup(self.capability_patch.stop)
        db_service.init_db()
        main.reminders.clear()
        self.client = TestClient(main.api)

    def reminder_enabled_competition(self, competition_key):
        competition = competition_service.get_competition(competition_key)
        if competition and competition.get("status") == "active":
            competition["supports_reminders"] = True
        return competition


    def body(
        self,
        competition_key="premier_league",
        season_key="2026-2027",
        match_id="mp_match_1",
    ):
        return {
            "telegram_id": 100,
            "competition_key": competition_key,
            "season_key": season_key,
            "match_id": match_id,
        }

    def post_with_match(self, match, **body_overrides):
        with patch("reminder_service.get_match_for_season", return_value=match):
            return self.client.post(
                "/reminder",
                json={**self.body(), **body_overrides},
            )

    def stored_rows(self):
        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn.execute(
            """
            SELECT competition_key, season_key, match_id, match_data, notified
            FROM reminders ORDER BY competition_key, season_key
            """
        ).fetchall()

    def test_ambiguous_identity_bodies_fail_before_provider_and_storage(self):
        with (
            patch("reminder_service.get_match_for_season") as get_match,
            patch("main.save_reminder_to_db") as save_reminder,
        ):
            scoped_integer = self.client.post(
                "/reminder",
                json=self.body(match_id=96),
            )
            partial_scope = self.client.post(
                "/reminder",
                json={
                    "telegram_id": 100,
                    "competition_key": "premier_league",
                    "match_id": "mp_match_1",
                },
            )
            legacy_string = self.client.post(
                "/reminder",
                json={
                    "telegram_id": 100,
                    "match_id": "96",
                },
            )

        self.assertEqual(scoped_integer.status_code, 422)
        self.assertEqual(partial_scope.status_code, 422)
        self.assertEqual(legacy_string.status_code, 422)
        get_match.assert_not_called()
        save_reminder.assert_not_called()


    def test_generic_create_is_idempotent_and_stores_server_snapshot(self):
        untrusted_body = {
            **self.body(),
            "home_team": "Client Home",
            "kickoff_utc": "2000-01-01T00:00:00Z",
        }
        with patch(
            "reminder_service.get_match_for_season",
            return_value=FUTURE_MATCH,
        ):
            first = self.client.post("/reminder", json=untrusted_body)
            duplicate = self.client.post("/reminder", json=untrusted_body)

        self.assertEqual(first.status_code, 200)
        self.assertIs(first.json()["created"], True)
        self.assertIs(duplicate.json()["created"], False)
        self.assertEqual(first.json()["reminders"][0]["match_id"], "mp_match_1")
        self.assertEqual(
            first.json()["reminders"][0]["competition_key"],
            "premier_league",
        )
        self.assertEqual(first.json()["reminders"][0]["season_key"], "2026-2027")
        self.assertIs(first.json()["reminders"][0]["notified"], False)

        rows = self.stored_rows()
        self.assertEqual(len(rows), 1)
        stored_snapshot = json.loads(rows[0][3])
        self.assertEqual(stored_snapshot["home_team"], "Server Home")
        self.assertEqual(stored_snapshot["kickoff_utc"], FUTURE_MATCH["kickoff_utc"])
        self.assertNotEqual(stored_snapshot["home_team"], untrusted_body["home_team"])

    def test_same_match_identity_is_isolated_by_competition_and_season(self):
        with (
            patch(
                "reminder_service.get_match_for_season",
                return_value=FUTURE_MATCH,
            ),
            patch(
                "reminder_service.get_season",
                side_effect=lambda competition_key, season_key: {
                    "competition_key": competition_key,
                    "season_key": season_key,
                },
            ),
        ):
            responses = [
                self.client.post("/reminder", json=self.body()),
                self.client.post(
                    "/reminder",
                    json=self.body(competition_key="la_liga"),
                ),
                self.client.post(
                    "/reminder",
                    json=self.body(season_key="2027-2028"),
                ),
            ]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertTrue(all(response.json()["created"] for response in responses))
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in self.stored_rows()],
            [
                ("la_liga", "2026-2027", "mp_match_1"),
                ("premier_league", "2026-2027", "mp_match_1"),
                ("premier_league", "2027-2028", "mp_match_1"),
            ],
        )

    def test_unknown_competition_season_and_match_return_404_without_storage(self):
        with (
            patch("reminder_service.get_match_for_season") as get_match,
            patch("main.save_reminder_to_db") as save_reminder,
        ):
            unknown_competition = self.client.post(
                "/reminder",
                json=self.body(competition_key="unknown"),
            )
            unknown_season = self.client.post(
                "/reminder",
                json=self.body(season_key="unknown"),
            )
            get_match.return_value = None
            unknown_match = self.client.post("/reminder", json=self.body())

        self.assertEqual(unknown_competition.status_code, 404)
        self.assertEqual(unknown_competition.json(), {"detail": "Competition not found"})
        self.assertEqual(unknown_season.status_code, 404)
        self.assertEqual(unknown_season.json(), {"detail": "Season not found"})
        self.assertEqual(unknown_match.status_code, 404)
        self.assertEqual(unknown_match.json(), {"detail": "Match not found"})
        get_match.assert_called_once()
        save_reminder.assert_not_called()

    def test_unsupported_capability_is_rejected_before_provider_and_storage(self):
        unsupported = {
            "competition_key": "future_cup",
            "status": "active",
            "is_active": True,
            "supports_reminders": False,
        }
        with (
            patch("reminder_service.get_competition", return_value=unsupported),
            patch(
                "reminder_service.get_season",
                return_value={
                    "competition_key": "future_cup",
                    "season_key": "2026",
                },
            ),
            patch("reminder_service.get_match_for_season") as get_match,
            patch("main.save_reminder_to_db") as save_reminder,
        ):
            response = self.client.post(
                "/reminder",
                json=self.body(
                    competition_key="future_cup",
                    season_key="2026",
                ),
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(
            response.json(),
            {"detail": "Competition reminders not supported"},
        )
        get_match.assert_not_called()
        save_reminder.assert_not_called()

    def test_provider_failure_is_sanitized(self):
        with patch(
            "reminder_service.get_match_for_season",
            side_effect=competition_data_service.CompetitionDataProviderError(
                "private provider details"
            ),
        ):
            response = self.client.post("/reminder", json=self.body())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Matches provider unavailable"})
        self.assertNotIn("private provider details", response.text)

    def test_storage_failures_are_sanitized_as_503(self):
        storage_error = sqlite3.OperationalError("private storage details")
        with (
            patch(
                "reminder_service.get_match_for_season",
                return_value=FUTURE_MATCH,
            ),
            patch("main.save_reminder_to_db", side_effect=storage_error),
        ):
            create = self.client.post("/reminder", json=self.body())
        with patch("main.get_reminders_from_db", side_effect=storage_error):
            read = self.client.get("/reminders/100")
        with patch("main.delete_reminder_from_db", side_effect=storage_error):
            delete = self.client.request(
                "DELETE",
                "/reminder",
                json=self.body(),
            )

        for response in (create, read, delete):
            with self.subTest(method=response.request.method):
                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.json(),
                    {"detail": "Reminder storage unavailable"},
                )
                self.assertNotIn("private storage details", response.text)

    def test_ineligible_statuses_are_rejected(self):
        cases = {
            "live": {**FUTURE_MATCH, "status": "live", "is_live": True},
            "finished": {
                **FUTURE_MATCH,
                "status": "finished",
                "is_finished": True,
            },
        }
        for label, match in cases.items():
            with self.subTest(label=label):
                response = self.post_with_match(match)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json(), {"detail": "Match is not upcoming"})

    def test_ineligible_kickoffs_are_rejected(self):
        cases = {
            "missing": {**FUTURE_MATCH, "kickoff_utc": None},
            "invalid": {**FUTURE_MATCH, "kickoff_utc": "not-a-date"},
            "naive": {**FUTURE_MATCH, "kickoff_utc": "2099-09-01T12:00:00"},
            "non_utc": {
                **FUTURE_MATCH,
                "kickoff_utc": "2099-09-01T15:30:00+03:30",
            },
            "malformed_offset": {
                **FUTURE_MATCH,
                "kickoff_utc": "2099-09-01T12:00:00+99:99",
            },
            "past": {**FUTURE_MATCH, "kickoff_utc": "2000-01-01T00:00:00Z"},
        }
        for label, match in cases.items():
            with self.subTest(label=label):
                response = self.post_with_match(match)
                self.assertEqual(response.status_code, 409)

    def test_kickoff_equal_to_now_is_rejected(self):
        now = datetime(2099, 9, 1, 12, 0, tzinfo=timezone.utc)
        with self.assertRaisesRegex(
            ReminderEligibilityError,
            "not in the future",
        ):
            validate_reminder_eligibility(
                FUTURE_MATCH,
                now=now,
            )

    def test_future_match_outside_prediction_scope_remains_eligible(self):
        outside_scope = {
            **FUTURE_MATCH,
            "round": "Week 99",
            "stage": "Later provider stage",
        }
        with (
            patch(
                "reminder_service.get_match_for_season",
                return_value=outside_scope,
            ),
            patch("main.select_prediction_scope_matches") as select_scope,
        ):
            response = self.client.post("/reminder", json=self.body())

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["created"], True)
        select_scope.assert_not_called()

    def test_exact_scoped_delete_is_idempotent(self):
        with patch(
            "reminder_service.get_match_for_season",
            return_value=FUTURE_MATCH,
        ):
            self.client.post("/reminder", json=self.body())
            self.client.post(
                "/reminder",
                json=self.body(competition_key="la_liga"),
            )

        first = self.client.request("DELETE", "/reminder", json=self.body())
        repeated = self.client.request("DELETE", "/reminder", json=self.body())

        self.assertIs(first.json()["deleted"], True)
        self.assertIs(repeated.json()["deleted"], False)
        rows = self.stored_rows()
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in rows],
            [("la_liga", "2026-2027", "mp_match_1")],
        )

    def test_competition_directory_advertises_reminders_only_for_enabled_competitions(self):
        response = self.client.get("/competitions")
        self.assertEqual(response.status_code, 200)
        competitions = {
            item["competition_key"]: item
            for item in response.json()["competitions"]
        }
        active_keys = {
            "premier_league",
            "persian_gulf_pro_league",
            "la_liga",
            "serie_a",
            "bundesliga",
            "ligue_1",
            "champions_league",
            "europa_league",
        }
        for competition_key in active_keys:
            with self.subTest(competition_key=competition_key):
                self.assertIs(
                    competitions[competition_key]["supports_reminders"],
                    True,
                )
        self.assertIs(competitions["worldcup2026"]["supports_reminders"], False)
        future_default = competition_service.validated_competition(
            {
                "competition_key": "future_league",
                "format": "league",
                "is_active": True,
                "supports_predictions": False,
            }
        )
        self.assertIs(future_default["supports_reminders"], False)


if __name__ == "__main__":
    unittest.main()
