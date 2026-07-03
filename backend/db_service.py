import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "matchpulse.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            language_code TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS favorite_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            team_id INTEGER,
            team_key TEXT,
            team_name TEXT,
            team_data TEXT,
            UNIQUE(telegram_id, team_id)
        )
        """
    )

    ensure_column(cursor, "favorite_teams", "team_key", "TEXT")
    ensure_column(cursor, "favorite_teams", "team_name", "TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            match_id INTEGER,
            match_data TEXT,
            notified INTEGER DEFAULT 0,
            UNIQUE(telegram_id, match_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS match_score_overrides (
            match_id INTEGER PRIMARY KEY,
            external_match_id INTEGER,
            status TEXT,
            home_score INTEGER,
            away_score INTEGER,
            result TEXT,
            last_updated TEXT,
            source TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            prediction TEXT NOT NULL CHECK(prediction IN ('home', 'draw', 'away')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_id, match_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sent_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_key TEXT UNIQUE,
            user_id INTEGER,
            match_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    ensure_live_notification_tables(conn)

    conn.commit()
    conn.close()

    print("Database initialized...")


def ensure_column(cursor, table_name, column_name, column_type):
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if column_name not in existing_columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def normalize_team_key(value):
    return (
        "".join(str(value or "").strip().lower().split())
        .replace("\u200c", "")
        .replace("-", "")
        .replace("_", "")
    )


ALLOWED_PREDICTIONS = {"home", "draw", "away"}


def save_prediction(telegram_id, match_id, prediction):
    if prediction not in ALLOWED_PREDICTIONS:
        raise ValueError("Invalid prediction")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO predictions (telegram_id, match_id, prediction)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id, match_id) DO UPDATE SET
            prediction = excluded.prediction,
            updated_at = CURRENT_TIMESTAMP
        """,
        (telegram_id, match_id, prediction),
    )
    conn.commit()
    conn.close()
    return get_prediction(telegram_id, match_id)


def get_user_predictions(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, telegram_id, match_id, prediction, created_at, updated_at
        FROM predictions
        WHERE telegram_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (telegram_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "telegram_id": row[1],
            "match_id": row[2],
            "prediction": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }
        for row in rows
    ]


def get_prediction(telegram_id, match_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, telegram_id, match_id, prediction, created_at, updated_at
        FROM predictions
        WHERE telegram_id = ? AND match_id = ?
        """,
        (telegram_id, match_id),
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row[0],
        "telegram_id": row[1],
        "match_id": row[2],
        "prediction": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }


def delete_prediction(telegram_id, match_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM predictions WHERE telegram_id = ? AND match_id = ?",
        (telegram_id, match_id),
    )
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def canonical_prediction_result(match):
    if not isinstance(match, dict):
        return None

    status = str(match.get("status") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if match.get("is_finished") is not True and status not in {
        "finished", "finish", "ft", "full_time", "fulltime", "completed", "complete", "final",
    }:
        return None

    result = str(match.get("result") or "").strip().lower()
    if result in ALLOWED_PREDICTIONS:
        return result

    penalty_winner = str(match.get("penalty_winner_side") or "").strip().lower()
    if penalty_winner in {"home", "away"}:
        return penalty_winner

    score_source = str(match.get("score_source") or "").strip().lower()
    trusted_score_sources = {
        "raw_final", "raw_score", "events", "scorers", "worldcup_wrapper", "varzesh3", "score_override",
    }
    if score_source not in trusted_score_sources:
        return None

    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    if home_score is None:
        home_score = score.get("home")
    if away_score is None:
        away_score = score.get("away")

    try:
        home_score = int(home_score)
        away_score = int(away_score)
    except (TypeError, ValueError):
        return None

    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def get_prediction_stats(telegram_id, matches):
    predictions = get_user_predictions(telegram_id)
    matches_by_id = {str(match.get("id")): match for match in matches}
    correct = 0
    wrong = 0
    pending = 0

    for prediction in predictions:
        match = matches_by_id.get(str(prediction["match_id"]))
        result = canonical_prediction_result(match)
        if result is None:
            pending += 1
        elif prediction["prediction"] == result:
            correct += 1
        else:
            wrong += 1

    return {
        "points": correct * 3,
        "correct": correct,
        "wrong": wrong,
        "pending": pending,
        "total": len(predictions),
    }


def team_key_from_data(team):
    return normalize_team_key(
        team.get("team_key")
        or team.get("name_en")
        or team.get("home_en")
        or team.get("away_en")
        or team.get("name_fa")
        or team.get("team_name")
        or team.get("name")
        or team.get("id")
    )


def prepare_favorite_team(team):
    item = dict(team)
    item["team_key"] = item.get("team_key") or team_key_from_data(item)
    item["team_name"] = item.get("team_name") or item.get("name_en") or item.get("name_fa") or item.get("name")
    return item


def save_user_to_db(user):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO users (
            telegram_id,
            first_name,
            last_name,
            username,
            language_code
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user.telegram_id,
            user.first_name,
            user.last_name,
            user.username,
            user.language_code,
        ),
    )

    conn.commit()
    conn.close()


def get_all_users_from_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT telegram_id, first_name, last_name, username, language_code
        FROM users
        """
    )

    rows = cursor.fetchall()
    conn.close()

    users = []

    for row in rows:
        users.append(
            {
                "telegram_id": row[0],
                "first_name": row[1],
                "last_name": row[2],
                "username": row[3],
                "language_code": row[4],
            }
        )

    return users


