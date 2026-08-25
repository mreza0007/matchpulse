import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from competition_service import get_competition, get_competitions


ACTIVE_COMPETITION_KEYS = {
    "premier_league",
    "persian_gulf_pro_league",
    "la_liga",
    "serie_a",
    "bundesliga",
    "ligue_1",
    "champions_league",
    "europa_league",
}


class WorldCupArchivalMetadataTests(unittest.TestCase):
    def test_worldcup_remains_listed_as_archive_without_new_mutation_capabilities(self):
        competitions = {
            competition["competition_key"]: competition
            for competition in get_competitions()
        }

        worldcup = competitions["worldcup2026"]
        self.assertEqual(worldcup["status"], "archived")
        self.assertIs(worldcup["is_active"], False)
        self.assertIs(worldcup["supports_archive"], True)
        self.assertIs(worldcup["supports_predictions"], False)
        self.assertIs(worldcup["supports_reminders"], False)
        self.assertIs(worldcup["supports_favorites"], False)
        self.assertIs(worldcup["supports_prediction_history"], True)

    def test_active_competition_capabilities_remain_enabled(self):
        for competition_key in ACTIVE_COMPETITION_KEYS:
            with self.subTest(competition_key=competition_key):
                competition = get_competition(competition_key)
                self.assertEqual(competition["status"], "active")
                self.assertIs(competition["is_active"], True)
                self.assertIs(competition["supports_predictions"], True)
                self.assertIs(competition["supports_favorites"], True)


class WorldCupArchivalMutationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.api)

    def test_new_worldcup_favorite_is_rejected_before_resolution_or_storage(self):
        with (
            patch("main.resolve_favorite_team") as resolve_team,
            patch("main.save_favorite_team_v2_to_db") as save_favorite,
        ):
            response = self.client.post(
                "/favorite-team",
                json={
                    "telegram_id": 100,
                    "competition_key": "worldcup2026",
                    "team_id": "6",
                },
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(
            response.json(),
            {"detail": "Competition favorites not supported"},
        )
        resolve_team.assert_not_called()
        save_favorite.assert_not_called()

    def test_new_worldcup_reminder_is_rejected_without_touching_storage(self):
        with (
            patch("main.get_real_matches") as get_matches,
            patch("main.save_reminder_to_db") as save_reminder,
        ):
            response = self.client.post(
                "/reminder",
                json={"telegram_id": 100, "match_id": 1},
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(
            response.json(),
            {"detail": "Competition reminders not supported"},
        )
        get_matches.assert_not_called()
        save_reminder.assert_not_called()

    def test_historical_worldcup_reminders_are_still_returned_from_storage(self):
        stored_reminders = [
            {
                "id": 1,
                "competition_key": "worldcup2026",
                "home_team": "Iran",
                "away_team": "England",
            }
        ]
        with patch("main.get_reminders_from_db", return_value=stored_reminders) as get_reminders:
            response = self.client.get("/reminders/100")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reminders"], stored_reminders)
        get_reminders.assert_called_once_with(100)

    def test_historical_worldcup_reminders_are_still_deletable(self):
        with (
            patch("main.delete_reminder_from_db", return_value=True) as delete_reminder,
            patch("main.get_reminders_from_db", return_value=[]) as get_reminders,
        ):
            response = self.client.request(
                "DELETE",
                "/reminder",
                json={"telegram_id": 100, "match_id": 1},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["deleted"], True)
        self.assertEqual(response.json()["reminders"], [])
        delete_reminder.assert_called_once_with(100, 1)
        get_reminders.assert_called_once_with(100)

    def test_new_worldcup_prediction_is_rejected_before_match_lookup(self):
        with patch("main.get_match_for_season") as get_match:
            response = self.client.post(
                "/prediction",
                json={
                    "telegram_id": 100,
                    "competition_key": "worldcup2026",
                    "season_key": "2026",
                    "match_id": "1",
                    "prediction_type": "result",
                    "predicted_result": "home",
                },
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(
            response.json(),
            {"detail": "Competition predictions not supported"},
        )
        get_match.assert_not_called()

    def test_historical_worldcup_favorites_are_still_returned_from_storage(self):
        stored_payload = {
            "count": 1,
            "resolution_errors": 0,
            "unresolved_count": 0,
            "favorite_teams": [
                {
                    "competition_key": "worldcup2026",
                    "team_id": "6",
                    "team_type": "national",
                }
            ],
        }
        with patch("main.favorite_list_payload", return_value=stored_payload):
            response = self.client.get("/favorite-teams/100")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["favorite_teams"], stored_payload["favorite_teams"])

    def test_historical_worldcup_predictions_remain_evaluable(self):
        self.assertIs(
            main.prediction_scope_supports_evaluation(
                {
                    "competition_key": "worldcup2026",
                    "season_key": "2026",
                }
            ),
            True,
        )


if __name__ == "__main__":
    unittest.main()
