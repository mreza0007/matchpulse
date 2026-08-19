import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db_service
from favorite_schema import (
    FAVORITE_TEAMS_V2_COLUMNS,
    FAVORITE_TEAMS_V2_MIGRATION_ID,
    create_favorite_teams_v2_table,
    ensure_favorite_teams_v2_schema,
    favorite_teams_schema_state,
)
from migrations import favorite_teams_v2
from prediction_schema import prediction_schema_state


LEGACY_FAVORITES_SQL = """
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


class FavoriteTeamsV2TestBase(unittest.TestCase):
    def make_path(self, name="favorites.sqlite"):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name) / name

    def make_legacy_database(self, rows=None):
        path = self.make_path("legacy.sqlite")
        conn = sqlite3.connect(path)
        conn.execute(LEGACY_FAVORITES_SQL)
        for row in rows or []:
            conn.execute(
                """
                INSERT INTO favorite_teams (
                    id, telegram_id, team_id, team_key, team_name, team_data
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        conn.commit()
        conn.close()
        return path


class FavoriteTeamsV2SchemaTests(FavoriteTeamsV2TestBase):
    def test_fresh_database_initialization_creates_v2_without_touching_other_schemas(self):
        path = self.make_path()
        with patch.object(db_service, "DB_PATH", path):
            db_service.init_db()

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(favorite_teams_schema_state(conn), "v2")
        columns = {
            row[1]: {"type": row[2], "notnull": bool(row[3])}
            for row in conn.execute("PRAGMA table_info(favorite_teams)")
        }
        self.assertEqual(set(columns), FAVORITE_TEAMS_V2_COLUMNS)
        self.assertEqual(columns["team_id"]["type"], "TEXT")
        self.assertNotIn("season_key", columns)
        self.assertTrue({"team_name", "team_logo", "team_key"}.isdisjoint(columns))
        self.assertEqual(
            conn.execute(
                "SELECT migration_id FROM schema_migrations WHERE migration_id = ?",
                (FAVORITE_TEAMS_V2_MIGRATION_ID,),
            ).fetchone()[0],
            FAVORITE_TEAMS_V2_MIGRATION_ID,
        )
        self.assertEqual(prediction_schema_state(conn), "v2")
        self.assertEqual(
            {row[1] for row in conn.execute("PRAGMA table_info(reminders)")},
            {"id", "telegram_id", "match_id", "match_data", "notified"},
        )

    def test_text_identity_is_scoped_by_competition(self):
        path = self.make_path()
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        ensure_favorite_teams_v2_schema(conn)
        conn.execute(
            "INSERT INTO favorite_teams (telegram_id, competition_key, team_id) VALUES (1, 'worldcup2026', 6)"
        )
        conn.execute(
            "INSERT INTO favorite_teams (telegram_id, competition_key, team_id) VALUES (1, 'premier_league', '6')"
        )
        self.assertEqual(
            conn.execute(
                "SELECT DISTINCT typeof(team_id) FROM favorite_teams"
            ).fetchall(),
            [("text",)],
        )
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO favorite_teams (telegram_id, competition_key, team_id) VALUES (1, 'worldcup2026', '6')"
            )

    def test_legacy_and_unknown_schema_detection(self):
        path = self.make_legacy_database()
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(favorite_teams_schema_state(conn), "legacy")
        conn.close()

        path = self.make_path("unknown.sqlite")
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE favorite_teams (value TEXT)")
        self.assertEqual(favorite_teams_schema_state(conn), "unknown")

    def test_init_db_leaves_legacy_favorites_untouched(self):
        row = (7, 100, 6, "client-key", "Client name", '{"id": 6}')
        path = self.make_legacy_database([row])
        with patch.object(db_service, "DB_PATH", path):
            db_service.init_db()

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(favorite_teams_schema_state(conn), "legacy")
        self.assertEqual(
            conn.execute(
                "SELECT id, telegram_id, team_id, team_key, team_name, team_data FROM favorite_teams"
            ).fetchone(),
            row,
        )
        self.assertFalse(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='favorite_teams_legacy'"
            ).fetchone()
        )


