"""Additive news v1 schema; only the explicit migration creates these tables."""
from functools import lru_cache
import sqlite3

from prediction_schema import table_exists

MIGRATION_ID = "news_engine_v1"
DDL = (
    """CREATE TABLE news_articles (
        id TEXT PRIMARY KEY NOT NULL, source_key TEXT NOT NULL,
        original_url TEXT NOT NULL, canonical_url TEXT NOT NULL UNIQUE,
        headline TEXT NOT NULL, summary TEXT, image_url TEXT,
        published_at TEXT NOT NULL, ingested_at TEXT NOT NULL,
        category TEXT NOT NULL CHECK(category IN ('iran','world','national','transfers')),
        language TEXT NOT NULL)""",
    """CREATE TABLE news_article_keys (
        source_key TEXT NOT NULL, identity_type TEXT NOT NULL CHECK(identity_type IN ('guid','url')),
        identity_value TEXT NOT NULL, article_id TEXT NOT NULL REFERENCES news_articles(id),
        PRIMARY KEY(source_key, identity_type, identity_value))""",
    """CREATE TABLE news_article_teams (
        article_id TEXT NOT NULL REFERENCES news_articles(id), competition_key TEXT NOT NULL,
        team_id TEXT NOT NULL, PRIMARY KEY(article_id, competition_key, team_id))""",
    """CREATE TABLE news_source_state (
        source_key TEXT PRIMARY KEY NOT NULL, config_hash TEXT NOT NULL,
        etag TEXT, last_modified TEXT, failure_count INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TEXT NOT NULL, lease_until TEXT, lease_token TEXT,
        last_attempt_at TEXT, last_success_at TEXT, last_error_code TEXT)""",
    "CREATE INDEX news_articles_order ON news_articles(published_at DESC, id ASC)",
    "CREATE INDEX news_teams_lookup ON news_article_teams(competition_key, team_id, article_id)",
)
TABLES = {"news_articles", "news_article_keys", "news_article_teams", "news_source_state"}


def signature(conn):
    return {(kind, name): " ".join(sql.lower().split())
            for kind, name, sql in conn.execute(
                "SELECT type, name, sql FROM sqlite_master WHERE substr(name,1,5)='news_' AND sql IS NOT NULL")}


@lru_cache(maxsize=1)
def expected_signature():
    conn = sqlite3.connect(":memory:")
    try:
        for statement in DDL:
            conn.execute(statement)
        return signature(conn)
    finally:
        conn.close()


def news_schema_state(conn):
    recorded = table_exists(conn, "schema_migrations") and conn.execute(
        "SELECT 1 FROM schema_migrations WHERE migration_id=?", (MIGRATION_ID,)).fetchone() is not None
    actual = signature(conn)
    if not actual and not recorded:
        return "missing"
    if recorded and actual == expected_signature():
        return "v1"
    return "inconsistent"
