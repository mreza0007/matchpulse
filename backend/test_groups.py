import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import competition_data_service
import main
from services import worldcup_adapter


GROUPS = [
    {
        "group_key": "B",
        "standings": [
            {
                "team_id": "5",
                "team_fa": "کانادا",
                "team_en": "Canada",
                "logo": "https://example.test/ca.png",
                "played": 3,
                "wins": 2,
                "draws": 1,
                "losses": 0,
                "goals_for": 5,
                "goals_against": 2,
                "goal_difference": 3,
                "points": 7,
            },
            {
                "team_id": "6",
                "team_fa": "قطر",
                "team_en": "Qatar",
                "logo": "https://example.test/qa.png",
                "played": 3,
                "wins": 1,
                "draws": 1,
                "losses": 1,
                "goals_for": 3,
                "goals_against": 3,
                "goal_difference": 0,
                "points": 4,
            },
        ],
    },
    {"group_key": "A", "standings": []},
]


class GroupsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def test_worldcup_groups_preserve_source_group_and_row_order(self):
        with patch("main.get_groups_for_season", return_value=GROUPS) as get_groups:
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/groups"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["competition_key"], "worldcup2026")
        self.assertEqual(payload["season_key"], "2026")
        self.assertEqual(payload["count"], 2)
        self.assertEqual([group["group_key"] for group in payload["groups"]], ["B", "A"])
        self.assertEqual(
            [row["team_id"] for row in payload["groups"][0]["standings"]],
            ["5", "6"],
        )
        self.assertEqual(payload["groups"][0]["standings"][0]["team_en"], "Canada")
        get_groups.assert_called_once_with("worldcup2026", "2026")

    def test_league_groups_are_unsupported_without_dispatch(self):
        with patch("main.get_groups_for_season") as get_groups:
            response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/groups"
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json(), {"detail": "Competition groups not supported"})
        get_groups.assert_not_called()

    def test_invalid_competition_and_season_keep_404_behavior(self):
        competition = self.client.get("/competitions/unknown/seasons/2026/groups")
        season = self.client.get("/competitions/worldcup2026/seasons/unknown/groups")

        self.assertEqual(competition.status_code, 404)
        self.assertEqual(competition.json(), {"detail": "Competition not found"})
        self.assertEqual(season.status_code, 404)
        self.assertEqual(season.json(), {"detail": "Season not found"})

    def test_provider_failure_is_sanitized(self):
        with patch(
            "main.get_groups_for_season",
            side_effect=competition_data_service.CompetitionGroupsProviderError(
                "private upstream detail"
            ),
        ):
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/groups"
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Groups provider unavailable"})
        self.assertNotIn("private upstream detail", response.text)

    def test_configured_capability_without_source_is_unavailable(self):
        with patch("main.get_groups_for_season", return_value=None):
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/groups"
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(
            response.json(),
            {"detail": "Competition groups data source not configured"},
        )

    def test_existing_routes_and_legacy_worldcup_targets_are_unchanged(self):
        with (
            patch("main.get_standings_for_season", return_value=[{"rank": 1}]),
            patch("main.get_matches_for_season", return_value=[{"id": 1}]),
            patch("main.get_teams_for_season", return_value=[{"id": 1}]),
        ):
            standings = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/standings"
            )
            matches = self.client.get(
                "/competitions/worldcup2026/seasons/2026/matches"
            )
            teams = self.client.get(
                "/competitions/worldcup2026/seasons/2026/teams"
            )

        self.assertEqual(standings.status_code, 200)
        self.assertEqual(matches.json()["matches"], [{"id": 1}])
        self.assertEqual(teams.json()["teams"], [{"id": 1}])
        self.assertIs(main.get_events.__annotations__["match_id"], int)
        self.assertIs(main.get_match_live.__annotations__["match_id"], int)


class GroupsAdapterTests(unittest.TestCase):
    def test_registry_advertises_only_configured_groups_support(self):
        worldcup = main.get_competition("worldcup2026")
        league = main.get_competition("premier_league")

        self.assertIs(worldcup["supports_groups"], True)
        self.assertIs(league["supports_groups"], False)

    def test_explicit_source_fields_are_normalized_without_rank_or_qualification(self):
        groups_payload = {
            "groups": [
                {
                    "name": "C",
                    "teams": [
                        {
                            "team_id": "9",
                            "mp": "2",
                            "w": "1",
                            "d": "1",
                            "l": "0",
                            "gf": "4",
                            "ga": "2",
                            "gd": "2",
                            "pts": "4",
                        }
                    ],
                }
            ]
        }
        teams_payload = {
            "teams": [
                {
                    "id": "9",
                    "name_fa": "ایران",
                    "name_en": "Iran",
                    "flag": "https://example.test/ir.png",
                }
            ]
        }

        groups = worldcup_adapter.normalize_groups_payload(groups_payload, teams_payload)
        row = groups[0]["standings"][0]

        self.assertEqual(groups[0]["group_key"], "C")
        self.assertEqual(row["team_id"], "9")
        self.assertEqual(row["team_en"], "Iran")
        self.assertEqual(row["points"], 4)
        self.assertNotIn("rank", row)
        self.assertNotIn("qualified", row)

    def test_invalid_source_payload_is_not_silently_accepted(self):
        with self.assertRaises(worldcup_adapter.WorldCupGroupsProviderError):
            worldcup_adapter.normalize_groups_payload(
                {"groups": [{"name": "A", "teams": [{"team_id": "1"}]}]},
                {"teams": [{"id": "1"}]},
            )

    def test_dispatcher_configures_groups_only_for_worldcup(self):
        worldcup = competition_data_service.get_season_provider("worldcup2026", "2026")
        league = competition_data_service.get_season_provider(
            "premier_league", "2026-2027"
        )

        self.assertIn("groups", worldcup)
        self.assertNotIn("groups", league)


if __name__ == "__main__":
    unittest.main()