def save_favorite_team_to_db(telegram_id, team):
    conn = get_connection()
    cursor = conn.cursor()
    favorite_team = prepare_favorite_team(team)

    cursor.execute(
        """
        INSERT OR IGNORE INTO favorite_teams (
            telegram_id,
            team_id,
            team_key,
            team_name,
            team_data
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            telegram_id,
            favorite_team["id"],
            favorite_team["team_key"],
            favorite_team["team_name"],
            json.dumps(favorite_team, ensure_ascii=False),
        ),
    )

    conn.commit()
    conn.close()


def get_favorite_teams_from_db(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT team_data
        FROM favorite_teams
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [prepare_favorite_team(json.loads(row[0])) for row in rows]


def delete_favorite_team_from_db(telegram_id, team_id, team_key=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM favorite_teams
        WHERE telegram_id = ?
          AND (
            team_id = ?
            OR team_key = ?
          )
        """,
        (telegram_id, team_id, team_key),
    )

    deleted_count = cursor.rowcount

    conn.commit()
    conn.close()

    return deleted_count > 0


def save_reminder_to_db(telegram_id, match):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO reminders (
            telegram_id,
            match_id,
            match_data,
            notified
        )
        VALUES (?, ?, ?, 0)
        """,
        (
            telegram_id,
            match["id"],
            json.dumps(match, ensure_ascii=False),
        ),
    )

    conn.commit()
    conn.close()


def get_reminders_from_db(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT match_data, notified
        FROM reminders
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    reminders = []

    for row in rows:
        match = json.loads(row[0])
        match["notified"] = bool(row[1])
        reminders.append(match)

    return reminders


def delete_reminder_from_db(telegram_id, match_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM reminders
        WHERE telegram_id = ? AND match_id = ?
        """,
        (telegram_id, match_id),
    )

    deleted_count = cursor.rowcount

    conn.commit()
    conn.close()

    return deleted_count > 0


def get_all_reminders_from_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT telegram_id, match_data, notified
        FROM reminders
        """
    )

    rows = cursor.fetchall()
    conn.close()

    result = {}

    for row in rows:
        telegram_id = row[0]
        match = json.loads(row[1])
        match["notified"] = bool(row[2])

        if telegram_id not in result:
            result[telegram_id] = []

        result[telegram_id].append(match)

    return result


def mark_reminder_notified(telegram_id, match_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE reminders
        SET notified = 1
        WHERE telegram_id = ? AND match_id = ?
        """,
        (telegram_id, match_id),
    )

    conn.commit()
    conn.close()
 

def get_all_favorite_teams_from_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT telegram_id, team_data
        FROM favorite_teams
        """
    )

    rows = cursor.fetchall()
    conn.close()

    result = {}

    for row in rows:
        telegram_id = row[0]
        team = prepare_favorite_team(json.loads(row[1]))

        if telegram_id not in result:
            result[telegram_id] = []

        result[telegram_id].append(team)

    return result 


def has_sent_notification(notification_key):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM sent_notifications
        WHERE notification_key = ?
        LIMIT 1
        """,
        (notification_key,),
    )

    row = cursor.fetchone()
    conn.close()

    return row is not None


def mark_notification_sent(notification_key, user_id=None, match_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO sent_notifications (
            notification_key,
            user_id,
            match_id
        )
        VALUES (?, ?, ?)
        """,
        (notification_key, user_id, str(match_id) if match_id is not None else None),
    )

    inserted = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return inserted


def delete_live_notification_history():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM sent_notifications
        WHERE notification_key LIKE 'global_match_start:%'
           OR notification_key LIKE 'global_match_finished:%'
           OR notification_key LIKE 'favorite_match_start:%'
           OR notification_key LIKE 'favorite_match_finished:%'
           OR notification_key LIKE 'favorite_goal_for:%'
           OR notification_key LIKE 'favorite_goal_against:%'
        """
    )

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted_count


def get_all_users():
    return get_all_users_from_db()


def add_favorite_team(user_id, team):
    save_favorite_team_to_db(user_id, team)
    return get_favorite_teams_from_db(user_id)


def remove_favorite_team(user_id, team):
    team_id = team.get("id") if isinstance(team, dict) else team
    delete_favorite_team_from_db(user_id, team_id)
    return get_favorite_teams_from_db(user_id)


