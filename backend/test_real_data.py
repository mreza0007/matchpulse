import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

import competition_data_service
import main
from competition_service import get_competition
from real_data_service import get_real_matches, get_real_teams
from season_service import get_season
from services import generic_football_adapter


class RegistryAndDispatcherTests(unittest.TestCase):
    def test_worldcup_dispatcher_functions_remain_unchanged(self):
        provider = competition_data_service.COMPETITION_DATA_PROVIDERS["worldcup2026"]["seasons"]["2026"]
        self.assertIs(provider["matches"], get_real_matches)
        self.assertIs(provider["teams"], get_real_teams)
        self.assertNotIn("live", provider)
        self.assertNotIn("events", provider)

    def test_premier_league_registry_and_season_exist(self):
        competition = get_competition("premier_league")
        season = get_season("premier_league", "2026-2027")
        self.assertEqual(competition["name_en"], "Premier League")
        self.assertTrue(competition["supports_standings"])
        self.assertFalse(competition["supports_predictions"])
        self.assertEqual(season["status"], "active")
        self.assertTrue(season["is_default"])

    def test_scoped_dispatcher_preserves_stable_string_ids(self):
        season_provider = competition_data_service.COMPETITION_DATA_PROVIDERS["premier_league"]["seasons"]["2026-2027"]
        live = Mock(return_value={"match": {"id": "mp_match_live"}})
        events = Mock(return_value={"match_id": "mp_match_events", "events": []})

        with patch.dict(season_provider, {"live": live, "events": events}):
            competition_data_service.get_match_live_for_season(
                "premier_league", "2026-2027", "mp_match_live"
            )
            competition_data_service.get_match_events_for_season(
                "premier_league", "2026-2027", "mp_match_events"
            )

        live.assert_called_once_with("mp_match_live")
        events.assert_called_once_with("mp_match_events")

    def test_unknown_competition_and_season_return_none(self):
        self.assertIsNone(competition_data_service.get_matches_for_season("unknown", "2026"))
        self.assertIsNone(competition_data_service.get_teams_for_season("premier_league", "unknown"))
        self.assertIsNone(competition_data_service.get_match_live_for_season("unknown", "2026", "id"))


class GenericNormalizationTests(unittest.TestCase):
    def test_status_normalization_accepts_space_hyphen_and_underscore_separators(self):
        cases = {
            "in progress": "live",
            "in-progress": "live",
            "in_progress": "live",
            "full time": "finished",
            "scheduled": "upcoming",
        }
        for raw_status, expected in cases.items():
            with self.subTest(raw_status=raw_status):
                self.assertEqual(generic_football_adapter.normalize_status(raw_status), expected)

    def test_match_normalization_preserves_id_zero_scores_and_status(self):
        match = generic_football_adapter.normalize_match(
            {
                "id": "mp_match_fff9d4ee0487decc1d182887",
                "competition_key": "premier_league",
                "season_key": "2026-2027",
                "provider": "generic-test-provider",
                "external_match_id": "123",
                "home_team_id": "home-1",
                "away_team_id": "away-1",
                "home_name_fa": "Home FA",
                "away_name_fa": "Away FA",
                "home_name_en": None,
                "away_name_en": None,
                "status": "finished",
                "home_score": 0,
                "away_score": 0,
                "home_penalties": 4,
                "away_penalties": 3,
            }
        )

        self.assertEqual(match["id"], "mp_match_fff9d4ee0487decc1d182887")
        self.assertEqual(match["home_en"], "Home FA")
        self.assertIsNone(match["home_team_name_en"])
        self.assertEqual(match["score"], {"home": 0, "away": 0})
        self.assertTrue(match["is_finished"])
        self.assertFalse(match["is_live"])
        self.assertFalse(match["is_upcoming"])
        self.assertEqual(match["home_penalty_score"], 4)

    def test_live_and_unknown_status_flags_are_deterministic(self):
        live = generic_football_adapter.normalize_match({"status": "live"})
        unknown = generic_football_adapter.normalize_match({"status": "postponed"})
        self.assertTrue(live["is_live"])
        self.assertFalse(live["is_finished"])
        self.assertEqual(unknown["status"], "postponed")
        self.assertFalse(unknown["is_live"])
        self.assertFalse(unknown["is_finished"])
        self.assertFalse(unknown["is_upcoming"])

    def test_team_normalization_does_not_invent_english_name(self):
        team = generic_football_adapter.normalize_team(
            {
                "id": "mp_team_1",
                "competition_key": "premier_league",
                "season_key": "2026-2027",
                "provider": "generic-test-provider",
                "external_team_id": "9",
                "name_fa": "Team FA",
                "name_en": None,
                "logo": None,
            }
        )
        self.assertEqual(team["id"], "mp_team_1")
        self.assertIsNone(team["name_en"])
        self.assertEqual(team["flag"], "")
        self.assertEqual(team["warnings"], [])


