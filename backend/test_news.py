import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
import db_service
from data import NEWS
from favorite_schema import favorite_teams_schema_state
from news_service import filter_news, filter_news_for_favorites


class NewsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.api)

    def test_news_returns_structured_static_items_with_stable_ids(self):
        response = self.client.get("/news")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], len(NEWS))
        self.assertEqual([item["id"] for item in payload["news"]], [1, 2])

        for item in payload["news"]:
            self.assertIn(item["category"], {"iran", "world", "national", "transfers"})
            self.assertIsInstance(item["related_team_ids"], list)
            self.assertIsInstance(item["related_competition_keys"], list)
            self.assertIsInstance(item["related_teams"], list)
            self.assertIn("title_fa", item)
            self.assertIn("title_en", item)

    def test_explicit_category_and_relations_are_preserved(self):
        response = self.client.get("/news")

        for item in response.json()["news"]:
            self.assertEqual(item["category"], "world")
            self.assertEqual(item["related_team_ids"], [])
            self.assertEqual(item["related_competition_keys"], ["worldcup2026"])
            self.assertEqual(item["related_teams"], [])

    def test_category_filter_uses_explicit_metadata(self):
        world = self.client.get("/news?category=world")
        iran = self.client.get("/news?category=iran")

        self.assertEqual(world.status_code, 200)
        self.assertEqual(world.json()["count"], 2)
        self.assertEqual(iran.status_code, 200)
        self.assertEqual(iran.json(), {"count": 0, "news": []})

    def test_competition_and_team_filters(self):
        worldcup = self.client.get("/news?competition_key=worldcup2026")
        unknown_competition = self.client.get("/news?competition_key=unknown")
        unscoped_team = self.client.get("/news?team_id=999")
        explicitly_related = [
            {
                "id": "manual-team-relation",
                "category": "national",
                "related_team_ids": [6],
                "related_competition_keys": [],
                "related_teams": [
                    {"competition_key": "worldcup2026", "team_id": "6"}
                ],
            }
        ]

        self.assertEqual(worldcup.json()["count"], 2)
        self.assertEqual(unknown_competition.json(), {"count": 0, "news": []})
        self.assertEqual(unscoped_team.status_code, 422)
        self.assertEqual(
            unscoped_team.json(),
            {"detail": "competition_key is required with team_id"},
        )
        with patch.object(main, "NEWS", explicitly_related):
            scoped = self.client.get(
                "/news?competition_key=worldcup2026&team_id=6"
            )
        self.assertEqual(scoped.status_code, 200)
        self.assertEqual(scoped.json(), {"count": 1, "news": explicitly_related})
        self.assertEqual(
            filter_news(
                explicitly_related,
                competition_key="worldcup2026",
                team_id="6",
            ),
            explicitly_related,
        )
        self.assertEqual(
            filter_news(
                explicitly_related,
                competition_key="premier_league",
                team_id="6",
            ),
            [],
        )

    def test_invalid_category_returns_validation_error(self):
        response = self.client.get("/news?category=other")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"detail": "Invalid news category"})

    def test_titles_do_not_drive_category_classification(self):
        items = [
            {
                "id": "manual-1",
                "title_en": "World transfer news",
                "category": "iran",
                "related_team_ids": [],
                "related_competition_keys": [],
                "related_teams": [],
            }
        ]

        self.assertEqual(filter_news(items, category="iran"), items)
        self.assertEqual(filter_news(items, category="world"), [])
        self.assertEqual(filter_news(items, category="transfers"), [])

    def test_legacy_response_and_item_fields_remain_available(self):
        response = self.client.get("/news")
        item = response.json()["news"][0]

        self.assertEqual(set(response.json()), {"count", "news"})
        self.assertEqual(item["tag_fa"], NEWS[0]["tag_fa"])
        self.assertEqual(item["tag_en"], NEWS[0]["tag_en"])
        self.assertEqual(item["title_fa"], NEWS[0]["title_fa"])
        self.assertEqual(item["title_en"], NEWS[0]["title_en"])


