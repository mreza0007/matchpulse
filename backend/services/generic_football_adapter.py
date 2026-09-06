import math
import os
import re
from urllib.parse import quote, urljoin

import requests


DEFAULT_WRAPPER_URL = "http://127.0.0.1:3060"
DEFAULT_TIMEOUT_SECONDS = 10


class GenericFootballProviderError(RuntimeError):
    pass


class GenericStandingsUnavailableError(GenericFootballProviderError):
    pass


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


def fetch_json(path, *, required=False):
    url = build_url(path)
    if not url:
        if required:
            raise GenericFootballProviderError("Football provider unavailable")
        return None

    try:
        response = requests.get(url, timeout=get_timeout_seconds())
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as error:
        if required:
            raise GenericFootballProviderError("Football provider unavailable") from error
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


def normalize_finished_result(status, home_score, away_score, competition_format=None):
    if status != "finished" or competition_format != "league":
        return None
    if isinstance(home_score, bool) or isinstance(away_score, bool):
        return None
    if not isinstance(home_score, (int, float)) or not isinstance(away_score, (int, float)):
        return None
    try:
        scores_are_finite = math.isfinite(home_score) and math.isfinite(away_score)
    except (OverflowError, TypeError, ValueError):
        return None
    if not scores_are_finite or home_score < 0 or away_score < 0:
        return None
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def normalize_match(match, competition_format=None):
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
    result = normalize_finished_result(
        status, home_score, away_score, competition_format=competition_format
    )

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
        "result": result,
        "result_source": "final_score" if result is not None else None,
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


def normalize_standing(standing):
    if not isinstance(standing, dict):
        raise GenericFootballProviderError("Invalid standings row")

    confirmed_fields = (
        "rank",
        "team_id",
        "provider",
        "external_team_id",
        "team_fa",
        "team_en",
        "logo",
        "played",
        "wins",
        "draws",
        "losses",
        "points",
        "goals_for",
        "goals_against",
        "goal_difference",
        "qualification_color",
        "has_live_match",
    )
    return {field: standing.get(field) for field in confirmed_fields}


def status_matches_filter(requested_status, match_status):
    requested = str(requested_status or "all").strip().lower()
    if requested == "past":
        requested = "finished"
    elif requested == "scheduled":
        requested = "upcoming"
    return requested == "all" or requested == match_status


def get_season_matches(competition_key, season_key, status="all", competition_format=None):
    competition = quote(str(competition_key), safe="")
    season = quote(str(season_key), safe="")
    payload = fetch_json(
        f"/competitions/{competition}/seasons/{season}/matches", required=True
    )
    raw_matches = payload.get("matches") if isinstance(payload, dict) else payload
    if not isinstance(raw_matches, list):
        raise GenericFootballProviderError("Invalid matches payload")

    matches = []
    for match in raw_matches:
        normalized = normalize_match(match, competition_format=competition_format)
        if normalized is not None and status_matches_filter(status, normalized["status"]):
            matches.append(normalized)
    return matches


def get_season_overview(competition_key, season_key, competition_format=None):
    competition_value = str(competition_key)
    season_value = str(season_key)
    competition = quote(competition_value, safe="")
    season = quote(season_value, safe="")
    payload = fetch_json(
        f"/competitions/{competition}/seasons/{season}/overview", required=True
    )
    if not isinstance(payload, dict):
        raise GenericFootballProviderError("Invalid overview payload")
    if (
        str(payload.get("competition_key") or "") != competition_value
        or str(payload.get("season_key") or "") != season_value
    ):
        raise GenericFootballProviderError("Invalid overview scope")

    raw_matches = payload.get("matches")
    if not isinstance(raw_matches, list):
        raise GenericFootballProviderError("Invalid overview payload")

    matches = []
    for match in raw_matches:
        if not isinstance(match, dict):
            raise GenericFootballProviderError("Invalid overview payload")
        normalized = normalize_match(match, competition_format=competition_format)
        if normalized is not None:
            match_id = normalized.get("id")
            if not isinstance(match_id, str) or not match_id.startswith("mp_match_"):
                raise GenericFootballProviderError("Invalid overview payload")
            if (
                str(normalized.get("competition_key") or "") != competition_value
                or str(normalized.get("season_key") or "") != season_value
            ):
                raise GenericFootballProviderError("Invalid overview scope")
            normalized.pop("provider", None)
            normalized.pop("external_match_id", None)
            matches.append(normalized)
    return matches


