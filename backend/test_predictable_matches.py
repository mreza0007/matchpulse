import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import competition_data_service
import main
from competition_service import get_competition
from prediction_service import prediction_is_locked, prediction_is_predictable
from services import generic_football_adapter


def match_fixture(match_id, **overrides):
    match = {
        "id": match_id,
        "competition_key": "worldcup2026",
        "season_key": "2026",
        "home_en": "Home team",
        "away_en": "Away team",
        "status": "upcoming",
        "is_upcoming": True,
        "is_live": False,
        "is_finished": False,
        "kickoff_ts": time.time() + 3600,
    }
    match.update(overrides)
    return match


class PredictableMatchesRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def test_worldcup_route_includes_only_eligible_matches_and_preserves_order(self):
        first = match_fixture("second-in-time", marker={"source": "unchanged"})
        second = match_fixture("first-in-time", kickoff_ts=time.time() + 1800)
        excluded = [
            match_fixture("live", status="live", is_upcoming=False, is_live=True),
            match_fixture("finished", status="finished", is_upcoming=False, is_finished=True),
            match_fixture("missing-kickoff", kickoff_ts=None),
            match_fixture("invalid-kickoff", kickoff_ts="invalid"),
            match_fixture(
                "naive-kickoff",
                kickoff_ts=None,
                kickoff_utc="2026-09-01T12:00:00",
            ),
            match_fixture("past", kickoff_ts=time.time() - 1),
            match_fixture("missing-id", id=None),
            match_fixture("missing-home", home_en=""),
            match_fixture("placeholder-away", away_en="TBD"),
        ]

        with patch(
            "main.get_prediction_matches_for_season",
            return_value=[first, *excluded, second],
        ):
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/predictable-matches"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["competition_key"], "worldcup2026")
        self.assertEqual(payload["season_key"], "2026")
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            [match["id"] for match in payload["matches"]],
            ["second-in-time", "first-in-time"],
        )
        self.assertEqual(payload["matches"][0], first)

    def test_timezone_aware_kickoff_is_accepted(self):
        match = match_fixture(
            "aware",
            kickoff_ts=None,
            kickoff_utc="2099-01-01T12:00:00Z",
        )
        with patch("main.get_prediction_matches_for_season", return_value=[match]):
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/predictable-matches"
            )
        self.assertEqual(response.json()["matches"], [match])

    def test_valid_supported_competition_can_return_empty_list(self):
        with patch("main.get_prediction_matches_for_season", return_value=[]):
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/predictable-matches"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "competition_key": "worldcup2026",
                "season_key": "2026",
                "count": 0,
                "matches": [],
            },
        )

    def test_scope_errors_and_disabled_premier_league_do_not_call_provider(self):
        cases = [
            (
                "/competitions/unknown/seasons/2026/predictable-matches",
                404,
                "Competition not found",
            ),
            (
                "/competitions/worldcup2026/seasons/unknown/predictable-matches",
                404,
                "Season not found",
            ),
            (
                "/competitions/premier_league/seasons/2026-2027/predictable-matches",
                501,
                "Competition predictions not supported",
            ),
        ]
        with patch("main.get_prediction_matches_for_season") as provider:
            for path, status, detail in cases:
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.json(), {"detail": detail})
        provider.assert_not_called()

    def test_provider_failure_is_sanitized(self):
        with patch(
            "main.get_prediction_matches_for_season",
            side_effect=competition_data_service.CompetitionDataProviderError(
                "private provider detail"
            ),
        ):
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/predictable-matches"
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(), {"detail": "Prediction match provider unavailable"}
        )
        self.assertNotIn("private provider detail", response.text)

    def test_route_and_post_share_the_same_eligibility_decision(self):
        fixtures = [
            match_fixture("future"),
            match_fixture("past", kickoff_ts=time.time() - 1),
            match_fixture("live", status="live", is_upcoming=False, is_live=True),
            match_fixture("missing-away", away_en=""),
        ]
        for match in fixtures:
            with self.subTest(match=match["id"]):
                self.assertEqual(
                    prediction_is_predictable(match),
                    not prediction_is_locked(match),
                )
                self.assertIs(main.prediction_is_locked, prediction_is_locked)


class PremierLeagueReadinessTests(unittest.TestCase):
    def test_premier_league_remains_prediction_disabled(self):
        self.assertIs(get_competition("premier_league")["supports_predictions"], False)

    def test_generic_finished_match_has_scores_but_no_canonical_result_contract(self):
        match = generic_football_adapter.normalize_match(
            {
                "id": "generic-finished",
                "competition_key": "premier_league",
                "season_key": "2026-2027",
                "status": "finished",
                "kickoff_utc": "2026-08-01T12:00:00Z",
                "home_name_fa": "تیم میزبان",
                "away_name_fa": "تیم مهمان",
                "home_score": 2,
                "away_score": 1,
            }
        )

        self.assertTrue(match["is_finished"])
        self.assertEqual(match["score"], {"home": 2, "away": 1})
        self.assertNotIn("result", match)
        self.assertNotIn("score_source", match)

    def test_generic_empty_and_provider_failure_are_currently_indistinguishable(self):
        with patch("services.generic_football_adapter.fetch_json", return_value=None):
            provider_failure = generic_football_adapter.get_season_matches(
                "premier_league", "2026-2027"
            )
        with patch(
            "services.generic_football_adapter.fetch_json",
            return_value={"matches": []},
        ):
            valid_empty = generic_football_adapter.get_season_matches(
                "premier_league", "2026-2027"
            )

        self.assertEqual(provider_failure, [])
        self.assertEqual(valid_empty, [])


if __name__ == "__main__":
    unittest.main()
