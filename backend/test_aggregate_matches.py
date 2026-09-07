import copy
import unittest
from unittest.mock import Mock, patch

import requests
from fastapi.testclient import TestClient

import main
from services import generic_football_adapter as adapter


DATE = "2026-09-07"


def daily_group(key="premier_league", season="2026-2027"):
    return {
        "competition": {"key": key, "season_key": season, "name": "Premier League"},
        "matches": [{
            "id": "mp_match_daily", "competition_key": key, "season_key": season,
            "home_team_id": "mp_team_home", "away_team_id": "mp_team_away",
            "home_name_en": "Home", "away_name_en": "Away",
            "home_name_fa": "خانه", "away_name_fa": "مهمان",
            "kickoff_utc": "2026-09-06T21:00:00Z", "status": "live",
            "home_score": 1, "away_score": 0,
            "provider": "private", "external_match_id": "private-id",
            "warnings": ["kickoff_time_resolved_from_local_fields"],
            "private_extra": "secret",
        }],
    }


def daily_payload(groups=None, errors=None):
    return {"date": DATE, "groups": [daily_group()] if groups is None else groups, "errors": errors or []}


class AggregateMatchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def request_daily(self, payload=None, error=None):
        response = Mock()
        response.json.return_value = payload if payload is not None else daily_payload()
        with (
            patch.object(adapter.requests, "get", return_value=response, side_effect=error) as get,
            patch("competition_data_service.get_matches_for_season") as season,
            patch("competition_service.get_competitions") as directory,
            patch("main.get_real_matches") as worldcup,
            patch.object(adapter, "get_season_matches") as full,
            patch.object(adapter, "get_season_overview") as overview,
            patch.object(adapter, "get_season_teams") as teams,
            patch.object(adapter, "get_season_standings") as standings,
            patch.dict("os.environ", {"GENERIC_FOOTBALL_WRAPPER_URL": "http://configured-wrapper:3060"}),
        ):
            result = self.client.get(f"/matches/by-date?date={DATE}")
        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], f"http://configured-wrapper:3060/matches/by-date?date={DATE}")
        for forbidden in (season, directory, worldcup, full, overview, teams, standings):
            forbidden.assert_not_called()
        self.assertEqual(result.status_code, 200)
        return result.json()

    def test_one_daily_request_preserves_public_contract_and_display_fields(self):
        result = self.request_daily()
        self.assertEqual(set(result), {"date", "groups", "errors"})
        self.assertEqual(result["date"], DATE)
        self.assertEqual(result["errors"], [])
        group = result["groups"][0]
        self.assertEqual(set(group), {"competition", "matches"})
        self.assertEqual(set(group["competition"]), {"key", "name", "name_fa", "season_key", "type"})
        match = group["matches"][0]
        self.assertEqual(match["id"], "mp_match_daily")
        self.assertEqual(match["home_team_id"], "mp_team_home")
        self.assertEqual(match["home_en"], "Home")
        self.assertEqual(match["home_fa"], "خانه")
        self.assertTrue(match["is_live"])
        self.assertEqual(match["score"], {"home": 1, "away": 0})
        self.assertEqual(match["warnings"], ["kickoff_time_resolved_from_local_fields"])
        self.assertNotIn("private", str(result))
        self.assertNotIn("secret", str(result))

    def test_empty_success(self):
        self.assertEqual(self.request_daily(daily_payload([])), {"date": DATE, "groups": [], "errors": []})

    def test_daily_group_order_and_all_matches_are_preserved(self):
        first = daily_group("la_liga")
        second = daily_group()
        second["matches"] *= 20
        result = self.request_daily(daily_payload([first, second]))
        self.assertEqual([g["competition"]["key"] for g in result["groups"]], ["la_liga", "premier_league"])
        self.assertEqual(len(result["groups"][1]["matches"]), 20)

    def test_provider_failure_is_one_source_error_without_fallback(self):
        for error in (requests.Timeout("secret"), requests.HTTPError("private URL"), ValueError("bad json secret")):
            with self.subTest(error=type(error).__name__):
                result = self.request_daily(error=error)
                self.assertEqual(result["groups"], [])
                self.assertEqual(len(result["errors"]), 1)
                self.assertIsNone(result["errors"][0]["competition_key"])
                self.assertNotIn("secret", str(result))
                self.assertNotIn("private", str(result))

    def test_invalid_wrapper_envelopes_fail_safely(self):
        for payload in ([], {}, {"date": "2026-09-08", "groups": [], "errors": []},
                        {"date": DATE, "groups": {}, "errors": []}):
            with self.subTest(payload=payload):
                result = self.request_daily(payload)
                self.assertEqual(result["groups"], [])
                self.assertEqual(len(result["errors"]), 1)

    def test_partial_provider_errors_are_sanitized_without_losing_valid_groups(self):
        result = self.request_daily(daily_payload(errors=[{
            "competition_key": "la_liga", "season_key": "2026-2027", "message": "secret",
        }]))
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["errors"][0]["competition_key"], "la_liga")
        self.assertNotIn("secret", str(result))

    def test_malformed_group_is_isolated(self):
        result = self.request_daily(daily_payload([None, daily_group()]))
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(len(result["errors"]), 1)

    def test_wrong_date_naive_missing_and_invalid_kickoffs_never_leak(self):
        for kickoff in ("2026-09-07T21:00:00Z", "2026-09-07T12:00:00", None, "bad"):
            with self.subTest(kickoff=kickoff):
                group = daily_group()
                group["matches"][0].update(kickoff_utc=kickoff, date_key=DATE)
                result = self.request_daily(daily_payload([group]))
                self.assertEqual(result["groups"], [])
                self.assertTrue(result["errors"])

    def test_scopes_and_provider_ids_are_rejected(self):
        for changes in ({"id": "1234"}, {"home_team_id": "123"},
                        {"competition_key": "la_liga"}, {"season_key": "2025-2026"}):
            with self.subTest(changes=changes):
                group = daily_group()
                group["matches"][0].update(changes)
                self.assertTrue(self.request_daily(daily_payload([group]))["errors"])

    def test_archived_worldcup_and_unknown_scopes_not_exposed_or_separately_fetched(self):
        for key, season in (("worldcup2026", "2026"), ("unknown", "2026"), ("premier_league", "unknown")):
            result = self.request_daily(daily_payload([daily_group(key, season)]))
            self.assertEqual(result["groups"], [])
            self.assertTrue(result["errors"])

    def test_invalid_date_returns_422_without_network(self):
        with patch.object(adapter.requests, "get") as get:
            for invalid_date in ("2026-02-30", "2026-9-7", "not-a-date", " 2026-09-07", "۲۰۲۶-۰۹-۰۷"):
                with self.subTest(date=invalid_date):
                    response = self.client.get("/matches/by-date", params={"date": invalid_date})
                    self.assertEqual(response.status_code, 422)
            get.assert_not_called()

    def test_legacy_matches_route_is_unchanged(self):
        matches = [{"id": 75}]
        with patch("main.get_real_matches", return_value=matches) as legacy:
            response = self.client.get("/matches?status=live")
        self.assertEqual(response.json(), {"count": 1, "status": "live", "matches": matches})
        legacy.assert_called_once_with(status="live")

    def test_scoped_premier_league_route_is_unchanged(self):
        matches = [{"id": "mp_match_1"}]
        with patch("main.get_matches_for_season", return_value=matches) as scoped:
            response = self.client.get("/competitions/premier_league/seasons/2026-2027/matches?status=all")
        self.assertEqual(response.json(), {"count": 1, "status": "all", "matches": matches})
        scoped.assert_called_once_with("premier_league", "2026-2027", status="all")

    def test_wrapper_input_not_mutated(self):
        payload = daily_payload()
        original = copy.deepcopy(payload)
        self.request_daily(payload)
        self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
