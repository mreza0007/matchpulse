import unittest

from fastapi.testclient import TestClient

import main
from data import NEWS
from news_service import filter_news


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
            self.assertIn("title_fa", item)
            self.assertIn("title_en", item)

    def test_explicit_category_and_relations_are_preserved(self):
        response = self.client.get("/news")

        for item in response.json()["news"]:
            self.assertEqual(item["category"], "world")
            self.assertEqual(item["related_team_ids"], [])
            self.assertEqual(item["related_competition_keys"], ["worldcup2026"])

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
        unknown_team = self.client.get("/news?team_id=999")
        explicitly_related = [
            {
                "id": "manual-team-relation",
                "category": "national",
                "related_team_ids": [6],
                "related_competition_keys": [],
            }
        ]

        self.assertEqual(worldcup.json()["count"], 2)
        self.assertEqual(unknown_competition.json(), {"count": 0, "news": []})
        self.assertEqual(unknown_team.json(), {"count": 0, "news": []})
        self.assertEqual(filter_news(explicitly_related, team_id="6"), explicitly_related)

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


if __name__ == "__main__":
    unittest.main()
