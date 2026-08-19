import argparse
import json
import sqlite3
from pathlib import Path

from prediction_schema import (
    PREDICTION_V2_MIGRATION_ID,
    create_predictions_v2_table,
    prediction_schema_state,
    record_prediction_v2_migration,
    table_exists,
)


class PredictionMigrationError(RuntimeError):
    pass


def inspect_prediction_database(db_path):
    path = Path(db_path)
    if not path.exists():
        raise PredictionMigrationError("Database path does not exist")

    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        state = prediction_schema_state(conn)
        return {
            "database": str(path),
            "prediction_schema": state,
            "has_predictions_legacy": table_exists(conn, "predictions_legacy"),
            "migration_recorded": table_exists(conn, "schema_migrations")
            and conn.execute(
                "SELECT 1 FROM schema_migrations WHERE migration_id = ?",
                (PREDICTION_V2_MIGRATION_ID,),
            ).fetchone()
            is not None,
        }
    finally:
        conn.close()


def verify_legacy_copy(conn, source_count):
    target_count = conn.execute("SELECT COUNT(*) FROM predictions_v2").fetchone()[0]
    if target_count != source_count:
        raise PredictionMigrationError("Prediction copy row count mismatch")

    duplicate_count = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT telegram_id, competition_key, season_key, match_id, COUNT(*) AS row_count
            FROM predictions_v2
            GROUP BY telegram_id, competition_key, season_key, match_id
            HAVING row_count > 1
        )
        """
    ).fetchone()[0]
    if duplicate_count:
        raise PredictionMigrationError("Prediction copy created duplicate logical identities")

    mismatch_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM predictions AS legacy
        LEFT JOIN predictions_v2 AS migrated ON migrated.id = legacy.id
        WHERE migrated.id IS NULL
           OR migrated.telegram_id != legacy.telegram_id
           OR migrated.competition_key != 'worldcup2026'
           OR migrated.season_key != '2026'
           OR migrated.match_id != CAST(legacy.match_id AS TEXT)
           OR migrated.prediction_type != 'result'
           OR migrated.predicted_result != legacy.prediction
           OR migrated.home_score IS NOT NULL
           OR migrated.away_score IS NOT NULL
           OR migrated.points_awarded IS NOT NULL
           OR migrated.evaluated_at IS NOT NULL
           OR migrated.created_at != legacy.created_at
           OR migrated.updated_at != legacy.updated_at
        """
    ).fetchone()[0]
    if mismatch_count:
        raise PredictionMigrationError("Prediction copy verification failed")


def migrate_prediction_v2(db_path, *, backup_confirmed=False):
    path = Path(db_path)
    if not path.exists():
        raise PredictionMigrationError("Database path does not exist")

    conn = sqlite3.connect(path)
    try:
        state = prediction_schema_state(conn)
        if state == "v2":
            return {"action": "no-op", "reason": "prediction_v2 already present"}
        if state == "missing":
            return {"action": "no-op", "reason": "no predictions table to migrate"}
        if state != "legacy":
            raise PredictionMigrationError("Unknown predictions schema; migration aborted")
        if not backup_confirmed:
            raise PredictionMigrationError("Legacy migration requires backup confirmation")

        conn.execute("BEGIN IMMEDIATE")
        if prediction_schema_state(conn) != "legacy":
            raise PredictionMigrationError("Predictions schema changed before migration lock")
        if table_exists(conn, "predictions_legacy"):
            raise PredictionMigrationError("predictions_legacy already exists; migration aborted")

        invalid_rows = conn.execute(
            """
            SELECT COUNT(*) FROM predictions
            WHERE prediction NOT IN ('home', 'draw', 'away')
               OR created_at IS NULL
               OR updated_at IS NULL
            """
        ).fetchone()[0]
        if invalid_rows:
            raise PredictionMigrationError("Legacy predictions contain rows that cannot be safely preserved")

        create_predictions_v2_table(conn, "predictions_v2")
        source_count = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        conn.execute(
            """
            INSERT INTO predictions_v2 (
                id, telegram_id, competition_key, season_key, match_id,
                prediction_type, predicted_result, home_score, away_score,
                points_awarded, evaluated_at, created_at, updated_at
            )
            SELECT
                id, telegram_id, 'worldcup2026', '2026', CAST(match_id AS TEXT),
                'result', prediction, NULL, NULL,
                NULL, NULL, created_at, updated_at
            FROM predictions
            """
        )
        verify_legacy_copy(conn, source_count)
        conn.execute("ALTER TABLE predictions RENAME TO predictions_legacy")
        conn.execute("ALTER TABLE predictions_v2 RENAME TO predictions")
        record_prediction_v2_migration(conn)
        conn.commit()
        return {"action": "migrated", "rows": source_count}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Explicit MatchPulse prediction v2 migration")
    parser.add_argument("--db", required=True, help="Path to the SQLite database")
    parser.add_argument("--migrate", action="store_true", help="Perform the migration")
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        help="Confirm that a verified database backup exists",
    )
    args = parser.parse_args()

    try:
        if args.migrate:
            result = migrate_prediction_v2(
                args.db,
                backup_confirmed=args.backup_confirmed,
            )
        else:
            result = inspect_prediction_database(args.db)
    except PredictionMigrationError as error:
        parser.error(str(error))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
