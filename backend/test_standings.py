import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import competition_data_service
import main
from services import generic_football_adapter


STANDINGS = [
    {
        "rank": 1,
        "team_id": "mp_team_arsenal",
        "provider": "generic-test-provider",
        "external_team_id": 87,
        "team_fa": "آرسنال",
        "team_en": None,
        "logo": "https://example.test/arsenal.png",
        "played": 2,
        "wins": 2,
        "draws": 0,
        "losses": 0,
        "points": 6,
        "goals_for": 5,
        "goals_against": 1,
        "goal_difference": 4,
        "qualification_color": "#00f",
        "has_live_match": False,
    },
    {
        "rank": 2,
        "team_id": "mp_team_liverpool",
        "provider": "generic-test-provider",
        "external_team_id": 90,
        "team_fa": "لیورپول",
        "team_en": None,
        "logo": "https://example.test/liverpool.png",
        "played": 2,
        "wins": 1,
        "draws": 1,
        "losses": 0,
        "points": 4,
        "goals_for": 3,
        "goals_against": 1,
        "goal_difference": 2,
        "qualification_color": None,
        "has_live_match": False,
    },
]


class StandingsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    @patch("services.generic_football_adapter.requests.get")
    def test_premier_league_standings_preserve_order_and_team_identity(self, get):
        response = Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ok": True,
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "count": 2,
            "standings": STANDINGS,
        }
        get.return_value = response

        result = self.client.get(
            "/competitions/premier_league/seasons/2026-2027/standings"
        )

        self.assertEqual(result.status_code, 200)
        payload = result.json()
        self.assertEqual(payload["competition_key"], "premier_league")
        self.assertEqual(payload["season_key"], "2026-2027")
        self.assertEqual([row["rank"] for row in payload["standings"]], [1, 2])
        self.assertEqual(payload["standings"][0]["team_id"], "mp_team_arsenal")
        self.assertEqual(payload["standings"][0]["external_team_id"], 87)
        self.assertTrue(get.call_args.args[0].endswith(
            "/competitions/premier_league/seasons/2026-2027/standings"
        ))

    def test_unsupported_competition_does_not_fabricate_standings(self):
        with patch("main.get_standings_for_season") as standings:
            result = self.client.get(
                "/competitions/worldcup2026/seasons/2026/standings"
            )

        self.assertEqual(result.status_code, 501)
        self.assertEqual(result.json(), {"detail": "Competition standings not supported"})
        standings.assert_not_called()

    def test_invalid_competition_and_season_keep_404_behavior(self):
        invalid_competition = self.client.get(
            "/competitions/unknown/seasons/2026-2027/standings"
        )
        invalid_season = self.client.get(
            "/competitions/premier_league/seasons/unknown/standings"
        )

        self.assertEqual(invalid_competition.status_code, 404)
        self.assertEqual(invalid_competition.json(), {"detail": "Competition not found"})
        self.assertEqual(invalid_season.status_code, 404)
        self.assertEqual(invalid_season.json(), {"detail": "Season not found"})

    def test_provider_failure_is_sanitized(self):
        with patch(
            "services.generic_football_adapter.requests.get",
            side_effect=generic_football_adapter.requests.RequestException("private provider detail"),
        ):
            result = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/standings"
            )

        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json(), {"detail": "Standings provider unavailable"})
        self.assertNotIn("private provider detail", result.text)

    def test_wrapper_unavailable_standings_remain_distinct(self):
        response = Mock(status_code=501)
        with patch("services.generic_football_adapter.requests.get", return_value=response):
            result = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/standings"
            )

        self.assertEqual(result.status_code, 501)
        self.assertEqual(result.json(), {"detail": "Competition standings not available"})

    def test_existing_match_and_team_routes_are_unchanged(self):
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

        self.assertEqual(match_response.json(), {"count": 1, "status": "all", "matches": matches})
        self.assertEqual(team_response.json(), {"count": 1, "teams": teams})
        get_matches.assert_called_once_with("premier_league", "2026-2027", status="all")
        get_teams.assert_called_once_with("premier_league", "2026-2027")

    def test_legacy_worldcup_routes_keep_existing_targets(self):
        self.assertIs(main.get_events.__annotations__["match_id"], int)
        self.assertIs(main.get_match_live.__annotations__["match_id"], int)

        with patch("main.get_match_events", return_value={"events": []}) as events:
            main.get_events(75)
        with patch("main.get_match_live_from_worldcup_wrapper", return_value={"id": 75}) as live:
            main.get_match_live(75)

        events.assert_called_once_with(75)
        live.assert_called_once_with(75)


class StandingsDispatcherTests(unittest.TestCase):
    def test_premier_league_dispatcher_has_standings_without_worldcup_changes(self):
        premier_league = competition_data_service.get_season_provider(
            "premier_league", "2026-2027"
        )
        world_cup = competition_data_service.get_season_provider("worldcup2026", "2026")

        self.assertIn("standings", premier_league)
        self.assertNotIn("standings", world_cup)


if __name__ == "__main__":
    unittest.main()
