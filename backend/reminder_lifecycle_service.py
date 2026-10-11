"""Non-destructive reminder retirement; sent/deduplication records are retained."""
from datetime import datetime, timedelta, timezone

from reminder_service import ReminderEligibilityError, validate_reminder_eligibility


def lifecycle_snapshot(match, now=None):
    snapshot = dict(match)
    current = now or datetime.now(timezone.utc)
    try:
        kickoff = validate_reminder_eligibility(snapshot, now=current)
        # Preserve the scheduler's inclusive 65-to-55 minute delivery grace window.
        reason = "trigger_expired" if kickoff - timedelta(minutes=55) < current else None
    except ReminderEligibilityError:
        reason = "match_ineligible"
    if reason:
        snapshot["reminder_state"] = "retired"
        snapshot["retirement_reason"] = reason
    return snapshot


def is_active_reminder(match, now=None):
    if match.get("notified") or match.get("reminder_state") == "retired":
        return False
    if match.get("competition_key") == "worldcup2026":
        return False
    current = now or datetime.now(timezone.utc)
    try:
        kickoff = validate_reminder_eligibility(match, now=current)
        return kickoff - timedelta(minutes=60) > current
    except ReminderEligibilityError:
        return False


def refresh_active_reminders(telegram_id, records, now=None):
    from competition_data_service import get_matches_for_season
    from competition_service import get_competition
    from db_service import update_reminder_snapshot

    groups = {}
    for record in records:
        if record.get("notified") or record.get("reminder_state") == "retired":
            continue
        scope = (record.get("competition_key"), record.get("season_key"))
        competition = get_competition(scope[0])
        if not competition or competition.get("status") != "active":
            continue
        groups.setdefault(scope, []).append(record)
    active = []
    for (competition_key, season_key), entries in groups.items():
        try:
            matches = get_matches_for_season(competition_key, season_key, status="all")
            if not isinstance(matches, list):
                continue
            by_id = {str(match.get("id")): match for match in matches if isinstance(match, dict)}
            for record in entries:
                match_id = str(record["match_id"])
                match = by_id.get(match_id)
                # Provider failure/missing match is not proof of permanent removal.
                if match is None:
                    continue
                snapshot = lifecycle_snapshot({**match, "competition_key": competition_key,
                    "season_key": season_key, "match_id": match_id, "id": match_id}, now)
                old = {key: value for key, value in record.items() if key != "notified"}
                if old != snapshot and not update_reminder_snapshot(
                    telegram_id, match_id, competition_key, season_key, snapshot
                ):
                    continue
                record.clear()
                record.update(snapshot, notified=False)
                if is_active_reminder(record, now):
                    active.append(record)
        except Exception:
            # Fail closed, retain stored history, never display stale active claims.
            print(f"Active reminder refresh unavailable: competition_key={competition_key} season_key={season_key}")
    return active
