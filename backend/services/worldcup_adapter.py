import os
import threading
import time
from urllib.parse import urljoin

import requests

REFRESH_INTERVAL_SECONDS = 10
DEFAULT_TIMEOUT_SECONDS = 10

_cache_lock = threading.Lock()
_cache = {
    "matches": [],
    "events": {},
    "last_refresh": None,
}
_poller_started = False


def warn(message):
    print(f"[WORLDCUP_WRAPPER] {message}")


def get_wrapper_base_url():
    return os.getenv("WORLDCUP_WRAPPER_URL", "").strip()


def get_timeout_seconds():
    try:
        return float(os.getenv("WORLDCUP_WRAPPER_TIMEOUT", DEFAULT_TIMEOUT_SECONDS))
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
        warn("WORLDCUP_WRAPPER_URL is not configured; using empty match data.")
        return None

    try:
        response = requests.get(url, timeout=get_timeout_seconds())
        response.raise_for_status()
        return response.json()
    except Exception as error:
        warn(f"Request failed for {url}: {error}")
        return None


def payload_list(payload, keys):
    if payload is None:
        return []

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)

            if isinstance(value, list):
                return value

            if isinstance(value, dict):
                nested = payload_list(value, keys)

                if nested:
                    return nested

    return []


def coerce_int(value):
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_value(data, keys):
    for key in keys:
        value = data.get(key)

        if value is not None and value != "":
            return value

    return None


def normalize_status(status):
    normalized = str(status or "").strip().lower().replace("-", "_").replace(" ", "_")

    if normalized in {"live", "in_progress", "ongoing", "1h", "2h", "ht", "et"}:
        return "live"

    if normalized in {"finished", "finish", "ft", "ended", "complete", "completed"}:
        return "finished"

    return "upcoming"


def country_code_from_flag_url(flag_url):
    marker = "flagcdn.com/w80/"
    if not isinstance(flag_url, str) or marker not in flag_url:
        return ""

    code = flag_url.split(marker, 1)[1].split(".", 1)[0].strip().upper()
    return code if len(code) == 2 and code.isalpha() else ""


def country_code_to_emoji(code):
    if not code:
        return "\u26bd"

    return "".join(chr(127397 + ord(char)) for char in code.upper())


def flag_emoji(flag_url):
    return country_code_to_emoji(country_code_from_flag_url(flag_url))


def normalize_event_type(event):
    normalized = str(
        event.get("normalized_type") or event.get("type") or event.get("event_type") or ""
    ).strip().lower().replace("-", "_").replace(" ", "_")

    allowed = {
        "goal",
        "yellow_card",
        "red_card",
        "substitution",
        "var",
        "penalty",
        "own_goal",
        "second_yellow_card",
        "missed_penalty",
        "injury",
        "half_time",
        "full_time",
        "unknown",
    }

    return normalized if normalized in allowed else "unknown"


def normalize_event(event):
    if not isinstance(event, dict):
        return None

    side = event.get("team_side")
    if side not in {"home", "away"}:
        side = str(event.get("team") or "").strip().lower()

    if side not in {"home", "away"}:
        side = ""

    return {
        "id": event.get("id"),
        "minute": coerce_int(event.get("minute")) or 0,
        "raw_minute": event.get("raw_minute"),
        "type": normalize_event_type(event),
        "normalized_type": normalize_event_type(event),
        "team": side,
        "team_side": side,
        "team_name": event.get("team_name"),
        "player": str(event.get("player") or "").strip(),
        "assist": event.get("assist"),
        "description": event.get("description"),
        "video_url": event.get("video_url"),
        "created_at": event.get("created_at"),
    }


def normalize_events(events):
    normalized_events = []

    for event in events if isinstance(events, list) else []:
        normalized_event = normalize_event(event)

        if normalized_event is not None:
            normalized_events.append(normalized_event)

    return normalized_events


