import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db_service
from migrations import prediction_v2
from prediction_schema import (
    PREDICTION_V2_MIGRATION_ID,
    ensure_prediction_v2_schema,
    prediction_schema_state,
)


LEGACY_SQL = """
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    prediction TEXT NOT NULL CHECK(prediction IN ('home', 'draw', 'away')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_id, match_id)
)
"""


class PredictionV2SchemaTests(unittest.TestCase):
    def make_path(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name) / "predictions.sqlite"

    def test_fresh_database_initialization_creates_v2_schema(self):
        path = self.make_path()
        with patch.object(db_service, "DB_PATH", path):
            db_service.init_db()

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(prediction_schema_state(conn), "v2")
        self.assertEqual(
            conn.execute(
                "SELECT migration_id FROM schema_migrations WHERE migration_id = ?",
                (PREDICTION_V2_MIGRATION_ID,),
            ).fetchone()[0],
            PREDICTION_V2_MIGRATION_ID,
        )

    def test_v2_identity_is_text_and_scoped_by_competition_and_season(self):
        path = self.make_path()
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        ensure_prediction_v2_schema(conn)
        conn.execute(
            """INSERT INTO predictions
               (telegram_id, competition_key, season_key, match_id, prediction_type, predicted_result)
               VALUES (1, 'worldcup2026', '2026', 42, 'result', 'home')"""
        )
        conn.execute(
            """INSERT INTO predictions
               (telegram_id, competition_key, season_key, match_id, prediction_type, predicted_result)
               VALUES (1, 'premier_league', '2026-2027', '42', 'result', 'away')"""
        )
        conn.commit()

        self.assertEqual(
            conn.execute("SELECT typeof(match_id) FROM predictions WHERE id = 1").fetchone()[0],
            "text",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO predictions
                   (telegram_id, competition_key, season_key, match_id, prediction_type, predicted_result)
                   VALUES (1, 'worldcup2026', '2026', '42', 'result', 'draw')"""
            )

    def test_prediction_shape_constraints(self):
        path = self.make_path()
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        ensure_prediction_v2_schema(conn)

        conn.execute(
            """INSERT INTO predictions
               (telegram_id, competition_key, season_key, match_id, prediction_type, home_score, away_score, predicted_result)
               VALUES (1, 'worldcup2026', '2026', 'exact', 'exact_score', 2, 1, 'home')"""
        )
        for values in [
            "(2, 'w', '2026', 'result-score', 'result', 'home', 1, NULL)",
            "(3, 'w', '2026', 'wrong-result', 'exact_score', 'draw', 2, 1)",
            "(4, 'w', '2026', 'negative', 'exact_score', 'home', -1, 0)",
        ]:
            with self.subTest(values=values):
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """INSERT INTO predictions
                           (telegram_id, competition_key, season_key, match_id, prediction_type, predicted_result, home_score, away_score)
                           VALUES """ + values
                    )


class PredictionV2MigrationTests(unittest.TestCase):
    def make_legacy_database(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "legacy.sqlite"
        conn = sqlite3.connect(path)
        conn.execute(LEGACY_SQL)
        conn.execute(
            """INSERT INTO predictions
               (id, telegram_id, match_id, prediction, created_at, updated_at)
               VALUES (7, 100, 42, 'home', '2026-01-02 03:04:05', '2026-01-03 04:05:06')"""
        )
        conn.commit()
        conn.close()
        return path

    def test_legacy_schema_detection_and_backup_requirement(self):
        path = self.make_legacy_database()
        self.assertEqual(prediction_v2.inspect_prediction_database(path)["prediction_schema"], "legacy")
        with self.assertRaisesRegex(prediction_v2.PredictionMigrationError, "backup confirmation"):
            prediction_v2.migrate_prediction_v2(path)

    def test_init_db_leaves_legacy_predictions_untouched(self):
        path = self.make_legacy_database()
        with patch.object(db_service, "DB_PATH", path):
            db_service.init_db()

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(prediction_schema_state(conn), "legacy")
        self.assertFalse(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'predictions_legacy'"
            ).fetchone()
        )

    def test_missing_predictions_table_is_a_safe_migration_no_op(self):
        path = self.make_path()
        sqlite3.connect(path).close()
        self.assertEqual(
            prediction_v2.migrate_prediction_v2(path),
            {"action": "no-op", "reason": "no predictions table to migrate"},
        )

    def test_legacy_migration_preserves_rows_and_is_idempotent(self):
        path = self.make_legacy_database()
        result = prediction_v2.migrate_prediction_v2(path, backup_confirmed=True)
        self.assertEqual(result, {"action": "migrated", "rows": 1})

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        migrated = conn.execute(
            """SELECT id, telegram_id, competition_key, season_key, match_id, prediction_type,
                      predicted_result, home_score, away_score, points_awarded, evaluated_at,
                      created_at, updated_at, typeof(match_id)
               FROM predictions"""
        ).fetchone()
        self.assertEqual(
            migrated,
            (7, 100, "worldcup2026", "2026", "42", "result", "home", None, None, None, None,
             "2026-01-02 03:04:05", "2026-01-03 04:05:06", "text"),
        )
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM predictions_legacy").fetchone()[0], 1)
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE migration_id = ?",
                (PREDICTION_V2_MIGRATION_ID,),
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            prediction_v2.migrate_prediction_v2(path, backup_confirmed=True),
            {"action": "no-op", "reason": "prediction_v2 already present"},
        )

    def test_unknown_schema_and_legacy_collision_abort(self):
        path = self.make_path()
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE predictions (value TEXT)")
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(prediction_v2.PredictionMigrationError, "Unknown"):
            prediction_v2.migrate_prediction_v2(path, backup_confirmed=True)

        path = self.make_legacy_database()
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE predictions_legacy (id INTEGER)")
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(prediction_v2.PredictionMigrationError, "already exists"):
            prediction_v2.migrate_prediction_v2(path, backup_confirmed=True)

    def test_failed_verification_rolls_back_without_replacing_legacy_table(self):
        path = self.make_legacy_database()
        with patch(
            "migrations.prediction_v2.verify_legacy_copy",
            side_effect=prediction_v2.PredictionMigrationError("verification failed"),
        ):
            with self.assertRaisesRegex(prediction_v2.PredictionMigrationError, "verification failed"):
                prediction_v2.migrate_prediction_v2(path, backup_confirmed=True)

        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(prediction_schema_state(conn), "legacy")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0], 1)
        self.assertFalse(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'predictions_v2'"
            ).fetchone()
        )

    def make_path(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name) / "predictions.sqlite"


if __name__ == "__main__":
    unittest.main()
