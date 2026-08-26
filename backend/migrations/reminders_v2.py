import argparse
import json
import sqlite3
from pathlib import Path

from reminder_schema import (
    create_reminders_v2_table,
    record_reminders_v2_migration,
    reminder_table_state,
    reminders_schema_state,
    reminders_v2_migration_recorded,
    table_exists,
)


class ReminderMigrationError(RuntimeError):
    pass


def inspect_reminder_database(db_path):
    path = Path(db_path)
    if not path.exists():
        raise ReminderMigrationError("Database path does not exist")

    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        return {
            "database": str(path),
            "reminders_schema": reminders_schema_state(conn),
            "has_reminders_legacy": table_exists(conn, "reminders_legacy"),
            "has_reminders_v2_staging": table_exists(conn, "reminders_v2"),
            "migration_recorded": reminders_v2_migration_recorded(conn),
        }
    finally:
        conn.close()


def validate_legacy_source(conn):
    invalid_count = conn.execute(
        """
        SELECT COUNT(*) FROM reminders
        WHERE telegram_id IS NULL
           OR match_id IS NULL
           OR match_data IS NULL
           OR notified IS NULL
        """
    ).fetchone()[0]
    if invalid_count:
        raise ReminderMigrationError(
            "Legacy reminders contain NULL values that cannot be safely preserved"
        )

    duplicate_count = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT telegram_id, CAST(match_id AS TEXT), COUNT(*) AS row_count
            FROM reminders
            GROUP BY telegram_id, CAST(match_id AS TEXT)
            HAVING row_count > 1
        )
        """
    ).fetchone()[0]
    if duplicate_count:
        raise ReminderMigrationError(
            "Legacy reminders contain duplicate scoped identities"
        )


def verify_reminder_copy(conn, source_count):
    if reminder_table_state(conn, "reminders_v2") != "v2":
        raise ReminderMigrationError("Staged reminders schema verification failed")

    target_count = conn.execute("SELECT COUNT(*) FROM reminders_v2").fetchone()[0]
    if target_count != source_count:
        raise ReminderMigrationError("Reminder copy row count mismatch")

    duplicate_count = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT telegram_id, competition_key, season_key, match_id,
                   COUNT(*) AS row_count
            FROM reminders_v2
            GROUP BY telegram_id, competition_key, season_key, match_id
            HAVING row_count > 1
        )
        """
    ).fetchone()[0]
    if duplicate_count:
        raise ReminderMigrationError("Reminder copy created duplicate scoped identities")

    mismatch_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM reminders AS legacy
        LEFT JOIN reminders_v2 AS migrated ON migrated.id = legacy.id
        WHERE migrated.id IS NULL
           OR migrated.telegram_id IS NOT legacy.telegram_id
           OR migrated.competition_key != 'worldcup2026'
           OR migrated.season_key != '2026'
           OR migrated.match_id != CAST(legacy.match_id AS TEXT)
           OR typeof(migrated.match_id) != 'text'
           OR migrated.match_data IS NOT legacy.match_data
           OR migrated.notified IS NOT legacy.notified
        """
    ).fetchone()[0]
    if mismatch_count:
        raise ReminderMigrationError("Reminder copy value verification failed")


def migrate_reminders_v2(db_path, *, backup_confirmed=False):
    path = Path(db_path)
    if not path.exists():
        raise ReminderMigrationError("Database path does not exist")

    conn = sqlite3.connect(path)
    try:
        state = reminders_schema_state(conn)
        migration_recorded = reminders_v2_migration_recorded(conn)
        has_legacy_backup = table_exists(conn, "reminders_legacy")
        has_staging_table = table_exists(conn, "reminders_v2")

        if state == "v2":
            if has_staging_table:
                raise ReminderMigrationError(
                    "reminders_v2 staging table exists beside the active V2 schema"
                )
            if not migration_recorded:
                raise ReminderMigrationError(
                    "Reminders V2 schema exists without its migration marker"
                )
            if (
                has_legacy_backup
                and reminder_table_state(conn, "reminders_legacy") != "legacy"
            ):
                raise ReminderMigrationError(
                    "reminders_legacy is not a valid recoverable legacy backup"
                )
            return {"action": "no-op", "reason": "reminders_v2 already present"}

        if migration_recorded:
            raise ReminderMigrationError(
                "Reminders migration marker exists without an active V2 schema"
            )
        if state == "missing":
            if has_legacy_backup or has_staging_table:
                raise ReminderMigrationError(
                    "Reminder migration artifacts exist without an active reminders table"
                )
            return {"action": "no-op", "reason": "no reminders table to migrate"}
        if state != "legacy":
            raise ReminderMigrationError("Unknown reminders schema; migration aborted")
        if has_legacy_backup:
            raise ReminderMigrationError("reminders_legacy already exists; migration aborted")
        if has_staging_table:
            raise ReminderMigrationError(
                "reminders_v2 staging table already exists; migration aborted"
            )
        if not backup_confirmed:
            raise ReminderMigrationError("Legacy migration requires backup confirmation")

        conn.execute("BEGIN IMMEDIATE")
        if reminders_schema_state(conn) != "legacy":
            raise ReminderMigrationError("Reminders schema changed before migration lock")
        if reminders_v2_migration_recorded(conn):
            raise ReminderMigrationError(
                "Reminders migration marker appeared before migration lock"
            )
        if table_exists(conn, "reminders_legacy"):
            raise ReminderMigrationError(
                "reminders_legacy already exists; migration aborted"
            )
        if table_exists(conn, "reminders_v2"):
            raise ReminderMigrationError(
                "reminders_v2 staging table already exists; migration aborted"
            )

        validate_legacy_source(conn)
        source_count = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
        create_reminders_v2_table(conn, "reminders_v2")
        conn.execute(
            """
            INSERT INTO reminders_v2 (
                id, telegram_id, competition_key, season_key,
                match_id, match_data, notified
            )
            SELECT
                id, telegram_id, 'worldcup2026', '2026',
                CAST(match_id AS TEXT), match_data, notified
            FROM reminders
            """
        )
        verify_reminder_copy(conn, source_count)

        conn.execute("ALTER TABLE reminders RENAME TO reminders_legacy")
        conn.execute("ALTER TABLE reminders_v2 RENAME TO reminders")
        if reminders_schema_state(conn) != "v2":
            raise ReminderMigrationError("Final reminders schema verification failed")
        if reminder_table_state(conn, "reminders_legacy") != "legacy":
            raise ReminderMigrationError("Legacy reminder backup verification failed")
        record_reminders_v2_migration(conn)
        conn.commit()
        return {"action": "migrated", "rows": source_count}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Explicit MatchPulse reminders v2 migration")
    parser.add_argument("--db", required=True, help="Path to the SQLite database")
    parser.add_argument("--migrate", action="store_true", help="Perform the migration")
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        help="Confirm that a verified database backup exists",
    )
    args = parser.parse_args()

    try:
        result = (
            migrate_reminders_v2(args.db, backup_confirmed=args.backup_confirmed)
            if args.migrate
            else inspect_reminder_database(args.db)
        )
    except ReminderMigrationError as error:
        parser.error(str(error))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