def normalize_match(match):
    if not isinstance(match, dict):
        return None

    match_id = first_value(match, ("id", "internal_match_id", "match_id", "matchId"))
    normalized_match_id = coerce_int(match_id)
    status = normalize_status(match.get("status"))
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = first_value(match, ("home_score", "homeScore"))
    away_score = first_value(match, ("away_score", "awayScore"))

    if home_score is None:
        home_score = score.get("home")

    if away_score is None:
        away_score = score.get("away")

    home_flag = match.get("home_flag") or ""
    away_flag = match.get("away_flag") or ""

    return {
        **match,
        "id": normalized_match_id if normalized_match_id is not None else match_id,
        "internal_match_id": match.get("internal_match_id") or match_id,
        "external_match_id": match.get("external_match_id"),
        "provider": match.get("provider") or "worldcup2026",
        "home_en": match.get("home_en") or match.get("home_team") or "",
        "away_en": match.get("away_en") or match.get("away_team") or "",
        "home_fa": match.get("home_fa") or "",
        "away_fa": match.get("away_fa") or "",
        "home_flag_url": home_flag,
        "away_flag_url": away_flag,
        "home_flag": flag_emoji(home_flag),
        "away_flag": flag_emoji(away_flag),
        "home_team": match.get("home_en") or match.get("home_team") or "",
        "away_team": match.get("away_en") or match.get("away_team") or "",
        "home_score": coerce_int(home_score),
        "away_score": coerce_int(away_score),
        "score": {
            "home": coerce_int(home_score),
            "away": coerce_int(away_score),
        },
        "status": status,
        "live_badge": status == "live",
        "raw_live_badge": match.get("live_badge"),
        "events": normalize_events(match.get("events") or []),
        "score_source": "worldcup_wrapper",
        "kickoff": match.get("kickoff") or match.get("kickoff_utc") or "",
        "kickoff_utc": match.get("kickoff_utc") or match.get("kickoff") or "",
        "date": match.get("date") or "",
        "date_iran": match.get("date_iran") or "",
        "time_iran": match.get("time_iran") or "",
        "datetime_iran": match.get("datetime_iran") or "",
        "group": match.get("group") or "",
        "stage": match.get("stage") or "",
        "stage_label": match.get("stage_label") or match.get("stage") or "",
        "stadium": match.get("stadium") or "",
        "city": match.get("city") or "",
        "result": match.get("result"),
        "last_updated": match.get("last_updated"),
    }


def normalize_team(team):
    if not isinstance(team, dict):
        return None

    team_id = first_value(team, ("id", "team_id", "external_team_id"))
    normalized_team_id = coerce_int(team_id)
    flag = team.get("flag") or ""

    return {
        **team,
        "id": normalized_team_id if normalized_team_id is not None else team_id,
        "external_team_id": team.get("external_team_id"),
        "provider": team.get("provider") or "worldcup2026",
        "name_en": team.get("name_en") or team.get("team") or "",
        "name_fa": team.get("name_fa") or team.get("name_en") or "",
        "short_name": team.get("short_name") or team.get("name_en") or "",
        "flag_url": flag,
        "flag": flag_emoji(flag),
        "emoji": flag_emoji(flag),
        "logo": team.get("logo"),
        "group": team.get("group") or "",
    }


def fetch_matches_from_wrapper():
    payload = fetch_json("/matches")
    matches = []

    for match in payload_list(payload, ("matches", "data", "results", "items")):
        normalized_match = normalize_match(match)

        if normalized_match is not None:
            matches.append(normalized_match)

    return matches


def fetch_teams_from_wrapper():
    payload = fetch_json("/teams")
    teams = []

    for team in payload_list(payload, ("teams", "data", "results", "items")):
        normalized_team = normalize_team(team)

        if normalized_team is not None:
            teams.append(normalized_team)

    return teams


def fetch_match_live_from_wrapper(match_id):
    payload = fetch_json(f"/match/{match_id}/live")

    if isinstance(payload, dict) and isinstance(payload.get("match"), dict):
        return normalize_match(payload["match"])

    return None