class AdapterHttpTests(unittest.TestCase):
    @patch("services.generic_football_adapter.fetch_json")
    def test_match_events_preserves_count_and_stale(self, fetch_json):
        fetch_json.return_value = {
            "ok": True,
            "match_id": "mp_match_1",
            "count": 7,
            "stale": True,
            "events": [{"id": "event-1"}],
        }

        result = generic_football_adapter.get_match_events("mp_match_1")

        self.assertEqual(result["count"], 7)
        self.assertIs(result["stale"], True)
        self.assertEqual(result["events"], [{"id": "event-1"}])

    @patch("services.generic_football_adapter.fetch_json")
    def test_match_events_derives_missing_count_without_inventing_stale(self, fetch_json):
        fetch_json.return_value = {
            "events": [{"id": "event-1"}, {"id": "event-2"}],
        }

        result = generic_football_adapter.get_match_events("mp_match_1")

        self.assertEqual(result["count"], 2)
        self.assertIsNone(result["stale"])

    @patch("services.generic_football_adapter.requests.get")
    def test_season_matches_uses_generic_wrapper_and_normalizes(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "matches": [{"id": "mp_match_1", "status": "upcoming", "home_score": 0, "away_score": 0}]
        }
        get.return_value = response

        matches = generic_football_adapter.get_season_matches("premier_league", "2026-2027")

        self.assertEqual(matches[0]["id"], "mp_match_1")
        self.assertTrue(matches[0]["is_upcoming"])
        self.assertEqual(matches[0]["home_score"], 0)
        self.assertTrue(get.call_args.args[0].endswith(
            "/competitions/premier_league/seasons/2026-2027/matches"
        ))

    @patch("services.generic_football_adapter.requests.get")
    def test_http_failure_returns_safe_empty_results(self, get):
        get.side_effect = generic_football_adapter.requests.RequestException("unavailable")
        self.assertEqual(
            generic_football_adapter.get_season_matches("premier_league", "2026-2027"), []
        )
        self.assertEqual(generic_football_adapter.get_match_events("mp_match_1")["events"], [])


class RouteCompatibilityTests(unittest.TestCase):
    def test_scoped_routes_validate_unknown_competition_and_season(self):
        with self.assertRaises(HTTPException) as competition_error:
            main.get_competition_season_match_live("unknown", "2026", "mp_match_1")
        self.assertEqual(competition_error.exception.status_code, 404)

        with self.assertRaises(HTTPException) as season_error:
            main.get_competition_season_match_events("premier_league", "unknown", "mp_match_1")
        self.assertEqual(season_error.exception.status_code, 404)

    def test_worldcup_scoped_live_is_unsupported_not_rerouted(self):
        with self.assertRaises(HTTPException) as error:
            main.get_competition_season_match_live("worldcup2026", "2026", "75")
        self.assertEqual(error.exception.status_code, 501)

    def test_legacy_worldcup_route_functions_keep_numeric_annotations_and_targets(self):
        self.assertIs(main.get_events.__annotations__["match_id"], int)
        self.assertIs(main.get_match_live.__annotations__["match_id"], int)

        with patch("main.get_match_events", return_value={"events": []}) as events:
            main.get_events(75)
        with patch("main.get_match_live_from_worldcup_wrapper", return_value={"id": 75}) as live:
            main.get_match_live(75)

        events.assert_called_once_with(75)
        live.assert_called_once_with(75)


class ScopedRouteTestClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def test_premier_league_live_route_passes_string_id(self):
        payload = {"ok": True, "match": {"id": "mp_match_live"}}
        with patch("main.get_match_live_for_season", return_value=payload) as live:
            response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/matches/mp_match_live/live"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        live.assert_called_once_with("premier_league", "2026-2027", "mp_match_live")

    def test_premier_league_events_route_passes_string_id(self):
        payload = {"ok": True, "match_id": "mp_match_events", "events": []}
        with patch("main.get_match_events_for_season", return_value=payload) as events:
            response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/matches/mp_match_events/events"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        events.assert_called_once_with("premier_league", "2026-2027", "mp_match_events")

    def test_scoped_route_returns_404_for_unknown_season(self):
        response = self.client.get(
            "/competitions/premier_league/seasons/unknown/matches/mp_match_1/live"
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
