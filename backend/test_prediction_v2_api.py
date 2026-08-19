import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import competition_data_service
import db_service
import main
from prediction_schema import ensure_prediction_v2_schema


def future_match(match_id="42"):
    return {
        "id": match_id,
        "status": "upcoming",
        "is_upcoming": True,
        "is_live": False,
        "is_finished": False,
        "kickoff_ts": time.time() + 3600,
    }


def finished_match(match_id, home_score, away_score, **extra):
    return {
        "id": match_id,
        "status": "finished",
        "is_finished": True,
        "home_score": home_score,
        "away_score": away_score,
        "score_source": "worldcup_wrapper",
        **extra,
    }


class PredictionV2ApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "predictions.sqlite"
        conn = sqlite3.connect(self.db_path)
        ensure_prediction_v2_schema(conn)
        conn.commit()
        conn.close()
        self.db_patch = patch.object(db_service, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.client = TestClient(main.api)

    def post_result(self, match_id="42", predicted_result="home"):
        return self.client.post(
            "/prediction",
            json={
                "telegram_id": 10,
                "competition_key": "worldcup2026",
                "season_key": "2026",
                "match_id": match_id,
                "prediction_type": "result",
                "predicted_result": predicted_result,
            },
        )

    def test_v2_result_prediction_saves_and_updates_logical_identity(self):
        with patch("main.get_match_for_season", return_value=future_match()):
            first = self.post_result(predicted_result="home")

        self.assertEqual(first.status_code, 200)
        item = first.json()["predictions"][0]
        self.assertEqual(item["competition_key"], "worldcup2026")
        self.assertEqual(item["season_key"], "2026")
        self.assertEqual(item["match_id"], "42")
        self.assertEqual(item["prediction_type"], "result")
        self.assertEqual(item["prediction"], "home")

        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE predictions SET created_at = '2020-01-01 00:00:00'")
        conn.commit()
        conn.close()
        with patch("main.get_match_for_season", return_value=future_match()):
            updated = self.post_result(predicted_result="away")

        self.assertEqual(updated.status_code, 200)
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT COUNT(*), predicted_result, created_at FROM predictions"
        ).fetchone()
        conn.close()
        self.assertEqual(row, (1, "away", "2020-01-01 00:00:00"))

    def test_exact_score_saves_and_derives_each_outcome(self):
        scores = [(2, 1, "home"), (1, 1, "draw"), (0, 3, "away")]
        for index, (home_score, away_score, expected) in enumerate(scores, start=1):
            with patch("main.get_match_for_season", return_value=future_match(str(index))):
                response = self.client.post(
                    "/prediction",
                    json={
                        "telegram_id": 10,
                        "competition_key": "worldcup2026",
                        "season_key": "2026",
                        "match_id": str(index),
                        "prediction_type": "exact_score",
                        "home_score": home_score,
                        "away_score": away_score,
                    },
                )
            self.assertEqual(response.status_code, 200)

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT predicted_result FROM predictions ORDER BY CAST(match_id AS INTEGER)"
        ).fetchall()
        conn.close()
        self.assertEqual([row[0] for row in rows], ["home", "draw", "away"])

    def test_invalid_prediction_shapes_are_rejected_before_resolution(self):
        bodies = [
            {
                "telegram_id": 10,
                "competition_key": "worldcup2026",
                "season_key": "2026",
                "match_id": "42",
                "prediction_type": "result",
                "predicted_result": "home",
                "home_score": 1,
            },
            {
                "telegram_id": 10,
                "competition_key": "worldcup2026",
                "season_key": "2026",
                "match_id": "42",
                "prediction_type": "exact_score",
                "home_score": -1,
                "away_score": 0,
            },
        ]
        with patch("main.get_match_for_season") as resolver:
            for body in bodies:
                with self.subTest(body=body):
                    self.assertEqual(self.client.post("/prediction", json=body).status_code, 400)
        resolver.assert_not_called()

    def test_legacy_numeric_body_maps_only_to_worldcup_scope(self):
        with patch("main.get_match_for_season", return_value=future_match()) as resolver:
            response = self.client.post(
                "/prediction",
                json={"telegram_id": 10, "match_id": 42, "prediction": "draw"},
            )

        self.assertEqual(response.status_code, 200)
        item = response.json()["predictions"][0]
        self.assertEqual(
            (item["competition_key"], item["season_key"], item["match_id"], item["prediction"]),
            ("worldcup2026", "2026", "42", "draw"),
        )
        resolver.assert_called_once_with("worldcup2026", "2026", "42")

        rejected = self.client.post(
            "/prediction",
            json={"telegram_id": 10, "match_id": "generic-id", "prediction": "home"},
        )
        self.assertEqual(rejected.status_code, 400)
        negative = self.client.post(
            "/prediction",
            json={"telegram_id": 10, "match_id": -1, "prediction": "home"},
        )
        self.assertEqual(negative.status_code, 400)

    def test_scope_and_match_errors_are_stable(self):
        cases = [
            ({"competition_key": "unknown", "season_key": "2026"}, 404, "Competition not found"),
            ({"competition_key": "worldcup2026", "season_key": "unknown"}, 404, "Season not found"),
            (
                {"competition_key": "premier_league", "season_key": "2026-2027"},
                501,
                "Competition predictions not supported",
            ),
        ]
        for scope, status, detail in cases:
            with self.subTest(scope=scope):
                body = {
                    "telegram_id": 10,
                    "match_id": "42",
                    "prediction_type": "result",
                    "predicted_result": "home",
                    **scope,
                }
                response = self.client.post("/prediction", json=body)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"detail": detail})

        with patch("main.get_match_for_season", return_value=None):
            response = self.post_result()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Match not found"})

    def test_provider_failure_is_sanitized(self):
        with patch(
            "main.get_match_for_season",
            side_effect=competition_data_service.CompetitionDataProviderError("private provider detail"),
        ):
            response = self.post_result()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Prediction match provider unavailable"})
        self.assertNotIn("private provider detail", response.text)

    def test_locking_rejects_unsafe_match_states_and_kickoffs(self):
        now = 1_000.0
        accepted = future_match()
        accepted["kickoff_ts"] = now + 1
        self.assertFalse(main.prediction_is_locked(accepted, now))

        locked = [
            {**accepted, "kickoff_ts": now},
            {**accepted, "kickoff_ts": now - 1},
            {**accepted, "is_live": True},
            {**accepted, "is_finished": True},
            {**accepted, "status": "unknown", "is_upcoming": False},
            {**accepted, "kickoff_ts": None},
            {**accepted, "kickoff_ts": "invalid"},
            {**accepted, "kickoff_ts": None, "kickoff_utc": "2026-08-19T12:00:00"},
        ]
        for match in locked:
            with self.subTest(match=match):
                self.assertTrue(main.prediction_is_locked(match, now))

    def test_get_predictions_returns_and_filters_v2_rows(self):
        db_service.save_prediction_v2(10, "worldcup2026", "2026", "42", "result", "home")
        db_service.save_prediction_v2(
            10, "premier_league", "2026-2027", "same-id", "exact_score", None, 1, 1
        )

        all_rows = self.client.get("/predictions/10")
        worldcup = self.client.get(
            "/predictions/10?competition_key=worldcup2026&season_key=2026"
        )
        league = self.client.get("/predictions/10?competition_key=premier_league")

        self.assertEqual(all_rows.json()["count"], 2)
        self.assertEqual(worldcup.json()["count"], 1)
        self.assertEqual(worldcup.json()["predictions"][0]["prediction"], "home")
        self.assertEqual(league.json()["predictions"][0]["match_id"], "same-id")
        self.assertNotIn("prediction", league.json()["predictions"][0])

        invalid_season = self.client.get("/predictions/10?season_key=unknown")
        self.assertEqual(invalid_season.status_code, 404)
        self.assertEqual(invalid_season.json(), {"detail": "Season not found"})

    def test_stats_preserve_outcome_scoring_exact_score_and_penalty_winner(self):
        db_service.save_prediction_v2(10, "worldcup2026", "2026", "correct", "result", "home")
        db_service.save_prediction_v2(10, "worldcup2026", "2026", "wrong", "result", "away")
        db_service.save_prediction_v2(
            10, "worldcup2026", "2026", "exact", "exact_score", None, 2, 1
        )
        db_service.save_prediction_v2(10, "worldcup2026", "2026", "penalty", "result", "away")
        db_service.save_prediction_v2(10, "worldcup2026", "2026", "missing", "result", "home")

        matches = {
            "correct": finished_match("correct", 1, 0),
            "wrong": finished_match("wrong", 1, 0),
            "exact": finished_match("exact", 4, 2),
            "penalty": finished_match(
                "penalty", 1, 1, score_source="untrusted", penalty_winner_side="away"
            ),
            "missing": None,
        }
        with patch("main.get_match_for_season", side_effect=lambda _c, _s, match_id: matches[match_id]):
            response = self.client.get("/prediction-stats/10")

        self.assertEqual(
            response.json(),
            {"points": 9, "correct": 3, "wrong": 1, "pending": 1, "total": 5},
        )
        conn = sqlite3.connect(self.db_path)
        persisted_scores = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE points_awarded IS NOT NULL OR evaluated_at IS NOT NULL"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(persisted_scores, 0)

    def test_stats_provider_failure_is_sanitized_without_mutation(self):
        db_service.save_prediction_v2(10, "worldcup2026", "2026", "42", "result", "home")
        with patch(
            "main.get_match_for_season",
            side_effect=competition_data_service.CompetitionDataProviderError("secret"),
        ):
            response = self.client.get("/prediction-stats/10")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret", response.text)

    def test_stats_leave_disabled_competition_prediction_pending_without_provider_call(self):
        db_service.save_prediction_v2(
            10, "premier_league", "2026-2027", "generic-id", "result", "home"
        )
        with patch("main.get_match_for_season") as resolver:
            response = self.client.get("/prediction-stats/10")

        self.assertEqual(
            response.json(),
            {"points": 0, "correct": 0, "wrong": 0, "pending": 1, "total": 1},
        )
        resolver.assert_not_called()


class PredictionDispatcherTests(unittest.TestCase):
    def test_match_resolution_uses_opaque_string_ids(self):
        matches = [{"id": "001"}, {"id": "generic-match-id"}]
        with patch("competition_data_service.get_matches_for_season", return_value=matches) as source:
            generic = competition_data_service.get_match_for_season(
                "premier_league", "2026-2027", "generic-match-id"
            )
            leading_zero = competition_data_service.get_match_for_season(
                "premier_league", "2026-2027", "001"
            )
            coerced = competition_data_service.get_match_for_season(
                "premier_league", "2026-2027", 1
            )

        self.assertEqual(generic["id"], "generic-match-id")
        self.assertEqual(leading_zero["id"], "001")
        self.assertIsNone(coerced)
        source.assert_called_with("premier_league", "2026-2027", status="all")


if __name__ == "__main__":
    unittest.main()
