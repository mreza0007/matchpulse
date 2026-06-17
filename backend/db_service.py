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
            team_data TEXT,
            UNIQUE(telegram_id, team_id)
        )
        """
    )

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

    conn.commit()
    conn.close()

    print("Database initialized...")


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

    cursor.execute(
        """
        INSERT OR IGNORE INTO favorite_teams (
            telegram_id,
            team_id,
            team_data
        )
        VALUES (?, ?, ?)
        """,
        (
            telegram_id,
            team["id"],
            json.dumps(team, ensure_ascii=False),
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

    return [json.loads(row[0]) for row in rows]


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
        team = json.loads(row[1])

        if telegram_id not in result:
            result[telegram_id] = []

        result[telegram_id].append(team)

    return result 
    