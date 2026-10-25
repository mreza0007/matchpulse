"""Run from backend: python -m migrations.news_v1 --db PATH [--migrate --backup-confirmed]."""
import argparse
import json
from pathlib import Path
import sqlite3

from news_schema import DDL, MIGRATION_ID, news_schema_state
from prediction_schema import create_schema_migrations_table


def connect_existing(path, mode="ro"):
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise ValueError("Database path must be an existing file")
    return sqlite3.connect(f"file:{resolved.as_posix()}?mode={mode}", uri=True, timeout=5)


def inspect_news_database(path):
    conn = connect_existing(path)
    try:
        return {"news_schema": news_schema_state(conn)}
    finally:
        conn.close()


def migrate_news_v1(path, *, backup_confirmed=False):
    if not backup_confirmed:
        raise ValueError("A verified backup is required before migration")
    conn = connect_existing(path, "rw")
    try:
        conn.execute("BEGIN IMMEDIATE")
        state = news_schema_state(conn)
        if state == "v1":
            conn.rollback()
            return {"action": "unchanged"}
        if state != "missing":
            raise ValueError("Ambiguous news schema/marker state; operator recovery required")
        for statement in DDL:
            conn.execute(statement)
        create_schema_migrations_table(conn)
        conn.execute("INSERT INTO schema_migrations(migration_id) VALUES (?)", (MIGRATION_ID,))
        if news_schema_state(conn) != "v1":
            raise ValueError("News schema verification failed")
        conn.commit()
        return {"action": "migrated"}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Explicit additive news migration (inspect by default)")
    parser.add_argument("--db", required=True)
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--backup-confirmed", action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate_news_v1(args.db, backup_confirmed=args.backup_confirmed)
        if args.migrate else inspect_news_database(args.db)))


if __name__ == "__main__":
    main()
