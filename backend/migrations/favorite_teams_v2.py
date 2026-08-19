"""Explicit Favorites V2 migration.

Recovery rules:
- Before commit, any failure rolls the transaction back.
- After commit and before V2 writes, an operator may reverse the table renames manually.
- After V2 writes, restore a verified backup or perform explicit data reconciliation.

This module never performs destructive automatic rollback and never looks up teams over
the network. Only exact IDs from the supplied trusted World Cup ID snapshot can migrate.
"""

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

from favorite_schema import (
    create_favorite_teams_v2_table,
    favorite_teams_schema_state,
    favorite_teams_v2_migration_recorded,
    record_favorite_teams_v2_migration,
)
from prediction_schema import table_exists


class FavoriteTeamsMigrationError(RuntimeError):
    pass


def normalize_trusted_worldcup_team_ids(values):
    if isinstance(values, (str, bytes, dict)):
        raise FavoriteTeamsMigrationError(
            "Trusted World Cup team IDs must be a collection"
        )
    try:
        raw_values = list(values)
    except TypeError as error:
        raise FavoriteTeamsMigrationError(
            "Trusted World Cup team IDs must be a collection"
        ) from error

    normalized = []
    for value in raw_values:
        if isinstance(value, bool) or value is None or isinstance(value, (dict, list)):
            raise FavoriteTeamsMigrationError("Trusted World Cup team IDs contain an invalid ID")
        canonical_id = str(value)
        if not canonical_id or canonical_id != canonical_id.strip():
            raise FavoriteTeamsMigrationError("Trusted World Cup team IDs contain an invalid ID")
        normalized.append(canonical_id)

    if len(normalized) != len(set(normalized)):
        raise FavoriteTeamsMigrationError("Trusted World Cup team IDs contain duplicate IDs")
    return frozenset(normalized)


def inspect_favorite_teams_database(db_path):
    path = Path(db_path)
    if not path.exists():
        raise FavoriteTeamsMigrationError("Database path does not exist")

    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        return {
            "database": str(path),
            "favorites_schema": favorite_teams_schema_state(conn),
            "has_favorite_teams_legacy": table_exists(conn, "favorite_teams_legacy"),
            "has_favorite_teams_v2_temporary": table_exists(conn, "favorite_teams_v2"),
            "migration_recorded": favorite_teams_v2_migration_recorded(conn),
        }
    finally:
        conn.close()


def trusted_worldcup_team_ids_from_file(snapshot_path):
    path = Path(snapshot_path)
    if not path.exists():
        raise FavoriteTeamsMigrationError("Trusted World Cup team-ID snapshot does not exist")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FavoriteTeamsMigrationError(
            "Trusted World Cup team-ID snapshot is invalid"
        ) from error

    if not isinstance(payload, list):
        raise FavoriteTeamsMigrationError(
            "Trusted World Cup team-ID snapshot must be a JSON array"
        )

    return normalize_trusted_worldcup_team_ids(payload)


def classify_legacy_rows(rows, trusted_worldcup_team_ids):
    trusted_ids = normalize_trusted_worldcup_team_ids(trusted_worldcup_team_ids)
    resolved = []
    unresolved_rows = 0

    for legacy_id, telegram_id, legacy_team_id in rows:
        canonical_team_id = None if legacy_team_id is None else str(legacy_team_id)
        if (
            isinstance(telegram_id, bool)
            or not isinstance(telegram_id, int)
            or telegram_id <= 0
            or canonical_team_id not in trusted_ids
        ):
            unresolved_rows += 1
            continue
        resolved.append(
            (legacy_id, telegram_id, "worldcup2026", canonical_team_id)
        )

    return resolved, unresolved_rows


def composite_conflict_count(resolved_rows):
    identities = Counter(
        (telegram_id, competition_key, team_id)
        for _, telegram_id, competition_key, team_id in resolved_rows
    )
    return sum(count for count in identities.values() if count > 1)


def verify_favorite_teams_copy(conn, source_rows, resolved_rows, unresolved_rows):
    source_count = len(source_rows)
    resolved_count = len(resolved_rows)
    if resolved_count + unresolved_rows != source_count:
        raise FavoriteTeamsMigrationError("Favorite classification count mismatch")

    target_count = conn.execute("SELECT COUNT(*) FROM favorite_teams_v2").fetchone()[0]
    if target_count != resolved_count:
        raise FavoriteTeamsMigrationError("Favorite copy row count mismatch")

    duplicate_count = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT telegram_id, competition_key, team_id, COUNT(*) AS row_count
            FROM favorite_teams_v2
            GROUP BY telegram_id, competition_key, team_id
            HAVING row_count > 1
        )
        """
    ).fetchone()[0]
    if duplicate_count:
        raise FavoriteTeamsMigrationError("Favorite copy created composite duplicates")

    mismatch_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM favorite_teams_v2 AS migrated
        LEFT JOIN favorite_teams AS legacy ON legacy.id = migrated.id
        WHERE legacy.id IS NULL
           OR migrated.telegram_id != legacy.telegram_id
           OR migrated.competition_key != 'worldcup2026'
           OR migrated.team_id != CAST(legacy.team_id AS TEXT)
        """
    ).fetchone()[0]
    if mismatch_count:
        raise FavoriteTeamsMigrationError("Favorite copy verification failed")


