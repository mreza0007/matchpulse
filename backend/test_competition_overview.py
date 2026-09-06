import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import competition_data_service
import main
from competition_data_service import CompetitionDataProviderError
from competition_overview_service import select_overview_matches
from services import generic_football_adapter


def match(match_id, status, kickoff_utc, **overrides):
    item = {
        "id": match_id,
        "competition_key": "premier_league",
        "season_key": "2026-2027",
        "status": status,
        "kickoff_utc": kickoff_utc,
        "is_live": status == "live",
        "is_finished": status == "finished",
    }
    item.update(overrides)
    return item


class CompetitionOverviewSelectionTests(unittest.TestCase):
    def test_live_upcoming_and_finished_window_is_bounded_and_deterministic(self):
        matches = [
            *(match(f"finished-{day}", "finished", f"2026-08-{day:02d}T12:00:00Z") for day in range(1, 8)),
            *(match(f"upcoming-{day}", "upcoming", f"2026-09-{day:02d}T12:00:00Z") for day in range(1, 8)),
            match("live-b", "live", "2026-08-31T13:00:00Z"),
            match("live-a", "live", "2026-08-31T12:00:00Z"),
            match("cancelled", "cancelled", "2026-09-01T10:00:00Z"),
            match("invalid-upcoming", "upcoming", "not-a-date"),
            match("naive-upcoming", "upcoming", "2026-09-01T12:00:00"),
            match("duplicate", "upcoming", "2026-09-01T11:00:00Z"),
            match("duplicate", "upcoming", "2026-09-01T09:00:00Z"),
        ]

        selected = select_overview_matches(list(reversed(matches)))
        selected_ids = [item["id"] for item in selected]

        self.assertEqual(selected_ids[:2], ["live-a", "live-b"])
        self.assertEqual(
            selected_ids[2:7],
            ["duplicate", "upcoming-1", "upcoming-2", "upcoming-3", "upcoming-4"],
        )
        self.assertEqual(
            selected_ids[7:],
            ["finished-7", "finished-6", "finished-5", "finished-4", "finished-3"],
        )
        self.assertEqual(len(selected), 12)
        self.assertNotIn("cancelled", selected_ids)
        self.assertNotIn("invalid-upcoming", selected_ids)
        self.assertNotIn("naive-upcoming", selected_ids)

    def test_all_live_matches_are_retained_even_without_kickoff(self):
        selected = select_overview_matches([
            match("live-known", "live", "2026-09-01T12:00:00Z"),
            match("live-unknown", "live", None),
        ])

        self.assertEqual(
            [item["id"] for item in selected],
            ["live-known", "live-unknown"],
        )

    def test_data_service_uses_one_authoritative_bounded_fetch(self):
        matches = [match("next", "upcoming", "2026-09-01T12:00:00Z")]
        overview = Mock(return_value=matches)
        season_provider = competition_data_service.get_season_provider(
            "premier_league", "2026-2027"
        )
        with patch.dict(season_provider, {"overview": overview}):
            selected = competition_data_service.get_overview_matches_for_season(
                "premier_league",
                "2026-2027",
            )

        self.assertEqual(selected, matches)
        overview.assert_called_once_with()

    @patch("services.generic_football_adapter.requests.get")
    def test_bounded_adapter_calls_overview_once_and_preserves_canonical_ids(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ok": True,
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "count": 1,
            "stale": True,
            "warnings": ["private-warning"],
            "provider": "private-provider",
            "matches": [
                {
                    **match("mp_match_canonical", "upcoming", "2026-09-01T12:00:00Z"),
                    "provider": "varzesh3",
                    "external_match_id": "private-123",
                    "private_wrapper_field": "secret",
                }
            ],
        }
        get.return_value = response

        matches = generic_football_adapter.get_season_overview(
            "premier_league", "2026-2027", competition_format="league"
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], "mp_match_canonical")
        self.assertNotIn("provider", matches[0])
        self.assertNotIn("external_match_id", matches[0])
        self.assertNotIn("private_wrapper_field", matches[0])
        get.assert_called_once()
        self.assertTrue(
            get.call_args.args[0].endswith(
                "/competitions/premier_league/seasons/2026-2027/overview"
            )
        )

    @patch("services.generic_football_adapter.requests.get")
    def test_bounded_adapter_rejects_scope_mismatch(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "competition_key": "la_liga",
            "season_key": "2026-2027",
            "matches": [],
        }
        get.return_value = response

        with self.assertRaises(generic_football_adapter.GenericFootballProviderError):
            generic_football_adapter.get_season_overview(
                "premier_league", "2026-2027"
            )

    @patch("services.generic_football_adapter.requests.get")
    def test_bounded_adapter_rejects_cross_season_envelope(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "competition_key": "premier_league",
            "season_key": "2025-2026",
            "matches": [],
        }
        get.return_value = response

        with self.assertRaises(generic_football_adapter.GenericFootballProviderError):
            generic_football_adapter.get_season_overview(
                "premier_league", "2026-2027"
            )

    @patch("services.generic_football_adapter.requests.get")
    def test_bounded_adapter_rejects_malformed_match_rows(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "matches": ["not-a-match"],
        }
        get.return_value = response

        with self.assertRaises(generic_football_adapter.GenericFootballProviderError):
            generic_football_adapter.get_season_overview(
                "premier_league", "2026-2027"
            )

    @patch("services.generic_football_adapter.requests.get")
    def test_bounded_adapter_accepts_empty_overview(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "matches": [],
        }
        get.return_value = response

        self.assertEqual(
            generic_football_adapter.get_season_overview(
                "premier_league", "2026-2027"
            ),
            [],
        )

    @patch("services.generic_football_adapter.requests.get")
    def test_bounded_adapter_rejects_match_scope_mismatch(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "matches": [
                {
                    **match("mp_match_wrong_scope", "upcoming", "2026-09-01T12:00:00Z"),
                    "competition_key": "la_liga",
                }
            ],
        }
        get.return_value = response

        with self.assertRaises(generic_football_adapter.GenericFootballProviderError):
            generic_football_adapter.get_season_overview(
                "premier_league", "2026-2027"
            )

    @patch("services.generic_football_adapter.requests.get")
    def test_bounded_adapter_rejects_cross_season_match(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "matches": [
                {
                    **match("mp_match_wrong_season", "upcoming", "2026-09-01T12:00:00Z"),
                    "season_key": "2025-2026",
                }
            ],
        }
        get.return_value = response

        with self.assertRaises(generic_football_adapter.GenericFootballProviderError):
            generic_football_adapter.get_season_overview(
                "premier_league", "2026-2027"
            )

    @patch("services.generic_football_adapter.requests.get")
    def test_bounded_adapter_rejects_noncanonical_match_id(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "matches": [
                match("480301", "upcoming", "2026-09-01T12:00:00Z")
            ],
        }
        get.return_value = response

        with self.assertRaises(generic_football_adapter.GenericFootballProviderError):
            generic_football_adapter.get_season_overview(
                "premier_league", "2026-2027"
            )

    @patch("services.generic_football_adapter.requests.get")
    def test_full_season_adapter_still_calls_matches(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"matches": []}
        get.return_value = response

        self.assertEqual(
            generic_football_adapter.get_season_matches(
                "premier_league", "2026-2027"
            ),
            [],
        )
        get.assert_called_once()
        self.assertTrue(
            get.call_args.args[0].endswith(
                "/competitions/premier_league/seasons/2026-2027/matches"
            )
        )


class CompetitionOverviewRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def test_overview_returns_scoped_bounded_match_envelope(self):
        matches = [match("next", "upcoming", "2026-09-01T12:00:00Z")]
        with patch(
            "main.get_overview_matches_for_season",
            return_value=matches,
        ) as get_overview:
            response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/overview"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "count": 1,
            "matches": matches,
        })
        get_overview.assert_called_once_with("premier_league", "2026-2027")

    def test_unknown_competition_and_season_are_safe_404s(self):
        unknown_competition = self.client.get(
            "/competitions/unknown/seasons/2026-2027/overview"
        )
        unknown_season = self.client.get(
            "/competitions/premier_league/seasons/unknown/overview"
        )

        self.assertEqual(unknown_competition.status_code, 404)
        self.assertEqual(unknown_competition.json(), {"detail": "Competition not found"})
        self.assertEqual(unknown_season.status_code, 404)
        self.assertEqual(unknown_season.json(), {"detail": "Season not found"})

    def test_archived_worldcup_does_not_use_generic_overview(self):
        with patch("main.get_overview_matches_for_season") as get_overview:
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/overview"
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(
            response.json(),
            {"detail": "Competition overview not supported"},
        )
        get_overview.assert_not_called()

    def test_provider_failure_is_explicit_and_sanitized(self):
        private_error = CompetitionDataProviderError("private wrapper detail")
        with patch(
            "main.get_overview_matches_for_season",
            side_effect=private_error,
        ):
            response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/overview"
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Matches provider unavailable"})
        self.assertNotIn("private wrapper detail", response.text)

    @patch("services.generic_football_adapter.requests.get")
    def test_wrapper_scope_mismatch_is_a_sanitized_502(self, get):
        wrapper_response = Mock()
        wrapper_response.raise_for_status.return_value = None
        wrapper_response.json.return_value = {
            "competition_key": "la_liga",
            "season_key": "2026-2027",
            "matches": [],
        }
        get.return_value = wrapper_response

        response = self.client.get(
            "/competitions/premier_league/seasons/2026-2027/overview"
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Matches provider unavailable"})
        self.assertNotIn("la_liga", response.text)
        self.assertNotIn("Invalid overview scope", response.text)


if __name__ == "__main__":
    unittest.main()
