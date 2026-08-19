import math
import time
from datetime import datetime


UNUSABLE_PARTICIPANT_LABELS = {
    "",
    "-",
    "tbd",
    "unknown",
    "null",
    "none",
    "نامشخص",
}


def trusted_prediction_kickoff(match):
    if not isinstance(match, dict):
        return None

    for key in ("kickoff_ts", "kickoff_timestamp"):
        value = match.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(timestamp) and timestamp > 0:
            return timestamp

    for key in ("kickoff_utc", "kickoff_iso", "kickoff"):
        value = match.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            continue
        return parsed.timestamp()

    return None


def has_stable_match_id(match):
    value = match.get("id") if isinstance(match, dict) else None
    return value is not None and bool(str(value).strip())


def participant_is_displayable(match, side):
    candidates = (
        match.get(f"{side}_en"),
        match.get(f"{side}_fa"),
        match.get(f"{side}_team"),
        match.get(f"{side}_team_name_en"),
        match.get(f"{side}_team_name_fa"),
        match.get(f"{side}_name_en"),
        match.get(f"{side}_name_fa"),
    )
    return any(
        str(value).strip().casefold() not in UNUSABLE_PARTICIPANT_LABELS
        for value in candidates
        if value is not None
    )


def prediction_is_predictable(match, now_timestamp=None):
    if not isinstance(match, dict):
        return False
    if not has_stable_match_id(match):
        return False
    if not participant_is_displayable(match, "home") or not participant_is_displayable(match, "away"):
        return False
    if match.get("is_live") is True or match.get("is_finished") is True:
        return False

    status = str(match.get("status") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if match.get("is_upcoming") is not True or status != "upcoming":
        return False

    kickoff_timestamp = trusted_prediction_kickoff(match)
    if kickoff_timestamp is None:
        return False
    current_timestamp = time.time() if now_timestamp is None else now_timestamp
    return kickoff_timestamp > current_timestamp


def prediction_is_locked(match, now_timestamp=None):
    return not prediction_is_predictable(match, now_timestamp)
