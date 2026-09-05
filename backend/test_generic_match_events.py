import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import competition_data_service
import main
from competition_service import get_competition
from services import generic_football_adapter


MATCH_ID = "mp_match_scope_a"
MATCH = {
    "id": MATCH_ID,
    "competition_key": "premier_league",
    "season_key": "2026-2027",
}
EVENT_PATH = (
    "/competitions/premier_league/seasons/2026-2027/"
    f"matches/{MATCH_ID}/events"
)


class GenericEventNormalizationTests(unittest.TestCase):
    def normalize(self, events, **overrides):
        payload = {
            "ok": True,
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "match_id": MATCH_ID,
            "provider": "varzesh3",
            "external_match_id": "480301",
            "stale": False,
            "warnings": [],
            "events": events,
        }
        payload.update(overrides)
        with patch(
            "services.generic_football_adapter.fetch_json",
            return_value=payload,
        ) as fetch_json:
            result = generic_football_adapter.get_match_events(
                MATCH_ID,
                competition_key="premier_league",
                season_key="2026-2027",
            )
        fetch_json.assert_called_once_with(
            f"/matches/{MATCH_ID}/events",
            required=True,
        )
        return result

    def test_goal_names_score_and_provider_ids_are_normalized(self):
        result = self.normalize([
            {
                "id": "mp_event_goal",
                "external_event_id": "992",
                "type": "goal",
                "minute": 44,
                "team_side": "home",
                "team_id": "mp_team_home",
                "external_team_id": "88",
                "player_name_fa": "گلزن",
                "secondary_player_name_fa": "پاسور",
                "home_score": 1,
                "away_score": 0,
                "raw": {"provider": "secret"},
            }
        ])

        self.assertEqual(
            set(result),
            {
                "competition_key",
                "season_key",
                "match_id",
                "count",
                "stale",
                "warnings",
                "events",
            },
        )
        event = result["events"][0]
        self.assertEqual(
            set(event),
            {
                "id",
                "type",
                "minute",
                "added_time",
                "display_minute",
                "team_side",
                "team_id",
                "player_name",
                "secondary_player_name",
                "assist_name",
                "player_in_name",
                "player_out_name",
                "home_score",
                "away_score",
                "description",
                "raw_type_label",
            },
        )
        self.assertEqual(event["id"], "mp_event_goal")
        self.assertEqual(event["type"], "goal")
        self.assertEqual(event["player_name"], "گلزن")
        self.assertEqual(event["secondary_player_name"], "پاسور")
        self.assertEqual(event["assist_name"], "پاسور")
        self.assertEqual(event["home_score"], 1)
        self.assertEqual(event["away_score"], 0)
        self.assertEqual(event["display_minute"], "44")
        self.assertEqual(event["added_time"], 0)
        serialized = str(result)
        self.assertNotIn("external_event_id", serialized)
        self.assertNotIn("external_match_id", serialized)
        self.assertNotIn("480301", serialized)
        self.assertNotIn("varzesh3", serialized)

    def test_supported_event_types_and_name_aliases(self):
        cases = (
            ("own_goal", "own_goal"),
            ("penalty goal", "penalty_goal"),
            ("missed_penalty", "missed_penalty"),
            ("yellow_card", "yellow_card"),
            ("second yellow red", "second_yellow_red"),
            ("red-card", "red_card"),
            ("substitution", "substitution"),
            ("var", "var"),
            ("goal_disallowed", "disallowed_goal"),
            ("halftime", "halftime"),
            ("full_time", "fulltime"),
            ("kick_off", "kickoff"),
            ("provider_special", "other"),
        )
        events = [
            {
                "id": f"mp_event_{index}",
                "type": source_type,
                "minute": index,
                "player_in_name_fa": "ورودی",
                "player_out_name_fa": "خروجی",
            }
            for index, (source_type, _) in enumerate(cases)
        ]

        result = self.normalize(events)

        self.assertEqual(
            [event["type"] for event in result["events"]],
            [expected_type for _, expected_type in cases],
        )
        self.assertEqual(result["events"][0]["player_in_name"], "ورودی")
        self.assertEqual(result["events"][0]["player_out_name"], "خروجی")

    def test_explicit_var_disallowed_goal_evidence_is_preserved(self):
        result = self.normalize([
            {
                "type": "var",
                "minute": 60,
                "description": "Goal disallowed after VAR review",
                "raw_type_label": "VAR review",
            }
        ])
        self.assertEqual(result["events"][0]["type"], "disallowed_goal")
        self.assertEqual(
            result["events"][0]["description"],
            "Goal disallowed after VAR review",
        )

    def test_added_time_and_same_minute_order_are_deterministic(self):
        result = self.normalize([
            {"id": "mp_event_late", "type": "goal", "display_minute": "45+2"},
            {"id": "mp_event_second", "type": "yellow_card", "minute": 45},
            {"id": "mp_event_first", "type": "red_card", "minute": 44},
            {"id": "mp_event_third", "type": "substitution", "minute": 45},
            {"id": "mp_event_latest", "type": "goal", "display_minute": "90+4"},
        ])

        self.assertEqual(
            [event["id"] for event in result["events"]],
            [
                "mp_event_first",
                "mp_event_second",
                "mp_event_third",
                "mp_event_late",
                "mp_event_latest",
            ],
        )
        late = result["events"][3]
        self.assertEqual((late["minute"], late["added_time"], late["display_minute"]), (45, 2, "45+2"))
        latest = result["events"][4]
        self.assertEqual((latest["minute"], latest["added_time"]), (90, 4))

    def test_display_minute_is_canonical_and_malformed_values_are_not_echoed(self):
        result = self.normalize([
            {"type": "goal", "minute": 45, "added_time": 2, "display_minute": "45 + 2'"},
            {"type": "yellow_card", "minute": 44, "display_minute": "private-label"},
        ])
        self.assertEqual(
            [event["display_minute"] for event in result["events"]],
            ["44", "45+2"],
        )

    def test_noncanonical_event_and_team_ids_are_not_exposed(self):
        result = self.normalize([
            {
                "id": 12345,
                "type": "yellow_card",
                "minute": 1,
                "team_id": "42",
            }
        ])
        self.assertIsNone(result["events"][0]["id"])
        self.assertIsNone(result["events"][0]["team_id"])

    def test_valid_empty_and_stale_payloads(self):
        empty = self.normalize([])
        self.assertEqual(empty["count"], 0)
        self.assertEqual(empty["events"], [])
        self.assertIs(empty["stale"], False)
        self.assertEqual(empty["warnings"], [])

        stale = self.normalize(
            [{"type": "goal", "minute": 1}],
            stale=True,
            warnings=["private upstream timeout detail"],
        )
        self.assertIs(stale["stale"], True)
        self.assertEqual(stale["warnings"], ["stale_events"])
        self.assertNotIn("private upstream timeout detail", str(stale))

    def test_inconsistent_wrapper_identity_fails(self):
        cases = (
            {"match_id": "mp_match_other"},
            {"competition_key": "la_liga"},
            {"season_key": "2027-2028"},
        )
        for override in cases:
            with self.subTest(override=override):
                with self.assertRaises(generic_football_adapter.GenericFootballProviderError):
                    self.normalize([], **override)


class GenericEventRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def request_with_scope(self, *, match=MATCH, events=None):
        if events is None:
            events = {
                "competition_key": "premier_league",
                "season_key": "2026-2027",
                "match_id": MATCH_ID,
                "count": 0,
                "stale": False,
                "warnings": [],
                "events": [],
            }
        with (
            patch("main.has_match_events_source_for_season", return_value=True),
            patch("main.get_match_for_season", return_value=match) as get_match,
            patch("main.get_match_events_for_season", return_value=events) as get_events,
        ):
            response = self.client.get(EVENT_PATH)
        return response, get_match, get_events

    def test_valid_scoped_match_is_resolved_before_event_fetch(self):
        response, get_match, get_events = self.request_with_scope()
        self.assertEqual(response.status_code, 200)
        get_match.assert_called_once_with("premier_league", "2026-2027", MATCH_ID)
        get_events.assert_called_once_with("premier_league", "2026-2027", MATCH_ID)

    def test_unknown_and_cross_scope_match_return_404_without_event_fetch(self):
        cases = (
            ("unknown", None),
            (
                "cross_competition",
                {**MATCH, "competition_key": "la_liga"},
            ),
            (
                "cross_season",
                {**MATCH, "season_key": "2027-2028"},
            ),
        )
        for label, match in cases:
            with self.subTest(label=label):
                response, _, get_events = self.request_with_scope(match=match)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Match not found"})
                get_events.assert_not_called()

    def test_inconsistent_normalized_event_envelope_fails_safely(self):
        response, _, _ = self.request_with_scope(
            events={
                "competition_key": "la_liga",
                "season_key": "2026-2027",
                "match_id": MATCH_ID,
                "count": 0,
                "stale": False,
                "warnings": [],
                "events": [],
            }
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Events provider unavailable"})

    def test_numeric_provider_id_cannot_substitute_for_canonical_id(self):
        path = (
            "/competitions/premier_league/seasons/2026-2027/"
            "matches/480301/events"
        )
        with (
            patch("main.has_match_events_source_for_season", return_value=True),
            patch("main.get_match_for_season") as get_match,
            patch("main.get_match_events_for_season") as get_events,
        ):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 404)
        get_match.assert_not_called()
        get_events.assert_not_called()

    def test_source_is_checked_before_match_resolution(self):
        with (
            patch("main.has_match_events_source_for_season", return_value=False),
            patch("main.get_match_for_season") as get_match,
        ):
            response = self.client.get(EVENT_PATH)
        self.assertEqual(response.status_code, 501)
        get_match.assert_not_called()

    def test_provider_failure_is_sanitized_502(self):
        private_error = competition_data_service.CompetitionDataProviderError(
            "private wrapper address"
        )
        with (
            patch("main.has_match_events_source_for_season", return_value=True),
            patch("main.get_match_for_season", return_value=MATCH),
            patch("main.get_match_events_for_season", side_effect=private_error),
        ):
            response = self.client.get(EVENT_PATH)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Events provider unavailable"})
        self.assertNotIn("private wrapper address", response.text)

    def test_match_list_loading_does_not_fetch_events(self):
        with (
            patch("main.get_matches_for_season", return_value=[]) as get_matches,
            patch("main.get_match_events_for_season") as get_events,
        ):
            response = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/matches"
            )
        self.assertEqual(response.status_code, 200)
        get_matches.assert_called_once()
        get_events.assert_not_called()

    def test_public_capability_stays_false(self):
        self.assertIs(get_competition("premier_league")["supports_events"], False)
        self.assertIs(get_competition("worldcup2026")["supports_events"], False)

    def test_legacy_worldcup_event_route_is_unchanged(self):
        payload = {"match_id": 75, "events": []}
        with patch("main.get_match_events", return_value=payload) as get_events:
            response = self.client.get("/matches/75/events")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        get_events.assert_called_once_with(75)


if __name__ == "__main__":
    unittest.main()
