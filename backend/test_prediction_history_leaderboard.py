import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import competition_data_service
import db_service
import main


def finished_match(match_id, result=None, **extra):
    match = {
        "id": match_id,
        "status": "finished",
        "is_finished": True,
        **extra,
    }
    if result is not None:
        match["result"] = result
    return match


class PredictionHistoryLeaderboardTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "predictions.sqlite"
        self.db_patch = patch.object(db_service, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        db_service.init_db()
        self.client = TestClient(main.api)

    def add_user(self, telegram_id, first_name="", last_name="", username=""):
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            """
            INSERT INTO users (telegram_id, first_name, last_name, username, language_code)
            VALUES (?, ?, ?, ?, 'en')
            """,
            (telegram_id, first_name, last_name, username),
        )
        connection.commit()
        connection.close()

    def save_result(self, telegram_id, competition, season, match_id, result):
        db_service.save_prediction_v2(
            telegram_id, competition, season, match_id, "result", result
        )

    def save_exact(self, telegram_id, competition, season, match_id, home, away):
        db_service.save_prediction_v2(
            telegram_id, competition, season, match_id, "exact_score", None, home, away
        )

    def test_history_returns_result_and_exact_score_with_shared_evaluation(self):
        self.save_result(10, "worldcup2026", "2026", "result-id", "home")
        self.save_exact(10, "premier_league", "2026-2027", "exact-id", 2, 1)
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            "UPDATE predictions SET updated_at = '2026-01-01 00:00:00' WHERE match_id = 'result-id'"
        )
        connection.execute(
            "UPDATE predictions SET updated_at = '2026-02-01 00:00:00' WHERE match_id = 'exact-id'"
        )
        connection.commit()
        connection.close()
        matches = {
            ("worldcup2026", "2026", "result-id"): finished_match("result-id", "away"),
            ("premier_league", "2026-2027", "exact-id"): finished_match(
                "exact-id", "home"
            ),
        }

        with patch("main.get_match_for_season", side_effect=lambda *identity: matches[identity]):
            response = self.client.get("/prediction-history/10")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["match_id"] for item in payload["history"]], ["exact-id", "result-id"])
        exact, result = payload["history"]
        self.assertEqual((exact["prediction_type"], exact["home_score"], exact["away_score"]), ("exact_score", 2, 1))
        self.assertEqual(exact["evaluation"], {"status": "correct", "points": 3})
        self.assertEqual(result["prediction_type"], "result")
        self.assertEqual(result["evaluation"], {"status": "wrong", "points": 0})
        self.assertIsNone(exact["points_awarded"])
        self.assertNotIn("telegram_id", response.text)

    def test_history_filters_empty_and_invalid_scopes(self):
        self.save_result(10, "worldcup2026", "2026", "wc", "home")
        self.save_result(10, "premier_league", "2026-2027", "pl", "draw")

        with patch("main.get_match_for_season", return_value=None):
            worldcup = self.client.get(
                "/prediction-history/10?competition_key=worldcup2026"
            )
            season = self.client.get("/prediction-history/10?season_key=2026-2027")
            empty = self.client.get("/prediction-history/999")

        self.assertEqual([item["match_id"] for item in worldcup.json()["history"]], ["wc"])
        self.assertEqual([item["match_id"] for item in season.json()["history"]], ["pl"])
        self.assertEqual(empty.json(), {"count": 0, "evaluation_errors": 0, "history": []})
        self.assertEqual(
            self.client.get("/prediction-history/10?competition_key=unknown").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/prediction-history/10?competition_key=worldcup2026&season_key=unknown"
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get("/prediction-history/0").status_code, 400)

    def test_unknown_and_provider_failure_remain_pending_not_wrong(self):
        self.save_result(10, "worldcup2026", "2026", "unknown", "home")
        self.save_result(10, "worldcup2026", "2026", "failed", "away")

        def resolve(_competition, _season, match_id):
            if match_id == "failed":
                raise competition_data_service.CompetitionDataProviderError("private")
            return None

        with patch("main.get_match_for_season", side_effect=resolve):
            response = self.client.get("/prediction-history/10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["evaluation_errors"], 1)
        self.assertEqual(
            {item["match_id"]: item["evaluation"]["status"] for item in response.json()["history"]},
            {"unknown": "pending", "failed": "pending"},
        )
        self.assertNotIn("private", response.text)

    def test_exact_score_is_outcome_only_and_penalty_behavior_is_preserved(self):
        self.save_exact(10, "premier_league", "2026-2027", "exact", 5, 1)
        self.save_result(10, "worldcup2026", "2026", "penalty", "away")
        matches = {
            ("premier_league", "2026-2027", "exact"): finished_match("exact", "home"),
            ("worldcup2026", "2026", "penalty"): finished_match(
                "penalty", None, penalty_winner_side="away"
            ),
        }

        with patch("main.get_match_for_season", side_effect=lambda *identity: matches[identity]):
            response = self.client.get("/prediction-history/10")

        evaluations = {
            item["match_id"]: item["evaluation"] for item in response.json()["history"]
        }
        self.assertEqual(evaluations["exact"], {"status": "correct", "points": 3})
        self.assertEqual(evaluations["penalty"], {"status": "correct", "points": 3})

    def test_leaderboard_aggregates_users_competitions_and_uses_dense_rank(self):
        self.add_user(1, username="alice")
        self.add_user(2, first_name="Bob", last_name="Builder")
        self.save_result(1, "worldcup2026", "2026", "shared", "home")
        self.save_result(1, "premier_league", "2026-2027", "pl-wrong", "away")
        self.save_result(2, "worldcup2026", "2026", "shared", "home")
        self.save_result(2, "premier_league", "2026-2027", "pl-wrong", "away")
        self.save_result(3, "worldcup2026", "2026", "pending", "draw")
        matches = {
            ("worldcup2026", "2026", "shared"): finished_match("shared", "home"),
            ("premier_league", "2026-2027", "pl-wrong"): finished_match("pl-wrong", "home"),
            ("worldcup2026", "2026", "pending"): None,
        }
        resolver = Mock(side_effect=lambda *identity: matches[identity])

        with patch("main.get_match_for_season", resolver):
            response = self.client.get("/prediction-leaderboard")

        self.assertEqual(response.status_code, 200)
        entries = response.json()["leaderboard"]
        by_name = {entry["display_name"]: entry for entry in entries}
        self.assertEqual(by_name["@alice"]["rank"], 1)
        self.assertEqual(by_name["Bob B."]["rank"], 1)
        self.assertEqual(by_name["@alice"]["points"], 3)
        self.assertEqual(by_name["@alice"]["wrong"], 1)
        self.assertEqual(by_name["Anonymous"]["rank"], 2)
        self.assertEqual(resolver.call_count, 3)
        self.assertEqual(
            resolver.call_args_list.count(
                unittest.mock.call("worldcup2026", "2026", "shared")
            ),
            1,
        )
        self.assertNotIn("telegram_id", response.text)

    def test_leaderboard_filters_and_valid_empty_response(self):
        self.add_user(1, username="alice")
        self.save_result(1, "worldcup2026", "2026", "wc", "home")
        self.save_result(1, "premier_league", "2026-2027", "pl", "home")
        resolver = lambda competition, _season, match_id: finished_match(
            match_id, "home" if competition == "worldcup2026" else "away"
        )

        with patch("main.get_match_for_season", side_effect=resolver):
            worldcup = self.client.get(
                "/prediction-leaderboard?competition_key=worldcup2026"
            )
            season = self.client.get(
                "/prediction-leaderboard?season_key=2026-2027"
            )
            empty = self.client.get(
                "/prediction-leaderboard?competition_key=worldcup2026&season_key=2026"
            )

        self.assertEqual(worldcup.json()["leaderboard"][0]["points"], 3)
        self.assertEqual(worldcup.json()["leaderboard"][0]["total"], 1)
        self.assertEqual(season.json()["leaderboard"][0]["wrong"], 1)

        connection = sqlite3.connect(self.db_path)
        connection.execute("DELETE FROM predictions")
        connection.commit()
        connection.close()
        empty = self.client.get("/prediction-leaderboard")
        self.assertEqual(
            empty.json(), {"count": 0, "evaluation_errors": 0, "leaderboard": []}
        )
        self.assertEqual(
            self.client.get("/prediction-leaderboard?competition_key=unknown").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/prediction-leaderboard?competition_key=premier_league&season_key=unknown"
            ).status_code,
            404,
        )

    def test_leaderboard_provider_failure_is_partial_and_not_wrong(self):
        self.add_user(1, username="alice")
        self.save_result(1, "worldcup2026", "2026", "good", "home")
        self.save_result(1, "premier_league", "2026-2027", "failed", "away")

        def resolve(_competition, _season, match_id):
            if match_id == "failed":
                raise competition_data_service.CompetitionDataProviderError("secret")
            return finished_match(match_id, "home")

        with patch("main.get_match_for_season", side_effect=resolve):
            response = self.client.get("/prediction-leaderboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["evaluation_errors"], 1)
        entry = response.json()["leaderboard"][0]
        self.assertEqual(
            {key: entry[key] for key in ("points", "correct", "wrong", "pending", "total")},
            {"points": 3, "correct": 1, "wrong": 0, "pending": 1, "total": 2},
        )
        self.assertNotIn("secret", response.text)


if __name__ == "__main__":
    unittest.main()
