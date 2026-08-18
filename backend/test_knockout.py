import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import competition_data_service
import main
from services import worldcup_adapter


KNOCKOUT_ROUNDS = [
    {
        "round_key": "qf",
        "matches": [
            {
                "id": 97,
                "stage": "qf",
                "home_en": "Spain",
                "away_en": "Brazil",
                "home_score": 1,
                "away_score": 1,
                "score": {"home": 1, "away": 1},
                "status": "finished",
                "home_penalty_score": 5,
                "away_penalty_score": 4,
                "penalty_winner_side": "home",
            },
            {
                "id": 99,
                "stage": "qf",
                "home_en": "France",
                "away_en": "Argentina",
                "home_score": 2,
                "away_score": 0,
                "score": {"home": 2, "away": 0},
                "status": "finished",
            },
        ],
    },
    {"round_key": "sf", "matches": [{"id": 101, "stage": "sf", "status": "upcoming"}]},
]


class KnockoutRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def test_worldcup_knockout_preserves_round_match_and_normalized_match_data(self):
        with patch("main.get_knockout_for_season", return_value=KNOCKOUT_ROUNDS) as get_knockout:
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/knockout"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["competition_key"], "worldcup2026")
        self.assertEqual(payload["season_key"], "2026")
        self.assertEqual([item["round_key"] for item in payload["rounds"]], ["qf", "sf"])
        self.assertEqual([item["id"] for item in payload["rounds"][0]["matches"]], [97, 99])
        first_match = payload["rounds"][0]["matches"][0]
        self.assertEqual(first_match["score"], {"home": 1, "away": 1})
        self.assertEqual(first_match["status"], "finished")
        self.assertEqual(first_match["home_penalty_score"], 5)
        self.assertEqual(first_match["away_penalty_score"], 4)
        self.assertEqual(first_match["penalty_winner_side"], "home")
        self.assertNotIn("slot", payload["rounds"][0])
        self.assertNotIn("feeds_to", payload["rounds"][0])
        get_knockout.assert_called_once_with("worldcup2026", "2026")

    def test_premier_league_does_not_fabricate_knockout(self):
        with patch("main.get_knockout_for_season") as get_knockout:
            response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/knockout"
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json(), {"detail": "Competition knockout not supported"})
        get_knockout.assert_not_called()

    def test_invalid_competition_and_season_keep_404_behavior(self):
        competition = self.client.get("/competitions/unknown/seasons/2026/knockout")
        season = self.client.get("/competitions/worldcup2026/seasons/unknown/knockout")

        self.assertEqual(competition.status_code, 404)
        self.assertEqual(competition.json(), {"detail": "Competition not found"})
        self.assertEqual(season.status_code, 404)
        self.assertEqual(season.json(), {"detail": "Season not found"})

    def test_provider_failure_is_sanitized(self):
        with patch(
            "main.get_knockout_for_season",
            side_effect=competition_data_service.CompetitionKnockoutProviderError(
                "private upstream detail"
            ),
        ):
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/knockout"
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Knockout provider unavailable"})
        self.assertNotIn("private upstream detail", response.text)

    def test_configured_source_unavailable_and_absent_are_distinct(self):
        with patch(
            "main.get_knockout_for_season",
            side_effect=competition_data_service.CompetitionKnockoutUnavailableError(),
        ):
            unavailable = self.client.get(
                "/competitions/worldcup2026/seasons/2026/knockout"
            )
        with patch("main.get_knockout_for_season", return_value=None):
            absent = self.client.get(
                "/competitions/worldcup2026/seasons/2026/knockout"
            )

        self.assertEqual(unavailable.status_code, 501)
        self.assertEqual(unavailable.json(), {"detail": "Competition knockout not available"})
        self.assertEqual(absent.status_code, 501)
        self.assertEqual(
            absent.json(),
            {"detail": "Competition knockout data source not configured"},
        )

    def test_groups_standings_and_legacy_worldcup_routes_are_unchanged(self):
        with (
            patch("main.get_groups_for_season", return_value=[{"group_key": "A", "standings": []}]),
            patch("main.get_standings_for_season", return_value=[{"rank": 1}]),
        ):
            groups = self.client.get("/competitions/worldcup2026/seasons/2026/groups")
            standings = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/standings"
            )

        self.assertEqual(groups.status_code, 200)
        self.assertEqual(groups.json()["groups"][0]["group_key"], "A")
        self.assertEqual(standings.status_code, 200)
        self.assertIs(main.get_events.__annotations__["match_id"], int)
        self.assertIs(main.get_match_live.__annotations__["match_id"], int)


class KnockoutSourceTests(unittest.TestCase):
    def test_source_stage_and_match_order_are_preserved_without_graph_linkage(self):
        matches = [
            {"id": 89, "stage": "r16", "status": "finished"},
            {"id": 90, "stage": "r16", "status": "finished"},
            {"id": 97, "stage": "qf", "status": "upcoming"},
            {"id": 103, "stage": "third", "status": "upcoming"},
            {"id": 104, "stage": "final", "status": "upcoming"},
        ]

        rounds = worldcup_adapter.build_knockout_rounds(matches)

        self.assertEqual(
            [item["round_key"] for item in rounds],
            ["r16", "qf", "third", "final"],
        )
        self.assertEqual([item["id"] for item in rounds[0]["matches"]], [89, 90])
        for round_item in rounds:
            self.assertNotIn("order", round_item)
            self.assertNotIn("slot", round_item)
            self.assertNotIn("feeds_to", round_item)

    def test_non_knockout_matches_are_not_treated_as_bracket_rounds(self):
        with self.assertRaises(worldcup_adapter.WorldCupKnockoutUnavailableError):
            worldcup_adapter.build_knockout_rounds(
                [{"id": 1, "stage": "group", "group": "A"}]
            )

    def test_empty_or_invalid_source_is_not_silently_accepted(self):
        with self.assertRaises(worldcup_adapter.WorldCupKnockoutProviderError):
            worldcup_adapter.build_knockout_rounds([])
        with self.assertRaises(worldcup_adapter.WorldCupKnockoutProviderError):
            worldcup_adapter.build_knockout_rounds([{"id": 73, "stage": "r32"}, None])

    def test_dispatcher_and_capability_are_worldcup_only(self):
        worldcup = competition_data_service.get_season_provider("worldcup2026", "2026")
        league = competition_data_service.get_season_provider(
            "premier_league", "2026-2027"
        )

        self.assertIn("knockout", worldcup)
        self.assertNotIn("knockout", league)
        self.assertIs(main.get_competition("worldcup2026")["supports_knockout"], True)
        self.assertIs(main.get_competition("premier_league")["supports_knockout"], False)


if __name__ == "__main__":
    unittest.main()