def get_season_teams(competition_key, season_key):
    competition = quote(str(competition_key), safe="")
    season = quote(str(season_key), safe="")
    payload = fetch_json(
        f"/competitions/{competition}/seasons/{season}/teams", required=True
    )
    raw_teams = payload.get("teams") if isinstance(payload, dict) else payload
    if not isinstance(raw_teams, list):
        raise GenericFootballProviderError("Invalid teams payload")

    teams = []
    for team in raw_teams:
        normalized = normalize_team(team)
        if normalized is None or normalized.get("id") is None:
            raise GenericFootballProviderError("Invalid teams payload")
        teams.append(normalized)
    return teams


def get_season_standings(competition_key, season_key):
    competition = quote(str(competition_key), safe="")
    season = quote(str(season_key), safe="")
    url = build_url(f"/competitions/{competition}/seasons/{season}/standings")
    if not url:
        raise GenericFootballProviderError("Wrapper URL is not configured")

    try:
        response = requests.get(url, timeout=get_timeout_seconds())
        if response.status_code == 501:
            raise GenericStandingsUnavailableError("Standings not available")
        response.raise_for_status()
        payload = response.json()
    except GenericStandingsUnavailableError:
        raise
    except (requests.RequestException, ValueError) as error:
        raise GenericFootballProviderError("Standings provider unavailable") from error

    raw_standings = payload.get("standings") if isinstance(payload, dict) else None
    if not isinstance(raw_standings, list):
        raise GenericFootballProviderError("Invalid standings payload")

    return [normalize_standing(standing) for standing in raw_standings]


def get_match_live(match_id):
    stable_match_id = quote(str(match_id), safe="")
    payload = fetch_json(f"/matches/{stable_match_id}/live")
    raw_match = payload.get("match") if isinstance(payload, dict) else None
    normalized = normalize_match(raw_match)
    return {"ok": bool(normalized), "match": normalized}


EVENT_TYPES = frozenset({
    "goal",
    "own_goal",
    "penalty_goal",
    "missed_penalty",
    "yellow_card",
    "second_yellow_red",
    "red_card",
    "substitution",
    "var",
    "disallowed_goal",
    "halftime",
    "fulltime",
    "kickoff",
    "other",
})

EVENT_TYPE_ALIASES = {
    "own-goal": "own_goal",
    "own goal": "own_goal",
    "penalty-goal": "penalty_goal",
    "penalty goal": "penalty_goal",
    "penalty_missed": "missed_penalty",
    "missed-penalty": "missed_penalty",
    "missed penalty": "missed_penalty",
    "yellow": "yellow_card",
    "yellow-card": "yellow_card",
    "yellow card": "yellow_card",
    "second_yellow": "second_yellow_red",
    "second-yellow-red": "second_yellow_red",
    "second yellow red": "second_yellow_red",
    "red": "red_card",
    "red-card": "red_card",
    "red card": "red_card",
    "sub": "substitution",
    "video_assistant_referee": "var",
    "goal_disallowed": "disallowed_goal",
    "goal-disallowed": "disallowed_goal",
    "goal disallowed": "disallowed_goal",
    "disallowed-goal": "disallowed_goal",
    "disallowed goal": "disallowed_goal",
    "half_time": "halftime",
    "half-time": "halftime",
    "half time": "halftime",
    "full_time": "fulltime",
    "full-time": "fulltime",
    "full time": "fulltime",
    "kick_off": "kickoff",
    "kick-off": "kickoff",
    "kick off": "kickoff",
}

GOAL_EVENT_TYPES = frozenset({"goal", "own_goal", "penalty_goal"})


