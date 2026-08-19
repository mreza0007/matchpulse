import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import competition_data_service
import db_service
import main
from favorite_schema import favorite_teams_schema_state
from services import generic_football_adapter


WORLD_CUP_TEAM = {
    "id": 6,
    "name_en": "IR Iran",
    "name_fa": "ایران",
    "logo": None,
    "flag": "🇮🇷",
    "emoji": "🇮🇷",
}

PREMIER_LEAGUE_TEAM = {
    "id": "mp_team_1",
    "competition_key": "premier_league",
    "season_key": "2026-2027",
    "name_en": "Example Club",
    "name_fa": None,
    "logo": "https://example.invalid/club.png",
    "flag": "",
    "emoji": "",
}


class FavoritesV2ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "favorites.sqlite"
        self.db_patch = patch.object(db_service, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        db_service.init_db()
        main.favorite_teams.clear()
        self.client = TestClient(main.api)

    def provider_teams(self, competition_key):
        if competition_key == "worldcup2026":
            return [WORLD_CUP_TEAM]
        if competition_key == "premier_league":
            return [PREMIER_LEAGUE_TEAM]
        return []

    def post_favorite(self, competition_key, team_id, team):
        with (
            patch("main.get_team_for_competition", return_value=team),
            patch("favorite_service.get_teams_for_competition", side_effect=self.provider_teams),
        ):
            return self.client.post(
                "/favorite-team",
                json={
                    "telegram_id": 100,
                    "competition_key": competition_key,
                    "team_id": team_id,
                },
            )

    def test_add_world_cup_and_premier_league_favorites_with_trusted_metadata(self):
        world_cup = self.post_favorite("worldcup2026", 6, WORLD_CUP_TEAM)
        premier_league = self.post_favorite(
            "premier_league", "mp_team_1", PREMIER_LEAGUE_TEAM
        )

        self.assertEqual(world_cup.status_code, 200)
        self.assertEqual(world_cup.json()["favorite"]["team_type"], "national")
        self.assertEqual(world_cup.json()["favorite"]["team_name_en"], "IR Iran")
        self.assertNotIn("telegram_id", world_cup.json()["favorite"])
        self.assertEqual(premier_league.status_code, 200)
        self.assertEqual(premier_league.json()["favorite"]["team_type"], "club")
        self.assertEqual(
            premier_league.json()["favorite"]["team_logo"],
            "https://example.invalid/club.png",
        )

        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        rows = conn.execute(
            "SELECT competition_key, team_id, typeof(team_id) FROM favorite_teams ORDER BY id"
        ).fetchall()
        self.assertEqual(
            rows,
            [
                ("worldcup2026", "6", "text"),
                ("premier_league", "mp_team_1", "text"),
            ],
        )

    def test_same_team_id_across_competitions_and_duplicate_add_are_safe(self):
        shared_pl_team = {**PREMIER_LEAGUE_TEAM, "id": "6"}
        first = self.post_favorite("worldcup2026", 6, WORLD_CUP_TEAM)
        second = self.post_favorite("premier_league", "6", shared_pl_team)
        duplicate = self.post_favorite("worldcup2026", 6, WORLD_CUP_TEAM)

        self.assertTrue(first.json()["created"])
        self.assertTrue(second.json()["created"])
        self.assertFalse(duplicate.json()["created"])
        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM favorite_teams").fetchone()[0], 2)

    def test_unknown_competition_team_and_provider_failure_are_sanitized(self):
        unknown_competition = self.client.post(
            "/favorite-team",
            json={"telegram_id": 100, "competition_key": "unknown", "team_id": "1"},
        )
        self.assertEqual(unknown_competition.status_code, 404)

        with patch("main.get_team_for_competition", return_value=None):
            unknown_team = self.client.post(
                "/favorite-team",
                json={
                    "telegram_id": 100,
                    "competition_key": "premier_league",
                    "team_id": "missing",
                },
            )
        self.assertEqual(unknown_team.status_code, 404)

        with patch(
            "main.get_team_for_competition",
            side_effect=competition_data_service.CompetitionDataProviderError("private"),
        ):
            failed = self.client.post(
                "/favorite-team",
                json={
                    "telegram_id": 100,
                    "competition_key": "premier_league",
                    "team_id": "mp_team_1",
                },
            )
        self.assertEqual(failed.status_code, 502)
        self.assertEqual(failed.json(), {"detail": "Teams provider unavailable"})
        self.assertNotIn("private", failed.text)

    def test_scoped_requests_reject_client_display_identity(self):
        response = self.client.post(
            "/favorite-team",
            json={
                "telegram_id": 100,
                "competition_key": "premier_league",
                "team_id": "mp_team_1",
                "team_name": "Client controlled",
            },
        )
        self.assertEqual(response.status_code, 422)

        extra_field = self.client.post(
            "/favorite-team",
            json={
                "telegram_id": 100,
                "competition_key": "premier_league",
                "team_id": "mp_team_1",
                "team_logo": "https://client.invalid/logo.png",
            },
        )
        self.assertEqual(extra_field.status_code, 422)

    def test_legacy_numeric_world_cup_body_is_validated_and_mapped(self):
        with (
            patch("main.get_team_for_competition", return_value=WORLD_CUP_TEAM) as resolver,
            patch("favorite_service.get_teams_for_competition", return_value=[WORLD_CUP_TEAM]),
        ):
            response = self.client.post(
                "/favorite-team",
                json={
                    "telegram_id": 100,
                    "team_id": 6,
                    "team_key": "client-key",
                    "team_name": "Client name",
                    "name_en": "Client English",
                    "name_fa": "Client Persian",
                    "emoji": "X",
                },
            )

        self.assertEqual(response.status_code, 200)
        resolver.assert_called_once_with("worldcup2026", "6")
        favorite = response.json()["favorite"]
        self.assertEqual(favorite["competition_key"], "worldcup2026")
        self.assertEqual(favorite["team_name_en"], "IR Iran")
        self.assertNotEqual(favorite.get("emoji"), "X")

    def test_arbitrary_or_string_legacy_identity_is_rejected(self):
        with patch("main.get_team_for_competition", return_value=None):
            arbitrary = self.client.post(
                "/favorite-team",
                json={
                    "telegram_id": 100,
                    "team_id": 999,
                    "team_name": "Invented Team",
                },
            )
        self.assertEqual(arbitrary.status_code, 404)

        string_id = self.client.post(
            "/favorite-team",
            json={"telegram_id": 100, "team_id": "6"},
        )
        self.assertEqual(string_id.status_code, 422)

    def test_get_preserves_order_and_fetches_each_competition_once(self):
        db_service.save_favorite_team_v2_to_db(100, "worldcup2026", "6")
        db_service.save_favorite_team_v2_to_db(100, "worldcup2026", "7")
        db_service.save_favorite_team_v2_to_db(100, "premier_league", "mp_team_1")
        world_cup_second = {**WORLD_CUP_TEAM, "id": 7, "name_en": "Second National"}

        provider = Mock(
            side_effect=lambda key: (
                [WORLD_CUP_TEAM, world_cup_second]
                if key == "worldcup2026"
                else [PREMIER_LEAGUE_TEAM]
            )
        )
        with patch("favorite_service.get_teams_for_competition", provider):
            response = self.client.get("/favorite-teams/100")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [(item["competition_key"], item["team_id"]) for item in payload["favorite_teams"]],
            [
                ("worldcup2026", "6"),
                ("worldcup2026", "7"),
                ("premier_league", "mp_team_1"),
            ],
        )
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(payload["resolution_errors"], 0)
        self.assertEqual(payload["unresolved_count"], 0)

    def test_get_preserves_unresolved_and_partial_provider_failure(self):
        db_service.save_favorite_team_v2_to_db(100, "worldcup2026", "missing")
        db_service.save_favorite_team_v2_to_db(100, "premier_league", "mp_team_1")

        def provider(competition_key):
            if competition_key == "worldcup2026":
                return []
            raise competition_data_service.CompetitionDataProviderError("private")

        with patch("favorite_service.get_teams_for_competition", side_effect=provider):
            response = self.client.get("/favorite-teams/100")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["resolution_errors"], 1)
        self.assertEqual(payload["unresolved_count"], 2)
        self.assertTrue(all(item["resolved"] is False for item in payload["favorite_teams"]))
        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM favorite_teams").fetchone()[0], 2)

    def test_delete_is_exact_scoped_and_idempotent(self):
        db_service.save_favorite_team_v2_to_db(100, "worldcup2026", "6")
        db_service.save_favorite_team_v2_to_db(100, "premier_league", "6")
        with patch("favorite_service.get_teams_for_competition", return_value=[]):
            deleted = self.client.request(
                "DELETE",
                "/favorite-team",
                json={
                    "telegram_id": 100,
                    "competition_key": "worldcup2026",
                    "team_id": "6",
                },
            )
            repeated = self.client.request(
                "DELETE",
                "/favorite-team",
                json={
                    "telegram_id": 100,
                    "competition_key": "worldcup2026",
                    "team_id": "6",
                },
            )

        self.assertTrue(deleted.json()["deleted"])
        self.assertFalse(repeated.json()["deleted"])
        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertEqual(
            conn.execute(
                "SELECT competition_key FROM favorite_teams"
            ).fetchall(),
            [("premier_league",)],
        )

    def test_legacy_schema_fails_safely_without_migration(self):
        self.db_path.unlink()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE favorite_teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                team_id INTEGER,
                team_key TEXT,
                team_name TEXT,
                team_data TEXT,
                UNIQUE(telegram_id, team_id)
            )
            """
        )
        conn.commit()
        conn.close()

        response = self.client.get("/favorite-teams/100")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Favorites V2 migration required"})
        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertEqual(favorite_teams_schema_state(conn), "legacy")
        self.assertFalse(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='favorite_teams_legacy'"
            ).fetchone()
        )


class GenericTeamProviderSemanticsTests(unittest.TestCase):
    @patch("services.generic_football_adapter.requests.get")
    def test_valid_empty_team_list_is_successful(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"teams": []}
        get.return_value = response
        self.assertEqual(
            generic_football_adapter.get_season_teams("premier_league", "2026-2027"),
            [],
        )

    @patch("services.generic_football_adapter.requests.get")
    def test_timeout_non_2xx_and_malformed_payload_are_provider_errors(self, get):
        timeout = generic_football_adapter.requests.Timeout("private timeout")
        non_2xx = Mock()
        non_2xx.raise_for_status.side_effect = generic_football_adapter.requests.HTTPError(
            "private upstream"
        )
        malformed = Mock()
        malformed.raise_for_status.return_value = None
        malformed.json.return_value = {"items": []}

        for configured in (timeout, non_2xx, malformed):
            with self.subTest(configured=type(configured).__name__):
                if isinstance(configured, Exception):
                    get.side_effect = configured
                    get.return_value = None
                else:
                    get.side_effect = None
                    get.return_value = configured
                with self.assertRaises(generic_football_adapter.GenericFootballProviderError):
                    generic_football_adapter.get_season_teams(
                        "premier_league", "2026-2027"
                    )


if __name__ == "__main__":
    unittest.main()
