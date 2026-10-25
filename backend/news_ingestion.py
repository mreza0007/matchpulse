"""Metadata ingestion only; no Telegram dispatch. Explicit operator polling entrypoint."""
import argparse
from datetime import datetime, timedelta, timezone
import logging
import uuid

from news_http import fetch_feed
from news_parser import parse_feed
from news_sources import approved_sources, parse_utc, utc_text
from news_store import connect, save_articles

logger = logging.getLogger(__name__)


def poll_source(source, *, path=None, fetcher=fetch_feed, now=None):
    current = now or datetime.now(timezone.utc)
    source.validate()
    if not source.approved(current):
        return "disabled"
    conn = connect(path)
    token = uuid.uuid4().hex
    stamp = utc_text(current)
    try:
        conn.execute("BEGIN IMMEDIATE")
        state = conn.execute("SELECT * FROM news_source_state WHERE source_key=?", (source.source_key,)).fetchone()
        if state and state["lease_until"] and parse_utc(state["lease_until"]) > current:
            conn.rollback()
            return "busy"
        changed = state is None or state["config_hash"] != source.fingerprint()
        if state and not changed and parse_utc(state["next_attempt_at"]) > current:
            conn.rollback()
            return "not_due"
        if changed:
            conn.execute("DELETE FROM news_source_state WHERE source_key=?", (source.source_key,))
            conn.execute("INSERT INTO news_source_state(source_key,config_hash,next_attempt_at) VALUES (?,?,?)",
                         (source.source_key, source.fingerprint(), stamp))
        conn.execute("UPDATE news_source_state SET lease_until=?,lease_token=?,last_attempt_at=? WHERE source_key=?",
                     (utc_text(current + timedelta(seconds=120)), token, stamp, source.source_key))
        conn.commit()
        retry_after = 0
        try:
            response = fetcher(source, None if changed else state["etag"], None if changed else state["last_modified"])
            retry_after = response.retry_after
            if response.status not in {200, 304} or (changed and response.status == 304):
                raise ValueError("Feed HTTP failure")
            articles = parse_feed(source, response.body, current) if response.status == 200 else []
            # Approval must still be valid when a real fetch completes.
            if not source.approved(current if now is not None else datetime.now(timezone.utc)):
                raise ValueError("Approval expired")
            conn.execute("BEGIN IMMEDIATE")
            owned = conn.execute("SELECT lease_token FROM news_source_state WHERE source_key=?", (source.source_key,)).fetchone()
            if not owned or owned[0] != token:
                conn.rollback()
                return "superseded"
            save_articles(conn, source, articles, stamp)
            conn.execute("""UPDATE news_source_state SET etag=COALESCE(?,etag),last_modified=COALESCE(?,last_modified),
                failure_count=0,next_attempt_at=?,last_success_at=?,last_error_code=NULL,lease_until=NULL,lease_token=NULL
                WHERE source_key=?""", (response.etag, response.last_modified,
                utc_text(current + timedelta(seconds=source.interval_seconds)), stamp, source.source_key))
            conn.commit()
            return "updated" if response.status == 200 else "unchanged"
        except Exception:
            conn.rollback()
            conn.execute("BEGIN IMMEDIATE")
            owned = conn.execute("SELECT failure_count FROM news_source_state WHERE source_key=? AND lease_token=?",
                                 (source.source_key, token)).fetchone()
            if owned:
                failures = owned[0] + 1
                delay = max(min(60 * 2 ** min(failures - 1, 9), 21600), min(retry_after, 21600))
                conn.execute("""UPDATE news_source_state SET failure_count=?,next_attempt_at=?,last_error_code='fetch_or_parse_failed',
                    lease_until=NULL,lease_token=NULL WHERE source_key=? AND lease_token=?""",
                    (failures, utc_text(current + timedelta(seconds=delay)), source.source_key, token))
            conn.commit()
            logger.warning("News source %s failed; retry deferred", source.source_key)
            return "failed"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def poll_approved_sources(path=None):
    results = {}
    for key, source in approved_sources().items():
        try:
            results[key] = poll_source(source, path=path)
        except Exception:
            logger.warning("News source %s storage unavailable", key)
            results[key] = "storage_unavailable"
    return results


def register_news_job(scheduler):
    # Separate ingestion job: never coupled to Telegram notification delivery.
    if approved_sources():
        scheduler.add_job(poll_approved_sources, "interval", seconds=60,
                          id="matchpulse_news_ingestion", replace_existing=True,
                          max_instances=1, coalesce=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poll reviewed, licensed sources only; never migrate")
    parser.add_argument("--db", required=True)
    print(poll_approved_sources(parser.parse_args().db))
