import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import competition_service
import main


class CompetitionFormatRegistryTests(unittest.TestCase):
    def test_current_competitions_expose_explicit_formats_and_keep_types(self):
        premier_league = competition_service.get_competition("premier_league")
        world_cup = competition_service.get_competition("worldcup2026")

        self.assertEqual(premier_league["format"], "league")
        self.assertEqual(premier_league["type"], "club")
        self.assertEqual(world_cup["format"], "group_knockout")
        self.assertEqual(world_cup["type"], "international")

    def test_invalid_or_missing_format_is_rejected(self):
        invalid_entries = [
            {"competition_key": "invalid", "format": "round_robin"},
            {"competition_key": "missing"},
        ]

        for entry in invalid_entries:
            with self.subTest(entry=entry):
                with patch.object(competition_service, "COMPETITIONS", [entry]):
                    with self.assertRaisesRegex(ValueError, "Invalid competition format"):
                        competition_service.get_competitions()


class CompetitionFormatRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def test_competition_list_includes_format(self):
        response = self.client.get("/competitions")

        self.assertEqual(response.status_code, 200)
        competitions = {
            item["competition_key"]: item
            for item in response.json()["competitions"]
        }
        self.assertEqual(competitions["premier_league"]["format"], "league")
        self.assertEqual(competitions["worldcup2026"]["format"], "group_knockout")

    def test_competition_detail_includes_format_and_preserves_type(self):
        response = self.client.get("/competitions/worldcup2026")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["format"], "group_knockout")
        self.assertEqual(response.json()["type"], "international")

    def test_existing_season_match_and_team_routes_are_unchanged(self):
        season_response = self.client.get("/competitions/premier_league/seasons/2026-2027")
        self.assertEqual(season_response.status_code, 200)
        self.assertEqual(season_response.json()["season_key"], "2026-2027")

        matches = [{"id": "match-1"}]
        teams = [{"id": "team-1"}]
        with (
            patch("main.get_matches_for_season", return_value=matches) as get_matches,
            patch("main.get_teams_for_season", return_value=teams) as get_teams,
        ):
            match_response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/matches?status=all"
            )
            team_response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/teams"
            )

        self.assertEqual(match_response.status_code, 200)
        self.assertEqual(match_response.json(), {"count": 1, "status": "all", "matches": matches})
        self.assertEqual(team_response.status_code, 200)
        self.assertEqual(team_response.json(), {"count": 1, "teams": teams})
        get_matches.assert_called_once_with("premier_league", "2026-2027", status="all")
        get_teams.assert_called_once_with("premier_league", "2026-2027")


if __name__ == "__main__":
    unittest.main()
