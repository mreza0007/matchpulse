import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import aggregate_match_service
import main


COMPETITIONS = [
    {
        "competition_key": "worldcup2026",
        "name_en": "World Cup 2026",
        "name_fa": "جام جهانی ۲۰۲۶",
        "type": "international",
        "is_active": True,
        "supports_matches": True,
    },
    {
        "competition_key": "premier_league",
        "name_en": "Premier League",
        "name_fa": "لیگ برتر انگلیس",
        "type": "club",
        "is_active": True,
        "supports_matches": True,
    },
]

SEASONS = {
    "worldcup2026": {"competition_key": "worldcup2026", "season_key": "2026"},
    "premier_league": {"competition_key": "premier_league", "season_key": "2026-2027"},
}


class AggregateMatchServiceTests(unittest.TestCase):
    def aggregate(self, matches_by_competition, competitions=None):
        def get_matches(competition_key, season_key, status="all"):
            self.assertEqual(status, "all")
            self.assertEqual(season_key, SEASONS[competition_key]["season_key"])
            value = matches_by_competition[competition_key]
            if isinstance(value, Exception):
                raise value
            return value

        with (
            patch.object(aggregate_match_service, "get_competitions", return_value=competitions or COMPETITIONS),
            patch.object(aggregate_match_service, "get_default_season", side_effect=lambda key: SEASONS.get(key)),
            patch.object(aggregate_match_service, "get_matches_for_season", side_effect=get_matches),
        ):
            return aggregate_match_service.aggregate_matches_by_date("2026-08-16")

    def test_valid_date_aggregates_multiple_competitions(self):
        result = self.aggregate({
            "worldcup2026": [{"id": 1, "date_key": "2026-08-16", "time_iran": "20:00"}],
            "premier_league": [{"id": "pl-1", "kickoff_utc": "2026-08-15T21:00:00Z"}],
        })

        self.assertEqual(result["date"], "2026-08-16")
        self.assertEqual([group["competition"]["key"] for group in result["groups"]], [
            "worldcup2026", "premier_league",
        ])
        self.assertEqual(result["errors"], [])

    def test_only_requested_date_matches_are_returned(self):
        result = self.aggregate({
            "worldcup2026": [
                {"id": 1, "date_key": "2026-08-16"},
                {"id": 2, "date_key": "2026-08-17"},
            ],
            "premier_league": [
                {"id": "pl-1", "kickoff_utc": "2026-08-15T21:00:00Z"},
                {"id": "pl-2", "kickoff_utc": "2026-08-16T21:00:00Z"},
            ],
        })

        self.assertEqual([[match["id"] for match in group["matches"]] for group in result["groups"]], [
            [1], ["pl-1"],
        ])

    def test_empty_date_returns_no_groups(self):
        result = self.aggregate({"worldcup2026": [], "premier_league": []})
        self.assertEqual(result["groups"], [])
        self.assertEqual(result["errors"], [])

    def test_one_competition_failure_does_not_suppress_another(self):
        result = self.aggregate({
            "worldcup2026": [{"id": 1, "date_key": "2026-08-16"}],
            "premier_league": RuntimeError("provider secret"),
        })

        self.assertEqual([group["competition"]["key"] for group in result["groups"]], ["worldcup2026"])
        self.assertEqual(result["errors"], [{
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "code": "provider_failure",
            "message": "Matches could not be loaded for this competition.",
        }])
        self.assertNotIn("secret", str(result["errors"]))

    def test_competition_order_follows_registry(self):
        reversed_registry = list(reversed(COMPETITIONS))
        result = self.aggregate({
            "worldcup2026": [{"id": 1, "date_key": "2026-08-16"}],
            "premier_league": [{"id": "pl-1", "kickoff_utc": "2026-08-16T01:00:00+00:00"}],
        }, competitions=reversed_registry)

        self.assertEqual([group["competition"]["key"] for group in result["groups"]], [
            "premier_league", "worldcup2026",
        ])

    def test_match_order_is_chronological_with_stable_unknown_fallback(self):
        result = self.aggregate({
            "worldcup2026": [
                {"id": "unknown-1", "date_key": "2026-08-16", "time_iran": "TBD"},
                {"id": "late", "date_key": "2026-08-16", "time_iran": "20:30"},
                {"id": "early", "date_key": "2026-08-16", "time_iran": "08:15"},
                {"id": "unknown-2", "date_key": "2026-08-16", "time_iran": ""},
            ],
            "premier_league": [],
        })

        self.assertEqual([match["id"] for match in result["groups"][0]["matches"]], [
            "early", "late", "unknown-1", "unknown-2",
        ])

    def test_null_or_naive_kickoff_is_not_assigned_to_a_guessed_date(self):
        result = self.aggregate({
            "worldcup2026": [],
            "premier_league": [
                {"id": "null", "kickoff_utc": None, "date_fa": "2026-08-16"},
                {"id": "naive", "kickoff_utc": "2026-08-16T20:00:00"},
                {"id": "aware", "kickoff_utc": "2026-08-16T12:00:00Z"},
            ],
        })

        self.assertEqual([match["id"] for match in result["groups"][0]["matches"]], ["aware"])


class AggregateMatchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def test_invalid_date_returns_422(self):
        for invalid_date in ("2026-02-30", "2026-8-16", "not-a-date"):
            with self.subTest(invalid_date=invalid_date):
                response = self.client.get(f"/matches/by-date?date={invalid_date}")
                self.assertEqual(response.status_code, 422)

    def test_legacy_matches_route_is_unchanged(self):
        matches = [{"id": 75}]
        with patch("main.get_real_matches", return_value=matches) as legacy:
            response = self.client.get("/matches?status=live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 1, "status": "live", "matches": matches})
        legacy.assert_called_once_with(status="live")

    def test_scoped_premier_league_route_is_unchanged(self):
        matches = [{"id": "mp_match_1"}]
        with patch("main.get_matches_for_season", return_value=matches) as scoped:
            response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/matches?status=all"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 1, "status": "all", "matches": matches})
        scoped.assert_called_once_with("premier_league", "2026-2027", status="all")


if __name__ == "__main__":
    unittest.main()