def get_favorite_teams(user_id):
    return get_favorite_teams_from_db(user_id)


def get_users_by_favorite_team(team_name):
    requested_key = normalize_team_key(team_name)
    users = []

    for telegram_id, teams in get_all_favorite_teams_from_db().items():
        for team in teams:
            keys = {
                normalize_team_key(team.get("team_key")),
                normalize_team_key(team.get("team_name")),
                normalize_team_key(team.get("name_en")),
                normalize_team_key(team.get("name_fa")),
            }

            if requested_key in keys:
                users.append(telegram_id)
                break

    return users


def save_match_score_override_to_db(override):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO match_score_overrides (
            match_id,
            external_match_id,
            status,
            home_score,
            away_score,
            result,
            last_updated,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id) DO UPDATE SET
            external_match_id = excluded.external_match_id,
            status = excluded.status,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            result = excluded.result,
            last_updated = excluded.last_updated,
            source = excluded.source
        """,
        (
            override["match_id"],
            override.get("external_match_id"),
            override.get("status"),
            override.get("home_score"),
            override.get("away_score"),
            override.get("result"),
            override.get("last_updated"),
            override.get("source"),
        ),
    )

    conn.commit()
    conn.close()


def get_all_match_score_overrides_from_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            match_id,
            external_match_id,
            status,
            home_score,
            away_score,
            result,
            last_updated,
            source
        FROM match_score_overrides
        """
    )

    rows = cursor.fetchall()
    conn.close()

    overrides = {}

    for row in rows:
        overrides[row[0]] = {
            "match_id": row[0],
            "external_match_id": row[1],
            "status": row[2],
            "home_score": row[3],
            "away_score": row[4],
            "result": row[5],
            "last_updated": row[6],
            "source": row[7],
        }

    return overrides


def ensure_live_notification_tables(conn=None):
    owns_connection = conn is None

    if owns_connection:
        conn = get_connection()

    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS live_notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL,
            event_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_id, match_id, notification_type, event_key)
        )
        """
    )

    if owns_connection:
        conn.commit()
        conn.close()


def match_id_value(match):
    return match.get("id") or match.get("internal_match_id") or match.get("match_id")


def match_team_keys(match, side):
    values = [
        match.get(f"{side}_team_id"),
        match.get(f"{side}_id"),
        match.get(f"{side}_en"),
        match.get(f"{side}_fa"),
        match.get(f"{side}_name"),
        match.get(f"{side}_team"),
        match.get(f"{side}_team_name"),
        match.get(f"{side}_team_name_en"),
        match.get(f"{side}_team_name_fa"),
    ]

    return {
        normalize_team_key(value)
        for value in values
        if value is not None and str(value).strip()
    }


def favorite_team_keys(team):
    prepared = prepare_favorite_team(team)
    values = [
        prepared.get("id"),
        prepared.get("team_id"),
        prepared.get("team_key"),
        prepared.get("team_name"),
        prepared.get("name"),
        prepared.get("name_en"),
        prepared.get("name_fa"),
        prepared.get("short_name"),
        prepared.get("fifa_code"),
    ]

    return {
        normalize_team_key(value)
        for value in values
        if value is not None and str(value).strip()
    }


def favorite_team_matches_match(team, match):
    favorite_keys = favorite_team_keys(team)

    if not favorite_keys:
        return False

    return bool(
        favorite_keys.intersection(match_team_keys(match, "home"))
        or favorite_keys.intersection(match_team_keys(match, "away"))
    )


def get_relevant_users_for_match(match):
    match_id = match_id_value(match)
    relevant_users = set()

    if match_id is None:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT telegram_id
        FROM reminders
        WHERE match_id = ?
        """,
        (match_id,),
    )

    relevant_users.update(row[0] for row in cursor.fetchall())

    cursor.execute(
        """
        SELECT telegram_id, team_data
        FROM favorite_teams
        """
    )

    favorite_rows = cursor.fetchall()
    conn.close()

    for telegram_id, team_data in favorite_rows:
        try:
            team = json.loads(team_data)
        except (TypeError, json.JSONDecodeError):
            continue

        if favorite_team_matches_match(team, match):
            relevant_users.add(telegram_id)

    return sorted(relevant_users)


def has_live_notification_been_sent(telegram_id, match_id, notification_type, event_key):
    ensure_live_notification_tables()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM live_notification_log
        WHERE telegram_id = ?
          AND match_id = ?
          AND notification_type = ?
          AND event_key = ?
        LIMIT 1
        """,
        (telegram_id, match_id, notification_type, event_key),
    )

    row = cursor.fetchone()
    conn.close()
    return row is not None


def mark_live_notification_sent(telegram_id, match_id, notification_type, event_key):
    ensure_live_notification_tables()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO live_notification_log (
            telegram_id,
            match_id,
            notification_type,
            event_key,
            created_at
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (telegram_id, match_id, notification_type, event_key),
    )

    inserted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return inserted