def _event_text(value):
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _event_int(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _first_event_text(event, *fields):
    for field in fields:
        value = _event_text(event.get(field))
        if value is not None:
            return value
    return None


def _event_minute_parts(event):
    minute = _event_int(event.get("minute"))
    added_time = _event_int(event.get("added_time"))
    raw_display_minute = _first_event_text(event, "display_minute")

    minute_source = raw_display_minute or _first_event_text(event, "minute")
    if minute_source:
        match = re.fullmatch(r"\s*(\d+)\s*(?:\+\s*(\d+))?\s*'?\s*", minute_source)
        if match:
            if minute is None:
                minute = int(match.group(1))
            if added_time is None:
                added_time = int(match.group(2) or 0)

    if minute is not None and added_time is None:
        added_time = 0
    display_minute = None
    if minute is not None:
        display_minute = f"{minute}+{added_time}" if added_time else str(minute)

    return minute, added_time, display_minute


def _normalize_event_type(event):
    raw_type = _first_event_text(event, "type", "normalized_type", "event_type")
    normalized = str(raw_type or "").strip().lower()
    normalized = EVENT_TYPE_ALIASES.get(normalized, normalized)
    if normalized == "var":
        evidence = " ".join(
            value.lower()
            for value in (
                _first_event_text(event, "raw_type_label"),
                _first_event_text(event, "description"),
            )
            if value
        )
        if "goal disallowed" in evidence or "disallowed goal" in evidence:
            return "disallowed_goal"
    return normalized if normalized in EVENT_TYPES else "other"


def _canonical_public_id(value, prefix):
    normalized = _event_text(value)
    if normalized and normalized.startswith(prefix):
        return normalized
    return None


def normalize_match_event(event, original_index=0):
    if not isinstance(event, dict):
        return None

    event_type = _normalize_event_type(event)
    minute, added_time, display_minute = _event_minute_parts(event)
    secondary_player_name = _first_event_text(
        event, "secondary_player_name", "secondary_player_name_fa"
    )
    assist_name = _first_event_text(event, "assist_name", "assist_name_fa")
    if assist_name is None and event_type in GOAL_EVENT_TYPES:
        assist_name = secondary_player_name

    team_side = _first_event_text(event, "team_side")
    if team_side not in {"home", "away"}:
        team_side = None

    normalized = {
        "id": _canonical_public_id(event.get("id"), "mp_event_"),
        "type": event_type,
        "minute": minute,
        "added_time": added_time,
        "display_minute": display_minute,
        "team_side": team_side,
        "team_id": _canonical_public_id(event.get("team_id"), "mp_team_"),
        "player_name": _first_event_text(event, "player_name", "player_name_fa"),
        "secondary_player_name": secondary_player_name,
        "assist_name": assist_name,
        "player_in_name": _first_event_text(event, "player_in_name", "player_in_name_fa"),
        "player_out_name": _first_event_text(event, "player_out_name", "player_out_name_fa"),
        "home_score": _event_int(event.get("home_score")),
        "away_score": _event_int(event.get("away_score")),
        "description": _first_event_text(event, "description"),
        "raw_type_label": _first_event_text(event, "raw_type_label"),
    }
    return normalized, original_index


def _event_sort_key(item):
    event, original_index = item
    minute = event.get("minute")
    added_time = event.get("added_time")
    return (
        minute is None,
        minute if minute is not None else 0,
        added_time if added_time is not None else 0,
        original_index,
    )


def _normalized_scope_value(value):
    return str(value or "").strip().lower()


def get_match_events(match_id, *, competition_key=None, season_key=None):
    stable_match_id = quote(str(match_id), safe="")
    payload = fetch_json(f"/matches/{stable_match_id}/events", required=True)
    if not isinstance(payload, dict):
        raise GenericFootballProviderError("Invalid events payload")

    requested_match_id = str(match_id)
    if payload.get("ok") is False or str(payload.get("match_id") or "") != requested_match_id:
        raise GenericFootballProviderError("Invalid events payload")

    for field, requested_value in (
        ("competition_key", competition_key),
        ("season_key", season_key),
    ):
        returned_value = payload.get(field)
        if returned_value is not None and requested_value is not None and (
            _normalized_scope_value(returned_value) != _normalized_scope_value(requested_value)
        ):
            raise GenericFootballProviderError("Invalid events payload")

    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raise GenericFootballProviderError("Invalid events payload")
    normalized_events = []
    for index, event in enumerate(raw_events):
        normalized = normalize_match_event(event, original_index=index)
        if normalized is not None:
            normalized_events.append(normalized)
    normalized_events.sort(key=_event_sort_key)
    events = [event for event, _ in normalized_events]

    stale = payload.get("stale") is True
    warnings = ["stale_events"] if stale else []

    return {
        "competition_key": str(competition_key or payload.get("competition_key") or ""),
        "season_key": str(season_key or payload.get("season_key") or ""),
        "match_id": requested_match_id,
        "count": len(events),
        "stale": stale,
        "warnings": warnings,
        "events": events,
    }