def migrate_favorite_teams_v2(
    db_path,
    *,
    trusted_worldcup_team_ids,
    backup_confirmed=False,
):
    path = Path(db_path)
    if not path.exists():
        raise FavoriteTeamsMigrationError("Database path does not exist")

    conn = sqlite3.connect(path)
    try:
        state = favorite_teams_schema_state(conn)
        migration_recorded = favorite_teams_v2_migration_recorded(conn)
        has_legacy_backup = table_exists(conn, "favorite_teams_legacy")
        has_temporary_v2 = table_exists(conn, "favorite_teams_v2")

        if has_temporary_v2:
            raise FavoriteTeamsMigrationError(
                "favorite_teams_v2 already exists; migration aborted"
            )
        if state == "v2":
            if migration_recorded:
                return {"action": "no-op", "reason": "favorite_teams_v2 already present"}
            raise FavoriteTeamsMigrationError(
                "Favorites V2 schema exists without its migration marker"
            )
        if has_legacy_backup:
            raise FavoriteTeamsMigrationError(
                "favorite_teams_legacy already exists; migration aborted"
            )
        if state == "missing":
            return {"action": "no-op", "reason": "no favorite_teams table to migrate"}
        if state != "legacy":
            raise FavoriteTeamsMigrationError(
                "Unknown favorites schema; migration aborted"
            )
        if not backup_confirmed:
            raise FavoriteTeamsMigrationError(
                "Legacy favorites migration requires backup confirmation"
            )

        conn.execute("BEGIN IMMEDIATE")
        if favorite_teams_schema_state(conn) != "legacy":
            raise FavoriteTeamsMigrationError(
                "Favorites schema changed before migration lock"
            )
        if table_exists(conn, "favorite_teams_legacy"):
            raise FavoriteTeamsMigrationError(
                "favorite_teams_legacy already exists; migration aborted"
            )
        if table_exists(conn, "favorite_teams_v2"):
            raise FavoriteTeamsMigrationError(
                "favorite_teams_v2 already exists; migration aborted"
            )

        source_rows = conn.execute(
            "SELECT id, telegram_id, team_id FROM favorite_teams ORDER BY id"
        ).fetchall()
        resolved_rows, unresolved_rows = classify_legacy_rows(
            source_rows, trusted_worldcup_team_ids
        )
        conflict_rows = composite_conflict_count(resolved_rows)
        if conflict_rows:
            raise FavoriteTeamsMigrationError(
                f"Favorite migration found {conflict_rows} composite conflict rows"
            )

        create_favorite_teams_v2_table(conn, "favorite_teams_v2")
        conn.executemany(
            """
            INSERT INTO favorite_teams_v2 (
                id, telegram_id, competition_key, team_id
            ) VALUES (?, ?, ?, ?)
            """,
            resolved_rows,
        )
        verify_favorite_teams_copy(
            conn, source_rows, resolved_rows, unresolved_rows
        )
        conn.execute("ALTER TABLE favorite_teams RENAME TO favorite_teams_legacy")
        conn.execute("ALTER TABLE favorite_teams_v2 RENAME TO favorite_teams")
        record_favorite_teams_v2_migration(conn)
        conn.commit()
        return {
            "action": "migrated",
            "source_rows": len(source_rows),
            "resolved_rows": len(resolved_rows),
            "unresolved_rows": unresolved_rows,
            "conflict_rows": 0,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Inspect or explicitly migrate MatchPulse favorites to V2"
    )
    parser.add_argument("--db", required=True, help="Path to the SQLite database")
    parser.add_argument("--migrate", action="store_true", help="Perform the migration")
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        help="Confirm that a verified database backup exists",
    )
    parser.add_argument(
        "--trusted-worldcup-team-ids",
        help="UTF-8 JSON array containing exact trusted World Cup team IDs",
    )
    args = parser.parse_args()

    try:
        if args.migrate:
            if not args.trusted_worldcup_team_ids:
                raise FavoriteTeamsMigrationError(
                    "Migration requires --trusted-worldcup-team-ids"
                )
            result = migrate_favorite_teams_v2(
                args.db,
                trusted_worldcup_team_ids=trusted_worldcup_team_ids_from_file(
                    args.trusted_worldcup_team_ids
                ),
                backup_confirmed=args.backup_confirmed,
            )
        else:
            result = inspect_favorite_teams_database(args.db)
    except FavoriteTeamsMigrationError as error:
        parser.error(str(error))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
