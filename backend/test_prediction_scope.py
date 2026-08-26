import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from competition_service import get_competition
from prediction_scope_service import select_prediction_scope_matches


NOW = 1_000.0


def match_fixture(match_id, scope_value, kickoff=1_100.0, **overrides):
    match = {
        "id": match_id,
        "competition_key": "premier_league",
        "season_key": "2026-2027",
        "home_en": "Home",
        "away_en": "Away",
        "round": scope_value,
        "stage": scope_value,
        "status": "upcoming",
        "is_upcoming": True,
        "is_live": False,
        "is_finished": False,
        "kickoff_ts": kickoff,
    }
    match.update(overrides)
    return match


def finished_match(match_id, scope_value, kickoff=900.0):
    return match_fixture(
        match_id,
        scope_value,
        kickoff,
        status="finished",
        is_upcoming=False,
        is_finished=True,
    )


class PredictionScopeSelectorTests(unittest.TestCase):
    def setUp(self):
        self.league = get_competition("premier_league")
        self.tournament = get_competition("champions_league")

    def select(self, competition, matches):
        return select_prediction_scope_matches(competition, matches, NOW)

    def test_league_exposes_only_actual_next_round(self):
        matches = [
            finished_match("played", "هفته 2"),
            match_fixture("next-a", "هفته 3", 1_100),
            match_fixture("next-b", "هفته 3", 1_200),
            match_fixture("later", "هفته 4", 1_300),
        ]

        self.assertEqual(
            [match["id"] for match in self.select(self.league, matches)],
            ["next-a", "next-b"],
        )

    def test_skipped_round_numbers_and_persian_digits_are_not_incremented_blindly(self):
        matches = [
            finished_match("played", "هفته ۲"),
            match_fixture("missing-round", None, 1_050),
            match_fixture("actual-next", "هفته ۴", 1_100),
            match_fixture("later", "هفته ۷", 1_200),
        ]

        self.assertEqual(
            [match["id"] for match in self.select(self.league, matches)],
            ["actual-next"],
        )

    def test_postponed_match_from_older_round_does_not_reopen_that_round(self):
        matches = [
            finished_match("older-round-played", "هفته 3", 850),
            finished_match("played", "هفته 4"),
            match_fixture("postponed", "هفته 3", 1_050),
            match_fixture("next", "هفته 5", 1_100),
        ]

        self.assertEqual(
            [match["id"] for match in self.select(self.league, matches)],
            ["next"],
        )

    def test_early_later_round_match_does_not_skip_nearer_playable_round(self):
        matches = [
            finished_match("played", "هفته 2"),
            match_fixture("nearer", "هفته 3", 1_100),
            finished_match("early-later", "هفته 10"),
            match_fixture("rest-of-later", "هفته 10", 2_000),
        ]

        self.assertEqual(
            [match["id"] for match in self.select(self.league, matches)],
            ["nearer"],
        )

    def test_no_future_round_returns_empty(self):
        self.assertEqual(
            self.select(self.league, [finished_match("played", "هفته 4")]),
            [],
        )

    def test_missing_kickoff_in_next_round_is_excluded_without_exposing_later_round(self):
        matches = [
            finished_match("played", "هفته 3"),
            match_fixture("missing-kickoff", "هفته 4", None),
            match_fixture("later", "هفته 5", 1_200),
        ]

        self.assertEqual(self.select(self.league, matches), [])

    def test_match_whose_kickoff_has_started_is_excluded(self):
        matches = [
            finished_match("played", "هفته 3"),
            match_fixture("started", "هفته 4", NOW),
            match_fixture("later", "هفته 5", 1_200),
        ]

        self.assertEqual(self.select(self.league, matches), [])

    def test_knockout_exposes_only_next_provider_stage(self):
        matches = [
            match_fixture("quarterfinal-a", "یک چهارم نهایی", 1_100),
            match_fixture("quarterfinal-b", "یک چهارم نهایی", 1_150),
            match_fixture("semifinal", "نیمه نهایی", 1_300),
        ]

        self.assertEqual(
            [match["id"] for match in self.select(self.tournament, matches)],
            ["quarterfinal-a", "quarterfinal-b"],
        )

    def test_multiple_future_knockout_stages_do_not_leak_later_stage(self):
        matches = [
            match_fixture("final", "final", 1_500),
            match_fixture("qualifying", "مقدماتی", 1_100),
            match_fixture("semifinal", "semifinal", 1_300),
        ]

        self.assertEqual(
            [match["id"] for match in self.select(self.tournament, matches)],
            ["qualifying"],
        )

    def test_active_competitions_advertise_explicit_scope_types(self):
        expected = {
            "premier_league": "league_next_round",
            "persian_gulf_pro_league": "league_next_round",
            "la_liga": "league_next_round",
            "serie_a": "league_next_round",
            "bundesliga": "league_next_round",
            "ligue_1": "league_next_round",
            "champions_league": "knockout_next_stage",
            "europa_league": "knockout_next_stage",
        }
        self.assertEqual(
            {key: get_competition(key)["prediction_scope"] for key in expected},
            expected,
        )

    def test_worldcup_archival_capabilities_and_history_remain_unchanged(self):
        worldcup = get_competition("worldcup2026")
        self.assertIs(worldcup["supports_predictions"], False)
        self.assertEqual(worldcup["status"], "archived")
        self.assertIs(
            main.prediction_scope_supports_evaluation(
                {"competition_key": "worldcup2026", "season_key": "2026"}
            ),
            True,
        )


class PredictionScopeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def future_match(self, match_id, round_value):
        import time

        return match_fixture(match_id, round_value, time.time() + 3_600)

    def prediction_body(self, match_id):
        return {
            "telegram_id": 100,
            "competition_key": "premier_league",
            "season_key": "2026-2027",
            "match_id": match_id,
            "prediction_type": "result",
            "predicted_result": "home",
        }

    def test_endpoint_and_post_share_the_same_scope_decision(self):
        next_match = self.future_match("next", "هفته 4")
        later_match = self.future_match("later", "هفته 6")
        matches = [next_match, later_match]

        with (
            patch("main.get_prediction_matches_for_season", return_value=matches),
            patch("main.save_prediction_v2") as save_prediction,
            patch("main.get_user_predictions_v2", return_value=[]),
        ):
            listing = self.client.get(
                "/competitions/premier_league/seasons/2026-2027/predictable-matches"
            )
            rejected = self.client.post("/prediction", json=self.prediction_body("later"))
            accepted = self.client.post("/prediction", json=self.prediction_body("next"))

        self.assertEqual([match["id"] for match in listing.json()["matches"]], ["next"])
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(
            rejected.json(),
            {"detail": "Match is outside the current prediction scope"},
        )
        self.assertEqual(accepted.status_code, 200)
        save_prediction.assert_called_once()

    def test_worldcup_predictable_endpoint_remains_blocked_before_provider(self):
        with patch("main.get_prediction_matches_for_season") as provider:
            response = self.client.get(
                "/competitions/worldcup2026/seasons/2026/predictable-matches"
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(
            response.json(),
            {"detail": "Competition predictions not supported"},
        )
        provider.assert_not_called()