class FavoriteNewsRouteTests(unittest.TestCase):
    NEWS_ITEMS = [
        {
            "id": "pl",
            "category": "world",
            "related_teams": [
                {"competition_key": "premier_league", "team_id": "mp_team_1"}
            ],
            "related_team_ids": ["mp_team_1"],
            "related_competition_keys": ["premier_league"],
        },
        {
            "id": "national",
            "category": "national",
            "related_teams": [
                {"competition_key": "worldcup2026", "team_id": "6"}
            ],
            "related_team_ids": [6],
            "related_competition_keys": ["worldcup2026"],
        },
        {
            "id": "both",
            "category": "world",
            "related_teams": [
                {"competition_key": "premier_league", "team_id": "mp_team_1"},
                {"competition_key": "worldcup2026", "team_id": "6"},
            ],
            "related_team_ids": ["mp_team_1", 6],
            "related_competition_keys": ["premier_league", "worldcup2026"],
        },
        {
            "id": "both",
            "category": "world",
            "related_teams": [
                {"competition_key": "worldcup2026", "team_id": "6"}
            ],
            "related_team_ids": [6],
            "related_competition_keys": ["worldcup2026"],
        },
        {
            "id": "unrelated",
            "category": "world",
            "related_teams": [],
            "related_team_ids": [],
            "related_competition_keys": [],
        },
    ]

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "news.sqlite"
        self.db_patch = patch.object(db_service, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        db_service.init_db()
        self.news_patch = patch.object(main, "NEWS", self.NEWS_ITEMS)
        self.news_patch.start()
        self.addCleanup(self.news_patch.stop)
        self.client = TestClient(main.api)

    def add_favorite(self, competition_key, team_id, telegram_id=100):
        db_service.save_favorite_team_v2_to_db(
            telegram_id, competition_key, team_id
        )

    def test_zero_favorites_and_unmatched_favorites_return_empty_feed(self):
        empty = self.client.get("/news/favorites/100")
        self.add_favorite("premier_league", "missing")
        unmatched = self.client.get("/news/favorites/100")

        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json(), {"count": 0, "news": []})
        self.assertEqual(unmatched.status_code, 200)
        self.assertEqual(unmatched.json(), {"count": 0, "news": []})

    def test_premier_league_and_national_favorites_match_exact_scope(self):
        self.add_favorite("premier_league", "mp_team_1")
        premier_league = self.client.get("/news/favorites/100")

        self.assertEqual(
            [item["id"] for item in premier_league.json()["news"]],
            ["pl", "both"],
        )

        db_service.delete_favorite_team_v2_from_db(
            100, "premier_league", "mp_team_1"
        )
        self.add_favorite("worldcup2026", "6")
        national = self.client.get("/news/favorites/100")

        self.assertEqual(
            [item["id"] for item in national.json()["news"]],
            ["national", "both"],
        )

    def test_same_team_id_in_different_competition_does_not_match(self):
        items = [
            {
                "id": "collision",
                "category": "world",
                "related_teams": [
                    {"competition_key": "worldcup2026", "team_id": "6"}
                ],
            },
            {
                "id": "legacy-only",
                "category": "world",
                "related_teams": [],
                "related_team_ids": ["6"],
                "team_key": "matching-name-is-not-identity",
            },
        ]

        self.assertEqual(
            filter_news_for_favorites(
                items,
                [{"competition_key": "premier_league", "team_id": "6"}],
            ),
            [],
        )

    def test_multiple_favorites_deduplicate_and_preserve_source_order(self):
        self.add_favorite("premier_league", "mp_team_1")
        self.add_favorite("worldcup2026", "6")

        response = self.client.get("/news/favorites/100")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.json()["news"]],
            ["pl", "national", "both"],
        )

    def test_category_filter_uses_and_semantics(self):
        self.add_favorite("premier_league", "mp_team_1")
        self.add_favorite("worldcup2026", "6")

        world = self.client.get("/news/favorites/100?category=world")
        invalid = self.client.get("/news/favorites/100?category=other")

        self.assertEqual(
            [item["id"] for item in world.json()["news"]],
            ["pl", "both"],
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json(), {"detail": "Invalid news category"})

    def test_feed_is_private_and_does_not_call_team_provider(self):
        self.add_favorite("premier_league", "mp_team_1")

        with patch(
            "favorite_service.get_teams_for_competition"
        ) as team_provider:
            response = self.client.get("/news/favorites/100")

        self.assertEqual(response.status_code, 200)
        team_provider.assert_not_called()
        for item in response.json()["news"]:
            self.assertNotIn("telegram_id", item)
            self.assertNotIn("favorites", item)

    def test_invalid_telegram_id_is_rejected(self):
        response = self.client.get("/news/favorites/0")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Invalid telegram_id"})

    def test_legacy_schema_returns_safe_503_without_migration(self):
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

        response = self.client.get("/news/favorites/100")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Favorites V2 migration required"})
        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertEqual(favorite_teams_schema_state(conn), "legacy")


if __name__ == "__main__":
    unittest.main()
