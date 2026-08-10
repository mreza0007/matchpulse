import os
import re
from urllib.parse import quote, urljoin

import requests


DEFAULT_WRAPPER_URL = "http://127.0.0.1:3060"
DEFAULT_TIMEOUT_SECONDS = 10


def get_wrapper_base_url():
    return os.getenv("GENERIC_FOOTBALL_WRAPPER_URL", DEFAULT_WRAPPER_URL).strip()


def get_timeout_seconds():
    try:
        return float(os.getenv("GENERIC_FOOTBALL_WRAPPER_TIMEOUT", DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS


def build_url(path):
    base_url = get_wrapper_base_url()
    if not base_url:
        return ""
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def fetch_json(path):
    url = build_url(path)
    if not url:
        return None

    try:
        response = requests.get(url, timeout=get_timeout_seconds())
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def payload_items(payload, key):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return payload[key]
    return []


def normalize_warnings(value):
    if isinstance(value, list):
        return list(value)
    if value in (None, ""):
        return []
    return [value]


def normalize_status(value):
    normalized = re.sub(r"[-\s]+", "_", str(value or "").strip().lower())
    aliases = {
        "in_progress": "live",
        "ongoing": "live",
        "completed": "finished",
        "full_time": "finished",
        "scheduled": "upcoming",
    }
    return aliases.get(normalized, normalized or "unknown")


def normalize_match(match):
    if not isinstance(match, dict):
        return None

    status = normalize_status(match.get("status"))
    home_name_fa = match.get("home_name_fa")
    away_name_fa = match.get("away_name_fa")
    home_name_en = match.get("home_name_en")
    away_name_en = match.get("away_name_en")
    home_display_name = home_name_en or home_name_fa or ""
    away_display_name = away_name_en or away_name_fa or ""
    date_fa = match.get("date_fa")
    round_value = match.get("round")
    home_score = match.get("home_score")
    away_score = match.get("away_score")

    return {
        "id": match.get("id"),
        "competition_key": match.get("competition_key"),
        "season_key": match.get("season_key"),
        "provider": match.get("provider"),
        "external_match_id": match.get("external_match_id"),
        "home_team_id": match.get("home_team_id"),
        "away_team_id": match.get("away_team_id"),
        "home_fa": home_name_fa or home_display_name,
        "away_fa": away_name_fa or away_display_name,
        "home_en": home_display_name,
        "away_en": away_display_name,
        "home_team_name_fa": home_name_fa,
        "away_team_name_fa": away_name_fa,
        "home_team_name_en": home_name_en,
        "away_team_name_en": away_name_en,
        "home_logo": match.get("home_logo"),
        "away_logo": match.get("away_logo"),
        "kickoff_utc": match.get("kickoff_utc"),
        "date": date_fa or "",
        "date_iran": date_fa or "",
        "date_fa": date_fa,
        "time_iran": match.get("time_iran") or "",
        "stage": round_value or "",
        "round": round_value,
        "status": status,
        "is_live": status == "live",
        "is_finished": status == "finished",
        "is_upcoming": status == "upcoming",
        "live_phase": match.get("live_phase"),
        "home_score": home_score,
        "away_score": away_score,
        "score": {"home": home_score, "away": away_score},
        "home_penalty_score": match.get("home_penalties"),
        "away_penalty_score": match.get("away_penalties"),
        "warnings": normalize_warnings(match.get("warnings")),
    }


def normalize_team(team):
    if not isinstance(team, dict):
        return None

    return {
        "id": team.get("id"),
        "competition_key": team.get("competition_key"),
        "season_key": team.get("season_key"),
        "provider": team.get("provider"),
        "external_team_id": team.get("external_team_id"),
        "name_fa": team.get("name_fa"),
        "name_en": team.get("name_en"),
        "logo": team.get("logo"),
        "flag": team.get("flag") or "",
        "emoji": team.get("emoji") or "",
        "warnings": normalize_warnings(team.get("warnings")),
    }


def status_matches_filter(requested_status, match_status):
    requested = str(requested_status or "all").strip().lower()
    if requested == "past":
        requested = "finished"
    elif requested == "scheduled":
        requested = "upcoming"
    return requested == "all" or requested == match_status


def get_season_matches(competition_key, season_key, status="all"):
    competition = quote(str(competition_key), safe="")
    season = quote(str(season_key), safe="")
    payload = fetch_json(f"/competitions/{competition}/seasons/{season}/matches")
    matches = []
    for match in payload_items(payload, "matches"):
        normalized = normalize_match(match)
        if normalized is not None and status_matches_filter(status, normalized["status"]):
            matches.append(normalized)
    return matches


def get_season_teams(competition_key, season_key):
    competition = quote(str(competition_key), safe="")
    season = quote(str(season_key), safe="")
    payload = fetch_json(f"/competitions/{competition}/seasons/{season}/teams")
    teams = []
    for team in payload_items(payload, "teams"):
        normalized = normalize_team(team)
        if normalized is not None:
            teams.append(normalized)
    return teams


def get_match_live(match_id):
    stable_match_id = quote(str(match_id), safe="")
    payload = fetch_json(f"/matches/{stable_match_id}/live")
    raw_match = payload.get("match") if isinstance(payload, dict) else None
    normalized = normalize_match(raw_match)
    return {"ok": bool(normalized), "match": normalized}


def get_match_events(match_id):
    stable_match_id = quote(str(match_id), safe="")
    payload = fetch_json(f"/matches/{stable_match_id}/events")
    if not isinstance(payload, dict):
        return {"ok": False, "match_id": str(match_id), "events": []}

    events = list(payload.get("events")) if isinstance(payload.get("events"), list) else []
    count = payload.get("count")
    if count is None:
        count = len(events)

    return {
        "ok": payload.get("ok", True),
        "match_id": payload.get("match_id", str(match_id)),
        "competition_key": payload.get("competition_key"),
        "season_key": payload.get("season_key"),
        "provider": payload.get("provider"),
        "external_match_id": payload.get("external_match_id"),
        "count": count,
        "stale": payload.get("stale"),
        "events": events,
        "warnings": normalize_warnings(payload.get("warnings")),
    }
