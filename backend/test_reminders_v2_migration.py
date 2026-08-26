import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db_service
from migrations import reminders_v2
from reminder_schema import (
    has_unique_index,
    create_reminders_v2_table,
    record_reminders_v2_migration,
    reminder_table_state,
    reminders_schema_state,
    reminders_v2_migration_recorded,
)


LEGACY_REMINDERS_SQL = """
CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    match_id INTEGER,
    match_data TEXT,
    notified INTEGER DEFAULT 0,
    UNIQUE(telegram_id, match_id)
)
"""


class RemindersV2MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "matchpulse.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_legacy_database(self, rows=()):
        conn = sqlite3.connect(self.db_path)
        conn.execute(LEGACY_REMINDERS_SQL)
        conn.executemany(
            """
            INSERT INTO reminders (id, telegram_id, match_id, match_data, notified)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        conn.close()

    def migrate(self):
        return reminders_v2.migrate_reminders_v2(
            self.db_path, backup_confirmed=True
        )

    def test_populated_legacy_table_is_preserved_with_scoped_identity(self):
        rows = [
            (4, 100, 11, '{"id":11,"name":"ایران"}', 0),
            (9, 200, 12, '{"id": 12, "nested": {"a": 1}}', 1),
        ]
        self.create_legacy_database(rows)

        self.assertEqual(self.migrate(), {"action": "migrated", "rows": 2})

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(reminders_schema_state(conn), "v2")
            self.assertEqual(reminder_table_state(conn, "reminders_legacy"), "legacy")
            self.assertTrue(reminders_v2_migration_recorded(conn))
            migrated = conn.execute(
                """
                SELECT id, telegram_id, competition_key, season_key,
                       match_id, typeof(match_id), match_data, notified
                FROM reminders ORDER BY id
                """
            ).fetchall()
            backup = conn.execute(
                """
                SELECT id, telegram_id, match_id, match_data, notified
                FROM reminders_legacy ORDER BY id
                """
            ).fetchall()
            self.assertTrue(
                has_unique_index(
                    conn,
                    "reminders",
                    ("telegram_id", "competition_key", "season_key", "match_id"),
                )
            )
            new_id = conn.execute(
                """
                INSERT INTO reminders (
                    telegram_id, competition_key, season_key,
                    match_id, match_data
                )
                VALUES (300, 'premier_league', '2026-27', '99', '{"id":99}')
                """
            ).lastrowid
            self.assertEqual(new_id, 10)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO reminders_legacy (
                        id, telegram_id, match_id, match_data, notified
                    )
                    VALUES (10, 100, 11, '{"id":11}', 0)
                    """
                )
        finally:
            conn.close()

        self.assertEqual(
            migrated,
            [
                (4, 100, "worldcup2026", "2026", "11", "text", rows[0][3], 0),
                (9, 200, "worldcup2026", "2026", "12", "text", rows[1][3], 1),
            ],
        )
        self.assertEqual(backup, rows)
        self.assertEqual(
            self.migrate(),
            {"action": "no-op", "reason": "reminders_v2 already present"},
        )

    def test_empty_legacy_table_migrates_and_retains_empty_backup(self):
        self.create_legacy_database()
        self.assertEqual(self.migrate(), {"action": "migrated", "rows": 0})

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0], 0)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM reminders_legacy").fetchone()[0], 0
            )
            self.assertEqual(reminders_schema_state(conn), "v2")
        finally:
            conn.close()

    def test_scoped_uniqueness_and_cross_competition_season_coexistence(self):
        with patch.object(db_service, "DB_PATH", self.db_path):
            db_service.init_db()
            match = {"id": 77, "name": "fixture"}
            self.assertTrue(
                db_service.save_reminder_to_db(1, match, "premier_league", "2026-27")
            )
            self.assertFalse(
                db_service.save_reminder_to_db(1, match, "premier_league", "2026-27")
            )
            self.assertTrue(
                db_service.save_reminder_to_db(1, match, "la_liga", "2026-27")
            )
            self.assertTrue(
                db_service.save_reminder_to_db(1, match, "premier_league", "2027-28")
            )

        conn = sqlite3.connect(self.db_path)
        try:
            identities = conn.execute(
                """
                SELECT competition_key, season_key, match_id
                FROM reminders ORDER BY competition_key, season_key
                """
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(
            identities,
            [
                ("la_liga", "2026-27", "77"),
                ("premier_league", "2026-27", "77"),
                ("premier_league", "2027-28", "77"),
            ],
        )

    def test_exact_scoped_delete_is_idempotent(self):
        with patch.object(db_service, "DB_PATH", self.db_path):
            db_service.init_db()
            match = {"id": "same"}
            db_service.save_reminder_to_db(5, match, "premier_league", "2026-27")
            db_service.save_reminder_to_db(5, match, "la_liga", "2026-27")

            self.assertTrue(
                db_service.delete_reminder_from_db(
                    5, "same", "premier_league", "2026-27"
                )
            )
            self.assertFalse(
                db_service.delete_reminder_from_db(
                    5, "same", "premier_league", "2026-27"
                )
            )
            remaining = db_service.get_reminders_from_db(5)

        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["competition_key"], "la_liga")

    def test_mark_notified_updates_only_exact_scoped_tuple(self):
        with patch.object(db_service, "DB_PATH", self.db_path):
            db_service.init_db()
            match = {"id": "same"}
            db_service.save_reminder_to_db(8, match, "premier_league", "2026-27")
            db_service.save_reminder_to_db(8, match, "premier_league", "2027-28")
            db_service.save_reminder_to_db(8, match, "la_liga", "2026-27")
            self.assertTrue(
                db_service.mark_reminder_notified(
                    8, "same", "premier_league", "2027-28"
                )
            )

        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT competition_key, season_key, notified
                FROM reminders ORDER BY competition_key, season_key
                """
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(
            rows,
            [
                ("la_liga", "2026-27", 0),
                ("premier_league", "2026-27", 0),
                ("premier_league", "2027-28", 1),
            ],
        )

    def test_legacy_worldcup_read_and_delete_adapter(self):
        raw_match = json.dumps({"id": 31, "home_team": "A"})
        self.create_legacy_database([(3, 99, 31, raw_match, 0)])

        with patch.object(db_service, "DB_PATH", self.db_path):
            reminders = db_service.get_reminders_from_db(99)
            self.assertEqual(reminders[0]["id"], 31)
            self.assertEqual(reminders[0]["competition_key"], "worldcup2026")
            self.assertEqual(reminders[0]["season_key"], "2026")
            self.assertIs(reminders[0]["notified"], False)
            self.assertTrue(db_service.mark_reminder_notified(99, 31))
            reminders = db_service.get_reminders_from_db(99)
            self.assertIs(reminders[0]["notified"], True)
            self.assertTrue(db_service.delete_reminder_from_db(99, 31))
            self.assertFalse(db_service.delete_reminder_from_db(99, 31))

    def test_startup_does_not_silently_migrate_legacy_table(self):
        self.create_legacy_database([(1, 10, 22, '{"id":22}', 0)])

        with patch.object(db_service, "DB_PATH", self.db_path):
            db_service.init_db()

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(reminders_schema_state(conn), "legacy")
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reminders_legacy'"
                ).fetchone()
            )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0], 1)
        finally:
            conn.close()

    def test_failed_migration_rolls_back_schema_and_data(self):
        rows = [(6, 20, 88, '{"id":88,"raw":"unchanged"}', 1)]
        self.create_legacy_database(rows)

        with patch.object(
            reminders_v2,
            "record_reminders_v2_migration",
            side_effect=reminders_v2.ReminderMigrationError("forced finalization failure"),
        ):
            with self.assertRaisesRegex(
                reminders_v2.ReminderMigrationError, "forced finalization failure"
            ):
                self.migrate()

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(reminders_schema_state(conn), "legacy")
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reminders_v2'"
                ).fetchone()
            )
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reminders_legacy'"
                ).fetchone()
            )
            self.assertEqual(
                conn.execute(
                    "SELECT id, telegram_id, match_id, match_data, notified FROM reminders"
                ).fetchall(),
                rows,
            )
        finally:
            conn.close()

    def test_active_v2_with_staging_table_fails_explicitly(self):
        with patch.object(db_service, "DB_PATH", self.db_path):
            db_service.init_db()
        conn = sqlite3.connect(self.db_path)
        try:
            create_reminders_v2_table(conn, "reminders_v2")
            conn.commit()
        finally:
            conn.close()

        with self.assertRaisesRegex(
            reminders_v2.ReminderMigrationError, "staging table exists"
        ):
            self.migrate()

    def test_marker_without_active_v2_schema_fails_explicitly(self):
        self.create_legacy_database()
        conn = sqlite3.connect(self.db_path)
        try:
            record_reminders_v2_migration(conn)
            conn.commit()
        finally:
            conn.close()

        with self.assertRaisesRegex(
            reminders_v2.ReminderMigrationError,
            "marker exists without an active V2 schema",
        ):
            self.migrate()

    def test_startup_does_not_backfill_marker_for_preexisting_v2_schema(self):
        conn = sqlite3.connect(self.db_path)
        try:
            create_reminders_v2_table(conn)
            conn.commit()
        finally:
            conn.close()

        with patch.object(db_service, "DB_PATH", self.db_path):
            db_service.init_db()

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertFalse(reminders_v2_migration_recorded(conn))
        finally:
            conn.close()
        with self.assertRaisesRegex(
            reminders_v2.ReminderMigrationError, "without its migration marker"
        ):
            self.migrate()

    def test_existing_legacy_backup_is_never_overwritten(self):
        self.create_legacy_database()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE reminders_legacy (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    match_id INTEGER,
                    match_data TEXT,
                    notified INTEGER DEFAULT 0,
                    UNIQUE(telegram_id, match_id)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaisesRegex(
            reminders_v2.ReminderMigrationError, "reminders_legacy already exists"
        ):
            self.migrate()

    def test_invalid_legacy_rows_abort_before_replacement(self):
        self.create_legacy_database([(1, None, 1, '{"id":1}', 0)])
        with self.assertRaisesRegex(
            reminders_v2.ReminderMigrationError, "NULL values"
        ):
            self.migrate()

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(reminders_schema_state(conn), "legacy")
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0],
                1,
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
