"""Daily aggregation uses one bounded wrapper request, never season retrieval."""
import re
from datetime import date as calendar_date, datetime
from zoneinfo import ZoneInfo

from competition_service import get_competition
from season_service import get_season
from services.generic_football_adapter import (
    GenericFootballProviderError, get_daily_matches, normalize_match,
)


TEHRAN_TZ = ZoneInfo("Asia/Tehran")
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def parse_requested_date(value):
    normalized = str(value or "")
    if not DATE_PATTERN.fullmatch(normalized):
        raise ValueError("Date must use YYYY-MM-DD format")
    parsed = calendar_date.fromisoformat(normalized)
    if parsed.isoformat() != normalized:
        raise ValueError("Date must use YYYY-MM-DD format")
    return parsed


def safe_error(competition_key=None, season_key=None):
    return {
        "competition_key": competition_key,
        "season_key": season_key,
        "code": "provider_failure",
        "message": "Daily matches could not be loaded.",
    }


def normalize_daily_group(group, target_date):
    if not isinstance(group, dict) or not isinstance(group.get("competition"), dict):
        raise ValueError("Invalid daily group")
    identity = group["competition"]
    key, season_key = identity.get("key"), identity.get("season_key")
    if not isinstance(key, str) or not isinstance(season_key, str):
        raise ValueError("Invalid daily scope")
    competition = get_competition(key)
    season = get_season(key, season_key)
    if not competition or not season or competition.get("is_active") is not True or competition.get("supports_matches") is not True:
        raise ValueError("Unsupported daily scope")
    if not isinstance(group.get("matches"), list):
        raise ValueError("Invalid daily matches")

    matches = []
    for raw in group["matches"]:
        if not isinstance(raw, dict):
            raise ValueError("Invalid daily match")
        if raw.get("competition_key") != key or raw.get("season_key") != season_key:
            raise ValueError("Invalid daily match scope")
        if not isinstance(raw.get("id"), str) or not raw["id"].startswith("mp_match_"):
            raise ValueError("Invalid daily identity")
        for field in ("home_team_id", "away_team_id"):
            team_id = raw.get(field)
            if team_id is not None and (not isinstance(team_id, str) or not team_id.startswith("mp_team_")):
                raise ValueError("Invalid daily team identity")
        kickoff_value = raw.get("kickoff_utc")
        if not isinstance(kickoff_value, str):
            raise ValueError("Invalid daily kickoff")
        kickoff = datetime.fromisoformat(kickoff_value.replace("Z", "+00:00"))
        if kickoff.tzinfo is None or kickoff.utcoffset() is None:
            raise ValueError("Invalid daily kickoff")
        if kickoff.astimezone(TEHRAN_TZ).date().isoformat() != target_date:
            raise ValueError("Invalid daily date")
        match = normalize_match(raw, competition_format=competition.get("format"))
        match.pop("provider", None)
        match.pop("external_match_id", None)
        matches.append(match)

    return {
        "competition": {
            "key": key, "name": competition.get("name_en"),
            "name_fa": competition.get("name_fa"), "season_key": season_key,
            "type": competition.get("type"),
        },
        "matches": matches,
    }


def aggregate_matches_by_date(requested_date):
    target_date = parse_requested_date(requested_date).isoformat()
    result = {"date": target_date, "groups": [], "errors": []}
    try:
        payload = get_daily_matches(target_date)
    except GenericFootballProviderError:
        result["errors"].append(safe_error())
        return result

    for group in payload["groups"]:
        try:
            normalized = normalize_daily_group(group, target_date)
        except (ValueError, TypeError, OverflowError):
            result["errors"].append(safe_error())
            continue
        if normalized["matches"]:
            result["groups"].append(normalized)
    # Keep valid groups on partial failure, but never reflect provider diagnostics.
    for error in payload["errors"]:
        key = error.get("competition_key") if isinstance(error, dict) else None
        season_key = error.get("season_key") if isinstance(error, dict) else None
        if isinstance(key, str) and isinstance(season_key, str) and get_season(key, season_key):
            result["errors"].append(safe_error(key, season_key))
        else:
            result["errors"].append(safe_error())
    return result
