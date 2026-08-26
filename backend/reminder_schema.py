REMINDERS_V2_MIGRATION_ID = "reminders_v2"

REMINDERS_V2_COLUMNS = {
    "id",
    "telegram_id",
    "competition_key",
    "season_key",
    "match_id",
    "match_data",
    "notified",
}

LEGACY_REMINDER_COLUMNS = {
    "id",
    "telegram_id",
    "match_id",
    "match_data",
    "notified",
}


def table_exists(conn, table_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)
    ).fetchone() is not None


def table_columns(conn, table_name):
    return {
        row[1]: {
            "type": str(row[2] or "").upper(),
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        }
        for row in conn.execute(f"PRAGMA table_info({table_name})")
    }


def has_unique_index(conn, table_name, columns):
    for index in conn.execute(f"PRAGMA index_list({table_name})"):
        if not index[2]:
            continue
        indexed_columns = [
            row[2] for row in conn.execute(f"PRAGMA index_info({index[1]})")
        ]
        if indexed_columns == list(columns):
            return True
    return False


def reminder_table_state(conn, table_name="reminders"):
    if not table_exists(conn, table_name):
        return "missing"

    columns = table_columns(conn, table_name)
    column_names = set(columns)

    if (
        column_names == REMINDERS_V2_COLUMNS
        and columns["id"]["type"] == "INTEGER"
        and columns["id"]["pk"]
        and columns["telegram_id"]["type"] == "INTEGER"
        and columns["telegram_id"]["notnull"]
        and columns["competition_key"]["type"] == "TEXT"
        and columns["competition_key"]["notnull"]
        and columns["season_key"]["type"] == "TEXT"
        and columns["season_key"]["notnull"]
        and columns["match_id"]["type"] == "TEXT"
        and columns["match_id"]["notnull"]
        and columns["match_data"]["type"] == "TEXT"
        and columns["match_data"]["notnull"]
        and columns["notified"]["type"] == "INTEGER"
        and columns["notified"]["notnull"]
        and str(columns["notified"]["default"]).strip("()'") == "0"
        and has_unique_index(
            conn,
            table_name,
            ("telegram_id", "competition_key", "season_key", "match_id"),
        )
    ):
        return "v2"

    if (
        column_names == LEGACY_REMINDER_COLUMNS
        and columns["id"]["type"] == "INTEGER"
        and columns["id"]["pk"]
        and columns["telegram_id"]["type"] == "INTEGER"
        and columns["match_data"]["type"] == "TEXT"
        and columns["notified"]["type"] == "INTEGER"
        and str(columns["notified"]["default"]).strip("()'") == "0"
        and columns["match_id"]["type"] == "INTEGER"
        and has_unique_index(conn, table_name, ("telegram_id", "match_id"))
    ):
        return "legacy"

    return "unknown"


def reminders_schema_state(conn):
    return reminder_table_state(conn, "reminders")


def create_schema_migrations_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def record_reminders_v2_migration(conn):
    create_schema_migrations_table(conn)
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (migration_id) VALUES (?)",
        (REMINDERS_V2_MIGRATION_ID,),
    )


def reminders_v2_migration_recorded(conn):
    return table_exists(conn, "schema_migrations") and conn.execute(
        "SELECT 1 FROM schema_migrations WHERE migration_id = ?",
        (REMINDERS_V2_MIGRATION_ID,),
    ).fetchone() is not None


def create_reminders_v2_table(conn, table_name="reminders"):
    if table_name not in {"reminders", "reminders_v2"}:
        raise ValueError("Unsupported reminders table name")

    conn.execute(
        f"""
        CREATE TABLE {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            competition_key TEXT NOT NULL,
            season_key TEXT NOT NULL,
            match_id TEXT NOT NULL,
            match_data TEXT NOT NULL,
            notified INTEGER NOT NULL DEFAULT 0,
            UNIQUE (
                telegram_id,
                competition_key,
                season_key,
                match_id
            )
        )
        """
    )


def ensure_reminders_v2_schema(conn):
    state = reminders_schema_state(conn)
    if state == "missing":
        create_reminders_v2_table(conn)
        record_reminders_v2_migration(conn)
    return state
