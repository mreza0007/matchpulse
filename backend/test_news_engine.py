"""Fixture-only tests: no publishers, Telegram, secrets or application DB."""
from dataclasses import replace
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from migrations.news_v1 import inspect_news_database, migrate_news_v1
from news_http import FeedResponse, PublicHTTPS, fetch_feed
from news_ingestion import poll_source, register_news_job
from news_parser import parse_feed
from news_schema import DDL, news_schema_state
from news_service import query_news
from news_sources import NewsSource, TeamMapping, approved_sources, safe_url
from news_store import NewsStorageError, connect, read_articles

NOW = datetime(2026, 10, 25, 10, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent / "test_fixtures/news/sample.rss"


def source(**changes):
    config = NewsSource(" Fixture ", "Test fixture", "https://news.example.invalid/feed",
        ("news.example.invalid",), ("news.example.invalid",), enabled=True,
        commercial_metadata_approved=True, approval_reference="TEST ONLY permission",
        reviewed_by="fixture reviewer", approval_expires_at="2099-01-01T00:00:00Z",
        team_domain="fixture-teams", mapping_review_reference="fixture reviewed identities",
        team_mappings=(TeamMapping("club-1", (("premier_league", "mp_team_test"),)),))
    return replace(config, **changes)


class NewsEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.sqlite"
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("CREATE TABLE sentinel(value TEXT)")
            conn.execute("INSERT INTO sentinel VALUES ('preserved')")
        migrate_news_v1(self.path, backup_confirmed=True)
        self.source = source()
        self.body = FIXTURE.read_bytes()

    def ingest(self, source_config=None, body=None, now=NOW):
        return poll_source(source_config or self.source, path=self.path, now=now,
            fetcher=Mock(return_value=FeedResponse(200, self.body if body is None else body, '"fixture"')))

    def rows(self, **kwargs):
        return read_articles({self.source.source_key: self.source}, path=self.path, **kwargs)

    def test_migration_is_additive_and_idempotent(self):
        self.assertEqual(migrate_news_v1(self.path, backup_confirmed=True), {"action": "unchanged"})
        with closing(sqlite3.connect(self.path)) as conn, conn:
            self.assertEqual(conn.execute("SELECT value FROM sentinel").fetchone()[0], "preserved")
            self.assertEqual(news_schema_state(conn), "v1")

    def test_migration_requires_backup_confirmation(self):
        with self.assertRaises(ValueError):
            migrate_news_v1(self.path)

    def test_migration_rejects_marker_drift(self):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("DROP INDEX news_articles_order")
        with self.assertRaises(ValueError):
            migrate_news_v1(self.path, backup_confirmed=True)

    def test_failed_migration_rolls_back_all_ddl(self):
        fresh = Path(self.temp.name) / "fresh.sqlite"
        sqlite3.connect(fresh).close()
        with patch("migrations.news_v1.DDL", (*DDL, "INVALID SQL")):
            with self.assertRaises(sqlite3.Error):
                migrate_news_v1(fresh, backup_confirmed=True)
        self.assertEqual(inspect_news_database(fresh), {"news_schema": "missing"})

    def test_runtime_does_not_create_or_migrate(self):
        absent = Path(self.temp.name) / "absent.sqlite"
        with self.assertRaises(NewsStorageError):
            connect(absent)
        self.assertFalse(absent.exists())
        legacy = Path(self.temp.name) / "legacy.sqlite"
        sqlite3.connect(legacy).close()
        with self.assertRaises(NewsStorageError):
            connect(legacy)
        self.assertEqual(inspect_news_database(legacy)["news_schema"], "missing")

    def test_persistence_metadata_and_restart(self):
        self.assertEqual(self.ingest(), "updated")
        first = self.rows()[0]
        self.assertEqual(first["origin"], "publisher")
        self.assertIsNone(first["summary"])
        self.assertIsNone(first["image_url"])
        self.assertEqual(first["related_teams"], [{"competition_key": "premier_league", "team_id": "mp_team_test"}])
        self.assertEqual(self.rows()[0], first)
        self.assertEqual(self.ingest(), "not_due")

    def test_guid_and_url_deduplication(self):
        self.ingest()
        first = self.rows()[0]
        changed = self.body.replace(b"utm_source=test", b"utm_source=other")
        self.ingest(body=changed, now=NOW + timedelta(hours=1))
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["id"], first["id"])
        self.assertEqual(self.rows()[0]["ingested_at"], first["ingested_at"])

    def test_old_url_alias_is_preserved(self):
        self.ingest()
        self.ingest(body=self.body.replace(b"articles/one", b"articles/new"), now=NOW + timedelta(hours=1))
        self.ingest(body=self.body.replace(b"fixture-1", b"fixture-other"), now=NOW + timedelta(hours=2))
        self.assertEqual(len(self.rows()), 1)

    def test_cross_source_url_dedup_does_not_replace_provenance(self):
        self.ingest()
        self.ingest(source(key="other", summary_approved=True))
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["source_key"], "fixture")

    def test_filters_and_bounded_ordered_pages(self):
        self.ingest()
        self.assertEqual(len(self.rows(competition_key="premier_league", team_id="mp_team_test")), 1)
        self.assertEqual(self.rows(competition_key="la_liga", team_id="mp_team_test"), [])
        self.assertEqual(self.rows(category="iran"), [])
        self.assertEqual(self.rows(offset=1), [])
        self.assertEqual(len(self.rows(favorites=[{"competition_key": "premier_league", "team_id": "mp_team_test"}])), 1)
        self.assertEqual(self.rows(favorites=[{"competition_key": "la_liga", "team_id": "mp_team_test"}]), [])

    def test_304_uses_persisted_conditional_headers(self):
        self.ingest()
        fetcher = Mock(return_value=FeedResponse(304))
        self.assertEqual(poll_source(self.source, path=self.path, now=NOW + timedelta(hours=1), fetcher=fetcher), "unchanged")
        fetcher.assert_called_once_with(self.source, '"fixture"', None)
        self.assertEqual(len(self.rows()), 1)

    def test_failure_backoff_preserves_articles_and_recovers(self):
        self.ingest()
        failed = Mock(side_effect=RuntimeError("private publisher diagnostic"))
        later = NOW + timedelta(hours=1)
        self.assertEqual(poll_source(self.source, path=self.path, now=later, fetcher=failed), "failed")
        self.assertEqual(poll_source(self.source, path=self.path, now=later, fetcher=failed), "not_due")
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.ingest(now=later + timedelta(minutes=2)), "updated")
        conn = connect(self.path)
        self.addCleanup(conn.close)
        self.assertIsNone(conn.execute("SELECT last_error_code FROM news_source_state").fetchone()[0])

    def test_lease_prevents_overlap_and_recovers_after_restart(self):
        self.ingest()
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("UPDATE news_source_state SET lease_until='2026-10-25T12:00:00Z',lease_token='old'")
        self.assertEqual(self.ingest(now=NOW + timedelta(hours=1)), "busy")
        self.assertEqual(self.ingest(now=NOW + timedelta(hours=3)), "updated")

    def test_changed_mapping_forces_unconditional_refresh(self):
        self.ingest()
        changed = replace(self.source, team_mappings=())
        fetcher = Mock(return_value=FeedResponse(200, self.body))
        self.assertEqual(poll_source(changed, path=self.path, now=NOW, fetcher=fetcher), "updated")
        fetcher.assert_called_once_with(changed, None, None)
        self.assertEqual(self.rows()[0]["related_teams"], [])

    def test_default_disabled_and_expired_sources_never_fetch(self):
        fetcher = Mock()
        for config in (source(enabled=False), source(commercial_metadata_approved=False),
                       source(approval_expires_at="2020-01-01T00:00:00Z")):
            self.assertEqual(poll_source(config, path=self.path, fetcher=fetcher, now=NOW), "disabled")
        fetcher.assert_not_called()

    def test_summary_and_image_require_separate_approval(self):
        config = source(summary_approved=True, image_approved=True, image_hosts=("news.example.invalid",))
        body = self.body.replace(b"</item>", b'<enclosure type="image/png" url="https://news.example.invalid/pic.png"/></item>')
        self.ingest(config, body)
        approved = read_articles({"fixture": config}, path=self.path)[0]
        self.assertEqual(approved["summary"], "Permitted fixture summary")
        self.assertTrue(approved["image_url"].endswith("pic.png"))
        self.assertIsNone(self.rows()[0]["summary"])
        self.assertIsNone(self.rows()[0]["image_url"])

    def test_unknown_team_not_guessed_and_mapping_review_required(self):
        with self.assertRaises(ValueError):
            source(mapping_review_reference="").validate()
        self.ingest(body=self.body.replace(b"club-1", b"unknown"))
        self.assertEqual(self.rows()[0]["related_teams"], [])

    def test_xml_security_and_malformed_payload(self):
        for body in (b'<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>', b"<rss>", b"<html/>", b"\x00<rss/>", b"a" * (1024 * 1024 + 1)):
            with self.assertRaises((ValueError, SyntaxError)):
                parse_feed(self.source, body, NOW)

    def test_missing_and_future_dates_are_not_fabricated(self):
        for date in (b"", b"Mon, 25 Oct 2099 09:00:00 GMT"):
            self.assertEqual(parse_feed(self.source, self.body.replace(b"Sun, 25 Oct 2026 09:00:00 GMT", date), NOW), [])

    def test_json_metadata_adapter_ignores_body(self):
        body = json.dumps({"items": [{"id": "json-1", "url": "https://news.example.invalid/json",
            "title": "Metadata", "date_published": "2026-10-25T09:00:00Z", "content_html": "PRIVATE BODY"}]}).encode()
        items = parse_feed(source(format="json"), body, NOW)
        self.assertEqual(items[0]["headline"], "Metadata")
        self.assertNotIn("PRIVATE BODY", str(items))

    def test_url_allowlist_and_canonicalization(self):
        self.assertEqual(safe_url("https://news.example.invalid/a?utm_medium=x&id=2#fragment",
            self.source.article_hosts, canonical=True), "https://news.example.invalid/a?id=2")
        for url in ("http://news.example.invalid/feed", "https://other.invalid/feed", "https://user@news.example.invalid/feed"):
            with self.assertRaises(ValueError):
                safe_url(url, self.source.feed_hosts)

    def test_transport_rejects_private_dns_before_connect(self):
        with patch("news_http.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                PublicHTTPS("news.example.invalid").connect()

    def test_redirect_cannot_escape_allowlist(self):
        response = Mock(status=302)
        response.getheader.return_value = "https://private.invalid/feed"
        with patch("news_http.PublicHTTPS") as transport:
            transport.return_value.getresponse.return_value = response
            with self.assertRaises(ValueError):
                fetch_feed(self.source)
            self.assertEqual(transport.call_count, 1)

    def test_unapproved_registry_and_scheduler_default_empty(self):
        self.assertEqual(approved_sources(), {})
        scheduler = Mock()
        register_news_job(scheduler)
        scheduler.add_job.assert_not_called()
        with patch("news_sources.NEWS_SOURCES", (source(enabled=False), source(key="fixture"))):
            with self.assertRaises(ValueError):
                approved_sources(NOW)

    def test_static_fallback_and_pagination_contract(self):
        notices = [{"id": 1, "origin": "static_notice", "category": "world"}, {"id": 2, "category": "world"}]
        self.assertEqual(query_news(notices, limit=1, offset=1), [notices[1]])
        with self.assertRaises(ValueError):
            query_news(notices, limit=101)

    def test_api_reads_persisted_articles_and_paginates(self):
        import db_service
        import main
        from fastapi.testclient import TestClient
        self.ingest()
        with patch.object(db_service, "DB_PATH", self.path), patch("news_sources.NEWS_SOURCES", (self.source,)):
            client = TestClient(main.api)
            response = client.get("/news", params={"competition_key": "premier_league", "team_id": "mp_team_test"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(set(response.json()), {"count", "news"})
            self.assertEqual(response.json()["count"], 1)
            self.assertEqual(client.get("/news?offset=1").json()["count"], 0)
            self.assertEqual(client.get("/news?limit=101").status_code, 422)
            self.assertEqual(client.get("/news?team_id=mp_team_test").status_code, 422)

    def test_api_storage_failure_is_sanitized(self):
        import main
        from fastapi.testclient import TestClient
        with patch("news_sources.NEWS_SOURCES", (self.source,)), patch(
                "news_store.connect", side_effect=sqlite3.OperationalError("PRIVATE SQL PATH")):
            response = TestClient(main.api).get("/news")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("PRIVATE", response.text)

    def test_expired_source_is_not_served(self):
        import db_service
        self.ingest()
        with patch.object(db_service, "DB_PATH", self.path), patch("news_sources.NEWS_SOURCES", (
                source(approval_expires_at="2020-01-01T00:00:00Z"),)):
            self.assertEqual(query_news([]), [])
        self.assertEqual(len(self.rows()), 1)  # Retained, not destructively cleaned up.

    def test_conflicting_aliases_roll_back_entire_poll(self):
        self.ingest()
        second = self.body.replace(b"fixture-1", b"fixture-2").replace(b"articles/one", b"articles/two")
        self.ingest(body=second, now=NOW + timedelta(hours=1))
        conflict = self.body.replace(b"articles/one", b"articles/two")
        self.assertEqual(self.ingest(body=conflict, now=NOW + timedelta(hours=2)), "failed")
        self.assertEqual(len(self.rows()), 2)

    def test_guid_is_not_truncated_into_colliding_identity(self):
        body = self.body.replace(b"fixture-1", b"x" * 1025)
        self.assertEqual(parse_feed(self.source, body, NOW), [])

    def test_transport_size_encoding_and_type_limits(self):
        for mime, encoding, chunks in (("text/html", "identity", []),
                ("application/rss+xml", "gzip", []),
                ("application/rss+xml", "identity", [b"x" * (1024 * 1024 + 1)])):
            response = Mock(status=200)
            response.getheader.side_effect = lambda name, default=None: {
                "Content-Type": mime, "Content-Encoding": encoding}.get(name, default)
            response.read1.side_effect = chunks
            with patch("news_http.PublicHTTPS") as transport:
                transport.return_value.getresponse.return_value = response
                with self.assertRaises(ValueError):
                    fetch_feed(self.source)
                transport.return_value.close.assert_called_once()

    def test_retry_after_is_bounded_and_persistent(self):
        fetcher = Mock(return_value=FeedResponse(429, retry_after=999999))
        self.assertEqual(poll_source(self.source, path=self.path, now=NOW, fetcher=fetcher), "failed")
        self.assertEqual(poll_source(self.source, path=self.path, now=NOW + timedelta(hours=5), fetcher=fetcher), "not_due")

    def test_successful_poll_and_cursor_commit_are_atomic(self):
        with patch("news_ingestion.save_articles", side_effect=sqlite3.OperationalError("fixture write failure")):
            self.assertEqual(self.ingest(), "failed")
        self.assertIsNone(self.rows())
        conn = connect(self.path)
        self.addCleanup(conn.close)
        row = conn.execute("SELECT etag,failure_count FROM news_source_state").fetchone()
        self.assertIsNone(row[0])
        self.assertEqual(row[1], 1)

    def test_job_is_ingestion_only_and_coalesced(self):
        scheduler = Mock()
        with patch("news_ingestion.approved_sources", return_value={"fixture": self.source}):
            register_news_job(scheduler)
        kwargs = scheduler.add_job.call_args.kwargs
        self.assertEqual(kwargs["id"], "matchpulse_news_ingestion")
        self.assertTrue(kwargs["coalesce"])
        self.assertEqual(kwargs["max_instances"], 1)


if __name__ == "__main__":
    unittest.main()
