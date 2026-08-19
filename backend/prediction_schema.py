PREDICTION_V2_MIGRATION_ID = "prediction_v2"

PREDICTION_V2_COLUMNS = {
    "id",
    "telegram_id",
    "competition_key",
    "season_key",
    "match_id",
    "prediction_type",
    "predicted_result",
    "home_score",
    "away_score",
    "points_awarded",
    "evaluated_at",
    "created_at",
    "updated_at",
}

LEGACY_PREDICTION_COLUMNS = {
    "id",
    "telegram_id",
    "match_id",
    "prediction",
    "created_at",
    "updated_at",
}


def table_exists(conn, table_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)
    ).fetchone() is not None


def table_columns(conn, table_name):
    return {
        row[1]: {"type": str(row[2] or "").upper(), "notnull": bool(row[3])}
        for row in conn.execute(f"PRAGMA table_info({table_name})")
    }


def has_unique_index(conn, table_name, columns):
    for index in conn.execute(f"PRAGMA index_list({table_name})"):
        if not index[2]:
            continue
        index_columns = [
            row[2] for row in conn.execute(f"PRAGMA index_info({index[1]})")
        ]
        if index_columns == list(columns):
            return True
    return False


def prediction_schema_state(conn):
    if not table_exists(conn, "predictions"):
        return "missing"

    columns = table_columns(conn, "predictions")
    column_names = set(columns)
    table_sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'predictions'"
    ).fetchone()
    table_sql = str(table_sql_row[0] or "").lower() if table_sql_row else ""

    if (
        PREDICTION_V2_COLUMNS.issubset(column_names)
        and columns["match_id"]["type"] == "TEXT"
        and has_unique_index(
            conn,
            "predictions",
            ("telegram_id", "competition_key", "season_key", "match_id"),
        )
        and "exact_score" in table_sql
        and "predicted_result" in table_sql
    ):
        return "v2"

    if (
        LEGACY_PREDICTION_COLUMNS.issubset(column_names)
        and column_names.isdisjoint(PREDICTION_V2_COLUMNS - {"id", "telegram_id", "match_id", "created_at", "updated_at"})
        and has_unique_index(conn, "predictions", ("telegram_id", "match_id"))
    ):
        return "legacy"

    return "unknown"


def create_schema_migrations_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def record_prediction_v2_migration(conn):
    create_schema_migrations_table(conn)
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (migration_id) VALUES (?)",
        (PREDICTION_V2_MIGRATION_ID,),
    )


def create_predictions_v2_table(conn, table_name="predictions"):
    if table_name not in {"predictions", "predictions_v2"}:
        raise ValueError("Unsupported prediction table name")

    conn.execute(
        f"""
        CREATE TABLE {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            competition_key TEXT NOT NULL,
            season_key TEXT NOT NULL,
            match_id TEXT NOT NULL,
            prediction_type TEXT NOT NULL CHECK(prediction_type IN ('result', 'exact_score')),
            predicted_result TEXT,
            home_score INTEGER,
            away_score INTEGER,
            points_awarded INTEGER,
            evaluated_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK(points_awarded IS NULL OR points_awarded >= 0),
            CHECK(
                (prediction_type = 'result'
                    AND predicted_result IN ('home', 'draw', 'away')
                    AND home_score IS NULL
                    AND away_score IS NULL)
                OR
                (prediction_type = 'exact_score'
                    AND home_score IS NOT NULL
                    AND away_score IS NOT NULL
                    AND home_score >= 0
                    AND away_score >= 0
                    AND predicted_result = CASE
                        WHEN home_score > away_score THEN 'home'
                        WHEN home_score < away_score THEN 'away'
                        ELSE 'draw'
                    END)
            ),
            UNIQUE(telegram_id, competition_key, season_key, match_id)
        )
        """
    )


def ensure_prediction_v2_schema(conn):
    state = prediction_schema_state(conn)
    if state == "missing":
        create_predictions_v2_table(conn)
        record_prediction_v2_migration(conn)
    elif state == "v2":
        record_prediction_v2_migration(conn)
    return state