class FavoriteTeamsV2MigrationTests(FavoriteTeamsV2TestBase):
    def legacy_rows(self):
        return [
            (7, 100, 6, "not-trusted", "Untrusted display", '{"id": 6}'),
            (8, 100, 999, "6", "6", '{"id": 999}'),
        ]

    def test_inspection_and_backup_confirmation_are_required(self):
        path = self.make_legacy_database(self.legacy_rows())
        inspection = favorite_teams_v2.inspect_favorite_teams_database(path)
        self.assertEqual(inspection["favorites_schema"], "legacy")
        self.assertFalse(inspection["migration_recorded"])
        with self.assertRaisesRegex(
            favorite_teams_v2.FavoriteTeamsMigrationError, "backup confirmation"
        ):
            favorite_teams_v2.migrate_favorite_teams_v2(
                path, trusted_worldcup_team_ids={"6"}
            )

    def test_exact_trusted_id_migrates_and_untrusted_row_is_retained(self):
        path = self.make_legacy_database(self.legacy_rows())
        result = favorite_teams_v2.migrate_favorite_teams_v2(
            path,
            trusted_worldcup_team_ids={"6"},
            backup_confirmed=True,
        )
        self.assertEqual(
            result,
            {
                "action": "migrated",
                "source_rows": 2,
                "resolved_rows": 1,
                "unresolved_rows": 1,
                "conflict_rows": 0,
            },
        )

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(favorite_teams_schema_state(conn), "v2")
        self.assertEqual(
            conn.execute(
                "SELECT id, competition_key, team_id, typeof(team_id) FROM favorite_teams"
            ).fetchone(),
            (7, "worldcup2026", "6", "text"),
        )
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM favorite_teams_legacy").fetchone()[0],
            2,
        )
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE migration_id = ?",
                (FAVORITE_TEAMS_V2_MIGRATION_ID,),
            ).fetchone()[0],
            1,
        )

    def test_migration_is_idempotent(self):
        path = self.make_legacy_database(self.legacy_rows()[:1])
        favorite_teams_v2.migrate_favorite_teams_v2(
            path,
            trusted_worldcup_team_ids={"6"},
            backup_confirmed=True,
        )
        self.assertEqual(
            favorite_teams_v2.migrate_favorite_teams_v2(
                path,
                trusted_worldcup_team_ids={"6"},
                backup_confirmed=True,
            ),
            {"action": "no-op", "reason": "favorite_teams_v2 already present"},
        )

    def test_missing_table_is_safe_no_op(self):
        path = self.make_path()
        sqlite3.connect(path).close()
        self.assertEqual(
            favorite_teams_v2.migrate_favorite_teams_v2(
                path,
                trusted_worldcup_team_ids=set(),
                backup_confirmed=True,
            ),
            {"action": "no-op", "reason": "no favorite_teams table to migrate"},
        )

    def test_unknown_backup_and_temporary_collisions_abort(self):
        path = self.make_path("unknown.sqlite")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE favorite_teams (value TEXT)")
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(
            favorite_teams_v2.FavoriteTeamsMigrationError, "Unknown"
        ):
            favorite_teams_v2.migrate_favorite_teams_v2(
                path, trusted_worldcup_team_ids=set(), backup_confirmed=True
            )

        for collision_table in ("favorite_teams_legacy", "favorite_teams_v2"):
            with self.subTest(collision_table=collision_table):
                path = self.make_legacy_database()
                conn = sqlite3.connect(path)
                conn.execute(f"CREATE TABLE {collision_table} (id INTEGER)")
                conn.commit()
                conn.close()
                with self.assertRaisesRegex(
                    favorite_teams_v2.FavoriteTeamsMigrationError, "already exists"
                ):
                    favorite_teams_v2.migrate_favorite_teams_v2(
                        path,
                        trusted_worldcup_team_ids=set(),
                        backup_confirmed=True,
                    )

    def test_v2_without_marker_aborts(self):
        path = self.make_path()
        conn = sqlite3.connect(path)
        create_favorite_teams_v2_table(conn)
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(
            favorite_teams_v2.FavoriteTeamsMigrationError, "without its migration marker"
        ):
            favorite_teams_v2.migrate_favorite_teams_v2(
                path, trusted_worldcup_team_ids=set(), backup_confirmed=True
            )

    def test_composite_conflict_aborts_and_rolls_back(self):
        path = self.make_legacy_database(self.legacy_rows())
        duplicate_rows = [
            (7, 100, "worldcup2026", "6"),
            (8, 100, "worldcup2026", "6"),
        ]
        with patch(
            "migrations.favorite_teams_v2.classify_legacy_rows",
            return_value=(duplicate_rows, 0),
        ):
            with self.assertRaisesRegex(
                favorite_teams_v2.FavoriteTeamsMigrationError, "conflict"
            ):
                favorite_teams_v2.migrate_favorite_teams_v2(
                    path,
                    trusted_worldcup_team_ids={"6"},
                    backup_confirmed=True,
                )

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(favorite_teams_schema_state(conn), "legacy")
        self.assertFalse(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='favorite_teams_v2'"
            ).fetchone()
        )

    def test_failed_verification_rolls_back(self):
        path = self.make_legacy_database(self.legacy_rows()[:1])
        with patch(
            "migrations.favorite_teams_v2.verify_favorite_teams_copy",
            side_effect=favorite_teams_v2.FavoriteTeamsMigrationError(
                "verification failed"
            ),
        ):
            with self.assertRaisesRegex(
                favorite_teams_v2.FavoriteTeamsMigrationError, "verification failed"
            ):
                favorite_teams_v2.migrate_favorite_teams_v2(
                    path,
                    trusted_worldcup_team_ids={"6"},
                    backup_confirmed=True,
                )

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(favorite_teams_schema_state(conn), "legacy")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM favorite_teams").fetchone()[0], 1)
        self.assertFalse(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='favorite_teams_v2'"
            ).fetchone()
        )

    def test_prediction_and_reminder_tables_are_unchanged(self):
        path = self.make_legacy_database(self.legacy_rows()[:1])
        conn = sqlite3.connect(path)
        conn.execute(LEGACY_REMINDERS_SQL)
        conn.execute(
            "INSERT INTO reminders (telegram_id, match_id, match_data) VALUES (100, 42, '{}')"
        )
        conn.execute("CREATE TABLE predictions (sentinel TEXT)")
        conn.execute("INSERT INTO predictions VALUES ('unchanged')")
        conn.commit()
        before = {
            name: conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()[0]
            for name in ("reminders", "predictions")
        }
        conn.close()

        favorite_teams_v2.migrate_favorite_teams_v2(
            path,
            trusted_worldcup_team_ids={"6"},
            backup_confirmed=True,
        )

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        after = {
            name: conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()[0]
            for name in ("reminders", "predictions")
        }
        self.assertEqual(after, before)
        self.assertEqual(conn.execute("SELECT match_id FROM reminders").fetchone()[0], 42)
        self.assertEqual(conn.execute("SELECT sentinel FROM predictions").fetchone()[0], "unchanged")

    def test_trusted_snapshot_requires_exact_valid_unique_ids(self):
        path = self.make_path("trusted.json")
        path.write_text(json.dumps([6, "mp-team"]), encoding="utf-8")
        self.assertEqual(
            favorite_teams_v2.trusted_worldcup_team_ids_from_file(path),
            frozenset({"6", "mp-team"}),
        )

        for payload in ({"6": "6"}, ["6", "6"], [" 6"], [None], [True]):
            with self.subTest(payload=payload):
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(favorite_teams_v2.FavoriteTeamsMigrationError):
                    favorite_teams_v2.trusted_worldcup_team_ids_from_file(path)


if __name__ == "__main__":
    unittest.main()
