import re
from datetime import date as calendar_date, datetime
from zoneinfo import ZoneInfo

from competition_data_service import get_matches_for_season
from competition_service import get_competitions
from season_service import get_default_season


TEHRAN_TZ = ZoneInfo("Asia/Tehran")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})")


def parse_requested_date(value):
    normalized = str(value or "")
    if not DATE_PATTERN.fullmatch(normalized):
        raise ValueError("Date must use YYYY-MM-DD format")

    parsed = calendar_date.fromisoformat(normalized)
    if parsed.isoformat() != normalized:
        raise ValueError("Date must use YYYY-MM-DD format")
    return parsed


def parse_aware_kickoff(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.endswith(("Z", "z")):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def match_tehran_date(match):
    if not isinstance(match, dict):
        return None

    date_key = match.get("date_key")
    if isinstance(date_key, str) and DATE_PATTERN.fullmatch(date_key.strip()):
        normalized = date_key.strip()
        try:
            if calendar_date.fromisoformat(normalized).isoformat() == normalized:
                return normalized
        except ValueError:
            pass

    kickoff = parse_aware_kickoff(match.get("kickoff_utc"))
    if kickoff is None:
        return None
    return kickoff.astimezone(TEHRAN_TZ).date().isoformat()


def match_time_sort_value(match):
    kickoff = parse_aware_kickoff(match.get("kickoff_utc"))
    if kickoff is not None:
        local_kickoff = kickoff.astimezone(TEHRAN_TZ)
        return local_kickoff.hour * 3600 + local_kickoff.minute * 60 + local_kickoff.second

    time_value = str(match.get("time_iran") or "").strip()
    time_match = TIME_PATTERN.match(time_value)
    if time_match:
        hour, minute = (int(part) for part in time_match.groups())
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour * 3600 + minute * 60
    return None


def sort_matches(matches):
    indexed_matches = list(enumerate(matches))

    def sort_key(item):
        index, match = item
        time_value = match_time_sort_value(match)
        if time_value is None:
            return 1, 0, index
        return 0, time_value, index

    return [match for _, match in sorted(indexed_matches, key=sort_key)]


def competition_identity(competition, season):
    return {
        "key": competition.get("competition_key"),
        "name": competition.get("name_en"),
        "name_fa": competition.get("name_fa"),
        "season_key": season.get("season_key"),
        "type": competition.get("type"),
    }


def aggregate_matches_by_date(requested_date):
    target_date = parse_requested_date(requested_date).isoformat()
    groups = []
    errors = []

    for competition in get_competitions():
        if competition.get("is_active") is not True or competition.get("supports_matches") is not True:
            continue

        competition_key = competition.get("competition_key")
        season = get_default_season(competition_key)
        season_key = season.get("season_key") if season else None

        if not season:
            errors.append({
                "competition_key": competition_key,
                "season_key": None,
                "code": "default_season_unavailable",
                "message": "Default season is not configured.",
            })
            continue

        try:
            matches = get_matches_for_season(competition_key, season_key, status="all")
        except Exception:
            errors.append({
                "competition_key": competition_key,
                "season_key": season_key,
                "code": "provider_failure",
                "message": "Matches could not be loaded for this competition.",
            })
            continue

        if matches is None:
            errors.append({
                "competition_key": competition_key,
                "season_key": season_key,
                "code": "match_source_unavailable",
                "message": "Match data source is not configured.",
            })
            continue

        if not isinstance(matches, list):
            errors.append({
                "competition_key": competition_key,
                "season_key": season_key,
                "code": "invalid_match_payload",
                "message": "Match data source returned an invalid response.",
            })
            continue

        matching = [
            match
            for match in matches
            if isinstance(match, dict) and match_tehran_date(match) == target_date
        ]
        if matching:
            groups.append({
                "competition": competition_identity(competition, season),
                "matches": sort_matches(matching),
            })

    return {
        "date": target_date,
        "groups": groups,
        "errors": errors,
    }
