import os
import threading
import time
from urllib.parse import urljoin

import requests

REFRESH_INTERVAL_SECONDS = 10
EVENT_TYPES = {"goal", "assist", "yellow_card", "red_card", "substitution"}

_cache_lock = threading.Lock()
_cache = {
    "matches": [],
    "events": {},
    "last_refresh": None,
}
_poller_started = False


def warn(message):
    print(f"[VARZESH3_ADAPTER] {message}")


def get_varzesh3_base_url():
    return os.getenv("VARZESH3_API_URL", "").strip()


def build_url(path):
    base_url = get_varzesh3_base_url()

    if not base_url:
        return ""

    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def fetch_json(path):
    url = build_url(path)

    if not url:
        warn("VARZESH3_API_URL is not configured; using empty match data.")
        return None

    try:
        response = requests.get(url, timeout=15)
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


def nested_score(match, side):
    score = match.get("score") or {}

    for key in ("current", "fullTime", "regularTime", "halfTime"):
        value = (score.get(key) or {}).get(side)

        if value is not None:
            return value

    return None


def team_name(match, side):
    value = first_value(
        match,
        (
            f"{side}_en",
            f"{side}En",
            f"{side}_team",
            f"{side}Team",
            f"{side}_name",
            f"{side}Name",
        ),
    )

    if isinstance(value, dict):
        return (
            value.get("name_en")
            or value.get("english_name")
            or value.get("name")
            or value.get("shortName")
            or value.get("title")
            or ""
        )

    return value or ""


def normalize_event_type(event_type):
    normalized = str(event_type or "").strip().lower().replace("-", "_").replace(" ", "_")

    if normalized in EVENT_TYPES:
        return normalized

    if normalized in {"yellow", "yellowcard"}:
        return "yellow_card"

    if normalized in {"red", "redcard"}:
        return "red_card"

    if normalized in {"sub", "substitute"}:
        return "substitution"

    return None


def normalize_event(event):
    if not isinstance(event, dict):
        return None

    event_type = normalize_event_type(event.get("type") or event.get("event_type"))

    if event_type is None:
        return None

    team = str(event.get("team") or event.get("side") or "").strip().lower()

    if team not in {"home", "away"}:
        team = "home" if team in {"1", "home_team"} else "away" if team in {"2", "away_team"} else ""

    if team not in {"home", "away"}:
        return None

    return {
        "minute": coerce_int(event.get("minute") or event.get("time")) or 0,
        "type": event_type,
        "team": team,
        "player": str(event.get("player") or event.get("player_name") or "").strip(),
        "assist": event.get("assist") or event.get("assist_player"),
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

    home_score = first_value(match, ("home_score", "homeScore", "home_goals", "homeGoals"))
    away_score = first_value(match, ("away_score", "awayScore", "away_goals", "awayGoals"))

    if home_score is None:
        home_score = nested_score(match, "home")

    if away_score is None:
        away_score = nested_score(match, "away")

    status = normalize_status(match.get("status"))
    home = team_name(match, "home")
    away = team_name(match, "away")
    match_id = first_value(match, ("id", "match_id", "matchId", "matchNumber"))
    normalized_match_id = coerce_int(match_id)

    return {
        "id": normalized_match_id if normalized_match_id is not None else match_id,
        "home_en": home,
        "away_en": away,
        "home_flag": match.get("home_flag") or "⚽",
        "away_flag": match.get("away_flag") or "⚽",
        "home_team": home,
        "away_team": away,
        "home_score": coerce_int(home_score),
        "away_score": coerce_int(away_score),
        "status": status,
        "live_badge": status == "live",
        "events": normalize_events(match.get("events") or []),
        "score_source": "varzesh3",
        "date": match.get("date") or "",
        "kickoff": match.get("kickoff") or match.get("kickoffUtc") or "",
        "date_iran": match.get("date_iran") or "",
        "time_iran": match.get("time_iran") or "",
        "datetime_iran": match.get("datetime_iran") or "",
        "group": match.get("group") or "",
        "stage": match.get("stage") or "",
        "stage_label": match.get("stage_label") or match.get("stage") or "",
        "stadium": match.get("stadium") or "",
        "city": match.get("city") or match.get("hostCity") or "",
        "result": match.get("result"),
    }


def fetch_matches_from_varzesh3():
    payload = fetch_json("/matches")
    matches = []

    for match in payload_list(payload, ("matches", "data", "results", "items")):
        normalized_match = normalize_match(match)

        if normalized_match is not None:
            matches.append(normalized_match)

    return matches


def fetch_events_from_varzesh3(match_id):
    payload = fetch_json(f"/match/{match_id}/events")
    return normalize_events(payload_list(payload, ("events", "timeline", "data", "items")))


def refresh_cache():
    matches = fetch_matches_from_varzesh3()
    events = {
        match["id"]: match.get("events") or []
        for match in matches
        if match.get("id") is not None
    }

    with _cache_lock:
        _cache["matches"] = matches
        _cache["events"] = events
        _cache["last_refresh"] = time.time()


def poll_varzesh3():
    while True:
        refresh_cache()
        time.sleep(REFRESH_INTERVAL_SECONDS)


def start_varzesh3_poller():
    global _poller_started

    if _poller_started:
        return

    _poller_started = True
    thread = threading.Thread(target=poll_varzesh3, name="varzesh3-poller", daemon=True)
    thread.start()


def ensure_cache_started():
    start_varzesh3_poller()

    with _cache_lock:
        has_refreshed = _cache["last_refresh"] is not None

    if not has_refreshed:
        refresh_cache()


def get_matches_from_varzesh3():
    ensure_cache_started()

    with _cache_lock:
        return [dict(match) for match in _cache["matches"]]


def get_live_matches_from_varzesh3():
    return [
        match
        for match in get_matches_from_varzesh3()
        if match.get("status") == "live"
    ]


def get_match_live_from_varzesh3(match_id):
    try:
        normalized_match_id = int(match_id)
    except (TypeError, ValueError):
        normalized_match_id = match_id

    for match in get_matches_from_varzesh3():
        if match.get("id") == normalized_match_id:
            return match

    return {
        "id": normalized_match_id,
        "status": "upcoming",
        "live_badge": False,
        "events": [],
    }


def get_match_events_from_varzesh3(match_id):
    try:
        normalized_match_id = int(match_id)
    except (TypeError, ValueError):
        normalized_match_id = match_id

    with _cache_lock:
        cached_events = _cache["events"].get(normalized_match_id)

    if cached_events is None:
        cached_events = fetch_events_from_varzesh3(normalized_match_id)

        with _cache_lock:
            _cache["events"][normalized_match_id] = cached_events

    return {
        "match_id": normalized_match_id,
        "events": cached_events,
    }
