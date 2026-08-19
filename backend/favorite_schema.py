from prediction_schema import (
    create_schema_migrations_table,
    has_unique_index,
    table_columns,
    table_exists,
)


FAVORITE_TEAMS_V2_MIGRATION_ID = "favorite_teams_v2"

FAVORITE_TEAMS_V2_COLUMNS = {
    "id",
    "telegram_id",
    "competition_key",
    "team_id",
    "created_at",
}

LEGACY_FAVORITE_TEAMS_COLUMNS = {
    "id",
    "telegram_id",
    "team_id",
    "team_key",
    "team_name",
    "team_data",
}


def favorite_teams_schema_state(conn):
    if not table_exists(conn, "favorite_teams"):
        return "missing"

    columns = table_columns(conn, "favorite_teams")
    column_names = set(columns)
    table_sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'favorite_teams'"
    ).fetchone()
    table_sql = str(table_sql_row[0] or "").lower() if table_sql_row else ""

    if (
        column_names == FAVORITE_TEAMS_V2_COLUMNS
        and columns["id"]["type"] == "INTEGER"
        and columns["telegram_id"]["type"] == "INTEGER"
        and columns["telegram_id"]["notnull"]
        and columns["competition_key"]["type"] == "TEXT"
        and columns["competition_key"]["notnull"]
        and columns["team_id"]["type"] == "TEXT"
        and columns["team_id"]["notnull"]
        and columns["created_at"]["type"] == "TEXT"
        and columns["created_at"]["notnull"]
        and "default current_timestamp" in table_sql
        and has_unique_index(
            conn,
            "favorite_teams",
            ("telegram_id", "competition_key", "team_id"),
        )
    ):
        return "v2"

    if (
        column_names == LEGACY_FAVORITE_TEAMS_COLUMNS
        and columns["id"]["type"] == "INTEGER"
        and columns["telegram_id"]["type"] == "INTEGER"
        and columns["team_id"]["type"] == "INTEGER"
        and has_unique_index(conn, "favorite_teams", ("telegram_id", "team_id"))
    ):
        return "legacy"

    return "unknown"


def favorite_teams_v2_migration_recorded(conn):
    return table_exists(conn, "schema_migrations") and conn.execute(
        "SELECT 1 FROM schema_migrations WHERE migration_id = ?",
        (FAVORITE_TEAMS_V2_MIGRATION_ID,),
    ).fetchone() is not None


def record_favorite_teams_v2_migration(conn):
    create_schema_migrations_table(conn)
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (migration_id) VALUES (?)",
        (FAVORITE_TEAMS_V2_MIGRATION_ID,),
    )


def create_favorite_teams_v2_table(conn, table_name="favorite_teams"):
    if table_name not in {"favorite_teams", "favorite_teams_v2"}:
        raise ValueError("Unsupported favorite teams table name")

    conn.execute(
        f"""
        CREATE TABLE {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            competition_key TEXT NOT NULL,
            team_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_id, competition_key, team_id)
        )
        """
    )


def ensure_favorite_teams_v2_schema(conn):
    state = favorite_teams_schema_state(conn)
    if state == "missing":
        create_favorite_teams_v2_table(conn)
        record_favorite_teams_v2_migration(conn)
    elif state == "v2":
        record_favorite_teams_v2_migration(conn)
    return state