def merge_match_metadata_with_live(metadata, live):
    if metadata is None and live is None:
        return None

    if metadata is None:
        return live

    if live is None:
        return metadata

    merged = dict(metadata)
    live_values = dict(live)

    for key, value in live_values.items():
        if value is not None and value != "":
            merged[key] = value

    for key in (
        "id",
        "internal_match_id",
        "external_match_id",
        "provider",
        "home_en",
        "away_en",
        "home_fa",
        "away_fa",
        "home_team",
        "away_team",
        "home_flag",
        "away_flag",
        "home_flag_url",
        "away_flag_url",
        "kickoff",
        "kickoff_utc",
        "date",
        "date_iran",
        "time_iran",
        "datetime_iran",
        "group",
        "stage",
        "stage_label",
        "stadium",
        "city",
        "result",
    ):
        metadata_value = metadata.get(key)
        if metadata_value is not None and metadata_value != "":
            merged[key] = metadata_value

    for key in (
        "status",
        "status_title",
        "is_live",
        "live_badge",
        "raw_live_badge",
        "minute",
        "raw_minute",
        "home_score",
        "away_score",
        "score",
        "last_updated",
    ):
        live_value = live_values.get(key)
        if live_value is not None and live_value != "":
            merged[key] = live_value

    return merged


def fetch_events_from_wrapper(match_id):
    payload = fetch_json(f"/match/{match_id}/events")
    return normalize_events(payload_list(payload, ("events", "timeline", "data", "items")))


def refresh_cache():
    matches = fetch_matches_from_wrapper()
    events = {
        match["id"]: match.get("events") or []
        for match in matches
        if match.get("id") is not None
    }

    with _cache_lock:
        _cache["matches"] = matches
        _cache["events"] = events
        _cache["last_refresh"] = time.time()


def poll_worldcup_wrapper():
    while True:
        refresh_cache()
        time.sleep(REFRESH_INTERVAL_SECONDS)


def start_worldcup_wrapper_poller():
    global _poller_started

    if _poller_started:
        return

    _poller_started = True
    thread = threading.Thread(
        target=poll_worldcup_wrapper,
        name="worldcup-wrapper-poller",
        daemon=True,
    )
    thread.start()


def ensure_cache_started():
    start_worldcup_wrapper_poller()

    with _cache_lock:
        has_refreshed = _cache["last_refresh"] is not None

    if not has_refreshed:
        refresh_cache()


def get_matches_from_worldcup_wrapper():
    ensure_cache_started()

    with _cache_lock:
        return [dict(match) for match in _cache["matches"]]


def get_live_matches_from_worldcup_wrapper():
    return [
        match
        for match in get_matches_from_worldcup_wrapper()
        if match.get("status") == "live"
    ]


def get_match_live_from_worldcup_wrapper(match_id):
    try:
        normalized_match_id = int(match_id)
    except (TypeError, ValueError):
        normalized_match_id = match_id

    metadata_match = None
    for match in get_matches_from_worldcup_wrapper():
        if match.get("id") == normalized_match_id:
            metadata_match = match
            break

    live_match = fetch_match_live_from_wrapper(normalized_match_id)
    merged_match = merge_match_metadata_with_live(metadata_match, live_match)

    if merged_match is not None:
        return merged_match

    return {
        "id": normalized_match_id,
        "internal_match_id": normalized_match_id,
        "status": "upcoming",
        "status_title": "Upcoming",
        "is_live": False,
        "live_badge": False,
        "events": [],
        "wrapper_available": False,
    }


def get_match_events_from_worldcup_wrapper(match_id):
    try:
        normalized_match_id = int(match_id)
    except (TypeError, ValueError):
        normalized_match_id = match_id

    events = fetch_events_from_wrapper(normalized_match_id)

    with _cache_lock:
        _cache["events"][normalized_match_id] = events

    return {
        "match_id": normalized_match_id,
        "events": events,
    }


def get_teams_from_worldcup_wrapper():
    return fetch_teams_from_wrapper()


# Backward-compatible names used by existing MatchPulse backend imports.
start_varzesh3_poller = start_worldcup_wrapper_poller
get_matches_from_varzesh3 = get_matches_from_worldcup_wrapper
get_live_matches_from_varzesh3 = get_live_matches_from_worldcup_wrapper
get_match_live_from_varzesh3 = get_match_live_from_worldcup_wrapper
get_match_events_from_varzesh3 = get_match_events_from_worldcup_wrapper
