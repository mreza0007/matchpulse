import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import competition_data_service
import competition_service
import main
import season_service


REQUIRED_SCOPES = {
    "premier_league": ("2026-2027", True),
    "persian_gulf_pro_league": ("1405-1406", True),
    "la_liga": ("2026-2027", True),
    "serie_a": ("2026-2027", True),
    "bundesliga": ("2026-2027", True),
    "ligue_1": ("2026-2027", True),
    "champions_league": ("2026-2027", False),
    "europa_league": ("2026-2027", False),
}


class CompetitionExpansionRegistryTests(unittest.TestCase):
    def test_required_competitions_are_active_with_exact_default_seasons(self):
        competitions = {
            item["competition_key"]: item
            for item in competition_service.get_competitions()
        }

        for competition_key, (season_key, supports_standings) in REQUIRED_SCOPES.items():
            with self.subTest(competition_key=competition_key):
                competition = competitions[competition_key]
                self.assertEqual(competition["season_key"], season_key)
                self.assertEqual(competition["status"], "active")
                self.assertIs(competition["is_active"], True)
                self.assertIs(competition["supports_matches"], True)
                self.assertIs(
                    competition["supports_standings"],
                    supports_standings,
                )
                self.assertIs(competition["supports_predictions"], True)
                self.assertIs(competition["supports_events"], True)

    def test_worldcup_events_remain_disabled_and_future_entries_default_false(self):
        worldcup = competition_service.get_competition("worldcup2026")
        self.assertIs(worldcup["supports_events"], False)

        future = competition_service.validated_competition({
            "competition_key": "future_competition",
            "format": "league",
            "is_active": True,
            "supports_predictions": False,
        })
        self.assertIs(future["supports_events"], False)

    def test_required_default_seasons_and_generic_dispatchers_exist(self):
        for competition_key, (season_key, supports_standings) in REQUIRED_SCOPES.items():
            with self.subTest(competition_key=competition_key):
                season = season_service.get_default_season(competition_key)
                provider = competition_data_service.get_season_provider(
                    competition_key,
                    season_key,
                )
                self.assertEqual(season["season_key"], season_key)
                self.assertIn("matches", provider)
                self.assertIn("teams", provider)
                self.assertIn("live", provider)
                self.assertIn("events", provider)
                self.assertEqual("standings" in provider, supports_standings)


class CompetitionExpansionRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def test_directory_contains_all_required_competitions(self):
        response = self.client.get("/competitions")
        self.assertEqual(response.status_code, 200)
        keys = {
            item["competition_key"]
            for item in response.json()["competitions"]
        }
        self.assertTrue(REQUIRED_SCOPES.keys() <= keys)
        by_key = {
            item["competition_key"]: item
            for item in response.json()["competitions"]
        }
        self.assertTrue(all(by_key[key]["supports_events"] for key in REQUIRED_SCOPES))
        self.assertIs(by_key["worldcup2026"]["supports_events"], False)

    def test_new_domestic_scope_dispatches_matches(self):
        matches = [{"id": "laliga-1"}]
        with patch("main.get_matches_for_season", return_value=matches) as get_matches:
            response = self.client.get(
                "/competitions/la_liga/seasons/2026-2027/matches?status=all"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["matches"], matches)
        get_matches.assert_called_once_with("la_liga", "2026-2027", status="all")

    def test_uefa_standings_are_rejected_without_dispatch(self):
        with patch("main.get_standings_for_season") as get_standings:
            response = self.client.get(
                "/competitions/champions_league/seasons/2026-2027/standings"
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(
            response.json(),
            {"detail": "Competition standings not supported"},
        )
        get_standings.assert_not_called()


if __name__ == "__main__":
    unittest.main()
