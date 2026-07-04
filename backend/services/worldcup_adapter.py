import os
import re
import threading
import time
import json
from datetime import datetime, timedelta, time as datetime_time
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests

REFRESH_INTERVAL_SECONDS = 10
DEFAULT_TIMEOUT_SECONDS = 10
PROVIDER_MATCH_TOLERANCE_SECONDS = 18 * 60 * 60
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VARZESH3_MATCH_MAP_PATH = DATA_DIR / "varzesh3-match-map.json"
VARZESH_EVENT_TYPES = {
    1: "goal",
    2: "yellow_card",
    3: "penalty_event",
    4: "substitution",
    5: "var_disallowed_goal",
    6: "var",
    7: "own_goal",
    8: "red_card",
    9: "penalty_missed",
    10: "injury",
    11: "half_time",
    12: "full_time",
}
TEHRAN_TZ = ZoneInfo("Asia/Tehran")
UTC_TZ = ZoneInfo("UTC")
SOURCE_TZ = ZoneInfo(os.getenv("WORLDCUP_SOURCE_TIMEZONE", "America/New_York"))
STADIUM_TIMEZONES = {
    "1": "America/Mexico_City",
    "2": "America/Mexico_City",
    "3": "America/Monterrey",
    "4": "America/Chicago",
    "5": "America/Chicago",
    "6": "America/Chicago",
    "7": "America/New_York",
    "8": "America/New_York",
    "9": "America/New_York",
    "10": "America/New_York",
    "11": "America/New_York",
    "12": "America/Toronto",
    "13": "America/Vancouver",
    "14": "America/Los_Angeles",
    "15": "America/Los_Angeles",
    "16": "America/Los_Angeles",
}
WEEKDAYS_FA = {
    0: "\u062f\u0648\u0634\u0646\u0628\u0647",
    1: "\u0633\u0647\u200c\u0634\u0646\u0628\u0647",
    2: "\u0686\u0647\u0627\u0631\u0634\u0646\u0628\u0647",
    3: "\u067e\u0646\u062c\u0634\u0646\u0628\u0647",
    4: "\u062c\u0645\u0639\u0647",
    5: "\u0634\u0646\u0628\u0647",
    6: "\u06cc\u06a9\u0634\u0646\u0628\u0647",
}

_cache_lock = threading.Lock()
_cache = {
    "matches": [],
    "events": {},
    "last_refresh": None,
}
_persistent_match_map_cache = None
_poller_started = False


def warn(message):
    text = f"[WORLDCUP_WRAPPER] {message}"
    safe_text = text.encode("ascii", errors="backslashreplace").decode("ascii")
    print(safe_text)


def load_persistent_match_map():
    global _persistent_match_map_cache

    if _persistent_match_map_cache is not None:
        return _persistent_match_map_cache

    try:
        if VARZESH3_MATCH_MAP_PATH.exists():
            with VARZESH3_MATCH_MAP_PATH.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        else:
            payload = {}
    except Exception as error:
        warn(f"[EVENT_RESOLVE_AUDIT] persistent_map_load_failed path={VARZESH3_MATCH_MAP_PATH} error={error}")
        payload = {}

    mappings = payload.get("matches") if isinstance(payload, dict) else payload
    if not isinstance(mappings, dict):
        mappings = {}

    _persistent_match_map_cache = {
        str(match_id): str(external_id)
        for match_id, external_id in mappings.items()
        if external_id is not None and str(external_id).strip()
    }
    return _persistent_match_map_cache


def save_persistent_match_map(mapping):
    global _persistent_match_map_cache

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "description": "Persistent Varzesh3 external match ids keyed by MatchPulse internal match id.",
            "matches": dict(sorted(mapping.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else str(item[0]))),
        }
        with VARZESH3_MATCH_MAP_PATH.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        _persistent_match_map_cache = payload["matches"]
    except Exception as error:
        warn(f"[EVENT_RESOLVE_AUDIT] persistent_map_save_failed path={VARZESH3_MATCH_MAP_PATH} error={error}")


def persist_external_match_id(match_id, external_match_id):
    if match_id is None or external_match_id is None or external_match_id == "":
        return

    mapping = load_persistent_match_map()
    key = str(match_id)
    value = str(external_match_id)

    if mapping.get(key) == value:
        return

    mapping[key] = value
    save_persistent_match_map(mapping)


def get_wrapper_base_url():
    return (
        os.getenv("WORLDCUP_API_URL")
        or os.getenv("WORLDCUP_WRAPPER_URL")
        or "http://127.0.0.1:3050"
    ).strip()


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


def fetch_json_with_error(path):
    url = build_url(path)

    if not url:
        return None, "WORLDCUP_WRAPPER_URL is not configured"

    try:
        response = requests.get(url, timeout=get_timeout_seconds())
        response.raise_for_status()
        return response.json(), None
    except Exception as error:
        warn(f"Request failed for {url}: {error}")
        return None, str(error)


def payload_debug_summary(payload):
    if isinstance(payload, list):
        return {"type": "list", "count": len(payload)}

    if isinstance(payload, dict):
        summary = {"type": "dict", "keys": sorted(payload.keys())}

        for key in ("events", "timeline", "data", "items", "match"):
            value = payload.get(key)
            if isinstance(value, list):
                summary[f"{key}_count"] = len(value)
            elif isinstance(value, dict):
                summary[f"{key}_keys"] = sorted(value.keys())

        return summary

    return {"type": type(payload).__name__}


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


def text_value(value, language="en"):
    if isinstance(value, dict):
        if language == "fa":
            value = first_value(
                value,
                ("name_fa", "fa_name", "persian_name", "title_fa", "name", "title"),
            )
        else:
            value = first_value(
                value,
                ("name_en", "en_name", "english_name", "title_en", "name", "title", "shortName"),
            )

    return repair_text(value) or ""


def first_team_text(match, side, language="en"):
    if language == "fa":
        keys = (
            f"{side}_fa",
            f"{side}_team_name_fa",
            f"{side}_team_label_fa",
            f"{side}TeamFa",
        )
    else:
        keys = (
            f"{side}_en",
            f"{side}_team_label",
            f"{side}_team",
            f"{side}_team_name_en",
            f"{side}Team",
            "host" if side == "home" else "visitingTeam",
        )

    for key in keys:
        value = text_value(match.get(key), language=language)

        if value:
            return value

    return ""


def persian_digits(value):
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def placeholder_fa(value):
    text = text_value(value)

    if not text:
        return ""

    match = re.fullmatch(r"Winner\s+Match\s+(\d+)", text, flags=re.IGNORECASE)
    if match:
        return f"برنده بازی {persian_digits(match.group(1))}"

    match = re.fullmatch(r"Loser\s+Match\s+(\d+)", text, flags=re.IGNORECASE)
    if match:
        return f"بازنده بازی {persian_digits(match.group(1))}"

    match = re.fullmatch(r"Winner\s+Group\s+(.+)", text, flags=re.IGNORECASE)
    if match:
        return f"صدرنشین گروه {match.group(1).upper()}"

    match = re.fullmatch(r"Runner[-\s]?up\s+Group\s+(.+)", text, flags=re.IGNORECASE)
    if match:
        return f"تیم دوم گروه {match.group(1).upper()}"

    match = re.fullmatch(r"3rd\s+Group\s+(.+)", text, flags=re.IGNORECASE)
    if match:
        return f"تیم سوم یکی از گروه‌های {match.group(1).upper()}"

    return ""


STAGE_LABELS = {
    "r16": "R16",
    "r32": "R32",
    "qf": "QF",
    "sf": "SF",
    "third": "Third",
    "3rd": "Third",
    "final": "Final",
}
SCORING_EVENT_TYPES = {"goal", "own_goal", "penalty_goal"}


def resolve_stage(match):
    raw_stage = first_value(match, ("stage", "type"))
    normalized_stage = str(raw_stage or "").strip().lower()

    if normalized_stage not in STAGE_LABELS:
        normalized_group = str(match.get("group") or "").strip().lower()
        if normalized_group in STAGE_LABELS:
            normalized_stage = normalized_group

    if normalized_stage == "3rd":
        normalized_stage = "third"

    stage = normalized_stage or str(raw_stage or "").strip()
    stage_label = STAGE_LABELS.get(normalized_stage) or match.get("stage_label") or stage
    return stage, stage_label


def display_flag(value):
    text = str(value or "").strip()

    if text and any(127462 <= ord(char) <= 127487 for char in text):
        return text

    return flag_emoji(text)


def count_persian_chars(value):
    return len(re.findall(r"[\u0600-\u06ff]", str(value or "")))


def repair_text(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return ""

    candidates = [text]

    for encoding in ("latin1", "cp1252", "cp1256"):
        try:
            candidate = text.encode(encoding).decode("utf-8").strip()
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        if candidate and candidate not in candidates:
            candidates.append(candidate)

    return max(
        candidates,
        key=lambda candidate: (
            -sum(candidate.count(marker) for marker in ("ظ", "ط", "غ")),
            count_persian_chars(candidate),
            -candidate.count("\ufffd"),
        ),
    )


def minute_token_pattern():
    return r"\d{1,3}(?:\s*\+\s*\d{1,2})?"


def format_minute_token(value):
    text = normalize_digits(repair_text(value)).strip()
    match = re.search(minute_token_pattern(), text)

    if not match:
        return ""

    return re.sub(r"\s+", "", match.group(0))


def extract_minute_from_description(description):
    text = normalize_digits(repair_text(description)).strip()

    if not text:
        return ""

    match = re.search(rf"\b\u062f\u0642\u06cc\u0642\u0647\s*({minute_token_pattern()})", text)

    if not match:
        match = re.search(rf"\b({minute_token_pattern()})\b", text)

    return re.sub(r"\s+", "", match.group(1)) if match else ""


def is_minute_token(value):
    text = normalize_digits(repair_text(value)).replace(" ", "")
    return bool(re.fullmatch(r"(?:\+?\d{1,3}\+?|\d{1,3}\+\d{1,2})", text or ""))


def normalize_digits(value):
    if value is None:
        return ""

    translation = str.maketrans(
        "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
        "01234567890123456789",
    )
    return str(value).translate(translation).strip()


def parse_time_value(value):
    normalized = normalize_digits(value)
    match = re.search(r"(\d{1,2}):(\d{2})", normalized)

    if not match:
        return datetime_time(0, 0)

    hour = max(0, min(23, int(match.group(1))))
    minute = max(0, min(59, int(match.group(2))))
    return datetime_time(hour, minute)


def has_time_value(value):
    return bool(re.search(r"\d{1,2}:\d{2}", normalize_digits(value)))


def jalali_to_gregorian(jy, jm, jd):
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd

    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186

    gy = 400 * (days // 146097)
    days %= 146097

    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524

        if days >= 365:
            days += 1

    gy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365

    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    month_days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1

    while gm <= 12 and gd > month_days[gm - 1]:
        gd -= month_days[gm - 1]
        gm += 1

    return gy, gm, gd


def gregorian_to_jalali(gy, gm, gd):
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy -= 1600
    gm -= 1
    gd -= 1

    g_day_no = (365 * gy) + ((gy + 3) // 4) - ((gy + 99) // 100) + ((gy + 399) // 400)

    for index in range(gm):
        g_day_no += g_days_in_month[index]

    if gm > 1 and ((gy + 1600) % 4 == 0 and (gy + 1600) % 100 != 0 or (gy + 1600) % 400 == 0):
        g_day_no += 1

    g_day_no += gd
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + (33 * j_np) + (4 * (j_day_no // 1461))
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    jm = 0
    while jm < 11 and j_day_no >= j_days_in_month[jm]:
        j_day_no -= j_days_in_month[jm]
        jm += 1

    return jy, jm + 1, j_day_no + 1


def parse_numeric_date(value, prefer_jalali=False):
    normalized = normalize_digits(value)
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", normalized)

    if match:
        year, month, day = (int(part) for part in match.groups())

        if prefer_jalali or year < 1700:
            return jalali_to_gregorian(year, month, day)

        return year, month, day

    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", normalized)

    if match:
        month, day, year = (int(part) for part in match.groups())
        return year, month, day

    return None


def parse_iso_datetime(value):
    normalized = normalize_digits(value)

    if not normalized or not re.match(r"^\d{4}-\d{2}-\d{2}", normalized):
        return None

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC_TZ)

    return parsed.astimezone(UTC_TZ)


def parse_timezone_value(value):
    normalized = str(value or "").strip()

    if not normalized:
        return SOURCE_TZ

    aliases = {
        "et": "America/New_York",
        "est": "America/New_York",
        "edt": "America/New_York",
        "eastern": "America/New_York",
        "america/eastern": "America/New_York",
        "tehran": "Asia/Tehran",
        "iran": "Asia/Tehran",
        "utc": "UTC",
        "z": "UTC",
    }
    zone_name = aliases.get(normalized.lower(), normalized)

    try:
        return ZoneInfo(zone_name)
    except Exception:
        warn(f"Unknown source timezone '{normalized}', using {SOURCE_TZ.key}.")
        return SOURCE_TZ


def source_timezone_for_match(match):
    explicit_timezone = first_value(
        match,
        ("timezone", "time_zone", "source_timezone", "sourceTimezone", "tz"),
    )

    if explicit_timezone:
        return parse_timezone_value(explicit_timezone)

    stadium_id = first_value(match, ("stadium_id", "stadiumId"))
    zone_name = STADIUM_TIMEZONES.get(str(stadium_id or ""))

    if zone_name:
        return ZoneInfo(zone_name)

    return SOURCE_TZ


def parse_match_datetime(match):
    for key in ("kickoff_utc", "kickoff", "kickoff_iso", "datetime", "start_time"):
        parsed = parse_iso_datetime(match.get(key))

        if parsed is not None:
            return parsed

    local_datetime = first_value(
        match,
        ("datetime_iran", "local_datetime", "localDateTime", "date_time", "dateTime"),
    )
    local_date = first_value(
        match,
        ("local_date", "localDate", "date_iran", "persian_date", "date", "match_date"),
    )
    local_time = first_value(match, ("time_iran", "local_time", "localTime", "time"))
    has_wrapper_iran_time = bool(
        match.get("datetime_iran")
        or match.get("date_iran")
        or match.get("time_iran")
    )
    source_timezone = TEHRAN_TZ if has_wrapper_iran_time else source_timezone_for_match(match)

    if local_datetime and not local_date:
        local_date = local_datetime

    parsed_date = None

    if local_date:
        parsed_date = parse_numeric_date(local_date, prefer_jalali="persian" in str(local_date).lower())

        if parsed_date is None and local_date == match.get("persian_date"):
            parsed_date = parse_numeric_date(local_date, prefer_jalali=True)

    if parsed_date is None:
        for key in ("date",):
            parsed = parse_iso_datetime(match.get(key))

            if parsed is not None:
                return parsed

        return None

    try:
        time_source = local_date if has_time_value(local_date) else local_datetime or local_time
        parsed_time = parse_time_value(time_source)
        local_dt = datetime(
            *parsed_date,
            parsed_time.hour,
            parsed_time.minute,
            tzinfo=source_timezone,
        )
    except ValueError:
        return None

    return local_dt.astimezone(UTC_TZ)


def normalize_match_name(value):
    text = repair_text(value) or ""
    text = normalize_digits(text).strip().lower()
    replacements = {
        "\u064a": "\u06cc",
        "\u0643": "\u06a9",
        "\u0623": "\u0627",
        "\u0625": "\u0627",
        "\u0622": "\u0627",
        "\u0629": "\u0647",
        "\u200c": "",
        "\u200f": "",
        "\u200e": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[\s\-_().,'\"/]+", "", text)
    return text


def provider_team_names(provider_match, side):
    team = provider_match.get("host") if side == "home" else provider_match.get("guest")
    names = []

    if isinstance(team, dict):
        names.extend(
            [
                team.get("name"),
                team.get("title"),
                team.get("enName"),
                team.get("latinName"),
                team.get("shortName"),
            ]
        )

    names.extend(
        [
            provider_match.get("hostName") if side == "home" else provider_match.get("guestName"),
            provider_match.get("homeName") if side == "home" else provider_match.get("awayName"),
            provider_match.get("homeTeamName") if side == "home" else provider_match.get("awayTeamName"),
        ]
    )

    return {normalize_match_name(name) for name in names if name}


def local_team_names(match, side):
    return {
        normalize_match_name(value)
        for value in (
            match.get(f"{side}_fa"),
            match.get(f"{side}_en"),
            match.get(f"{side}_team_name_fa"),
            match.get(f"{side}_team_name_en"),
            match.get(f"{side}_team_label"),
            match.get(f"{side}_team"),
        )
        if value
    }


def names_match(local_names, provider_names):
    if not local_names or not provider_names:
        return False

    if local_names.intersection(provider_names):
        return True

    for local_name in local_names:
        for provider_name in provider_names:
            if local_name and provider_name and (local_name in provider_name or provider_name in local_name):
                return True

    return False


def parse_provider_kickoff(provider_match):
    candidates = (
        provider_match.get("startOnUtc"),
        provider_match.get("startDateUtc"),
        provider_match.get("startTimeUtc"),
        provider_match.get("startOn"),
        provider_match.get("startDate"),
        provider_match.get("dateTime"),
    )

    for value in candidates:
        if not value:
            continue

        parsed = parse_iso_datetime(value)

        if parsed:
            return parsed

    if provider_match.get("date") and provider_match.get("time"):
        return parse_iso_datetime(f"{provider_match.get('date')}T{provider_match.get('time')}")

    return None


def provider_raw_status(provider_match):
    return {
        "status": provider_match.get("status"),
        "statusTitle": provider_match.get("statusTitle"),
        "liveTime": provider_match.get("liveTime"),
        "isLive": bool(provider_match.get("isLive")),
        "startOnUtc": provider_match.get("startOnUtc"),
        "date": provider_match.get("date"),
        "time": provider_match.get("time"),
    }


def resolve_provider_match_for_local_match(match, provider_matches=None):
    existing = match.get("external_match_id") or match.get("raw_provider_match_id")
    match_id = match.get("id") or match.get("internal_match_id")
    teams = f"{match.get('home_en') or match.get('home_team_name_en')} vs {match.get('away_en') or match.get('away_team_name_en')}"

    if existing:
        warn(
            "[WORLDCUP_EVENT_ID_RESOLVE] "
            f"internal={match_id} teams={teams} date={match.get('kickoff_iso') or match.get('local_date') or ''} "
            f"resolved_external={existing} method=existing"
        )
        warn(
            "[EVENT_RESOLVE_AUDIT] "
            f"id={match_id} teams={teams} external={existing} method=existing event_count=unknown"
        )
        persist_external_match_id(match_id, existing)
        return str(existing), "existing", None

    persistent_external = load_persistent_match_map().get(str(match_id))

    if persistent_external:
        warn(
            "[EVENT_RESOLVE_AUDIT] "
            f"id={match_id} teams={teams} external={persistent_external} method=persistent_map event_count=unknown"
        )
        return persistent_external, "persistent_map", None

    provider_matches = provider_matches if provider_matches is not None else []
    local_home_names = local_team_names(match, "home")
    local_away_names = local_team_names(match, "away")
    kickoff = parse_match_datetime(match)
    candidates = []

    for provider_match in provider_matches:
        if not names_match(local_home_names, provider_team_names(provider_match, "home")):
            continue

        if not names_match(local_away_names, provider_team_names(provider_match, "away")):
            continue

        provider_kickoff = parse_provider_kickoff(provider_match)
        distance = (
            abs((provider_kickoff - kickoff).total_seconds())
            if provider_kickoff and kickoff
            else 0
        )

        if provider_kickoff and kickoff and distance > PROVIDER_MATCH_TOLERANCE_SECONDS:
            continue

        candidates.append((distance, provider_match))

    if candidates:
        candidates.sort(key=lambda item: item[0])
        provider_match = candidates[0][1]
        resolved = str(provider_match.get("id") or "")
        warn(
            "[WORLDCUP_EVENT_ID_RESOLVE] "
            f"internal={match_id} teams={teams} date={match.get('kickoff_iso') or match.get('local_date') or ''} "
            f"resolved_external={resolved} method=team_date_match"
        )
        warn(
            "[EVENT_RESOLVE_AUDIT] "
            f"id={match_id} teams={teams} external={resolved} method=team_date_match event_count=unknown"
        )
        persist_external_match_id(match_id, resolved)
        return resolved, "team_date_match", provider_match

    warn(
        "[WORLDCUP_EVENT_ID_RESOLVE] "
        f"internal={match_id} teams={teams} date={match.get('kickoff_iso') or match.get('local_date') or ''} "
        "resolved_external= method=failed"
    )
    warn(
        "[EVENT_RESOLVE_AUDIT] "
        f"id={match_id} teams={teams} external= method=failed event_count=0"
    )
    return None, "failed", None


def enrich_match_provider_identity(match, provider_matches=None):
    item = dict(match)
    resolved, method, provider_match = resolve_provider_match_for_local_match(item, provider_matches)

    if not resolved:
        return item

    item["external_match_id"] = resolved
    item["raw_provider_match_id"] = resolved
    item["provider"] = "varzesh3"
    item["event_id_resolution_method"] = method

    if provider_match:
        item["raw_provider_status"] = provider_raw_status(provider_match)

    return item


def format_tehran_time(kickoff_utc):
    if kickoff_utc is None:
        return ""

    return kickoff_utc.astimezone(TEHRAN_TZ).strftime("%H:%M")


def format_date_label_fa(kickoff_utc, fallback=""):
    if kickoff_utc is None:
        return fallback or ""

    tehran_dt = kickoff_utc.astimezone(TEHRAN_TZ)
    jy, jm, jd = gregorian_to_jalali(tehran_dt.year, tehran_dt.month, tehran_dt.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def format_weekday_fa(kickoff_utc):
    if kickoff_utc is None:
        return ""

    return WEEKDAYS_FA[kickoff_utc.astimezone(TEHRAN_TZ).weekday()]


def kickoff_date_key(kickoff_utc):
    if kickoff_utc is None:
        return ""

    return kickoff_utc.astimezone(TEHRAN_TZ).strftime("%Y-%m-%d")


def normalize_status(status):
    normalized = str(status or "").strip().lower().replace("-", "_").replace(" ", "_")

    if normalized in {
        "live", "in_progress", "ongoing", "1h", "2h", "ht", "half_time",
        "halftime", "break", "et", "extra_time_break", "penalties",
        "penalty_shootout", "shootout", "intermission", "pause", "extra_time_halftime",
    }:
        return "live"

    if normalized in {"finished", "finish", "ft", "ended", "end", "complete", "completed", "full_time", "fulltime", "final"}:
        return "finished"

    return "upcoming"


def normalize_status_text(value):
    text = str(repair_text(value) or "").strip().lower()
    return re.sub(r"[\s\-_]+", "_", text)


def is_football_data_source(source):
    normalized = str(source or "").strip().lower().replace("_", "-")
    return normalized in {"football-data.org", "football-data", "footballdata.org", "footballdata"}


def is_trusted_score_override(override):
    return isinstance(override, dict) and not is_football_data_source(override.get("source"))


def visible_match_result(match, result, score_source, home_score, away_score):
    value = str(result or "").strip()
    if not value:
        return None

    if value.lower() in {"home", "away", "draw"}:
        return value.lower()

    if is_football_data_source(score_source):
        return None

    home_name = str(match.get("home_en") or match.get("home_team_name_en") or match.get("home_team") or "").strip()
    away_name = str(match.get("away_en") or match.get("away_team_name_en") or match.get("away_team") or "").strip()
    lowered_result = value.casefold()

    if home_name and away_name and home_name.casefold() in lowered_result and away_name.casefold() in lowered_result:
        return value

    trusted_sources = {"raw_final", "raw_score", "events", "scorers", "worldcup_wrapper", "varzesh3"}
    if score_source in trusted_sources and home_name and away_name and home_score is not None and away_score is not None:
        return f"{home_name} {home_score} - {away_score} {away_name}"

    return None


ACTIVE_BREAK_STATUSES = {
    "ht",
    "half_time",
    "halftime",
    "break",
    "extra_time_break",
    "penalties",
    "penalty_shootout",
    "shootout",
    "intermission",
    "pause",
    "extra_time_halftime",
}

ACTIVE_BREAK_MARKERS = (
    "half time",
    "half-time",
    "halftime",
    "extra time break",
    "penalty shootout",
    "\u067e\u0627\u06cc\u0627\u0646 \u0646\u06cc\u0645\u0647 \u0627\u0648\u0644",
    "\u067e\u0627\u06cc\u0627\u0646 \u0646\u06cc\u0645\u0647",
    "\u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647",
    "\u0627\u0633\u062a\u0631\u0627\u062d\u062a \u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647",
    "\u0627\u0633\u062a\u0631\u0627\u062d\u062a \u0648\u0642\u062a \u0627\u0636\u0627\u0641\u0647",
    "\u0636\u0631\u0628\u0627\u062a \u067e\u0646\u0627\u0644\u062a\u06cc",
)


def match_active_break_label(match):
    raw_provider_status = match.get("raw_provider_status")
    raw_provider_status = raw_provider_status if isinstance(raw_provider_status, dict) else {}
    values = (
        match.get("status"),
        match.get("status_title"),
        match.get("statusTitle"),
        match.get("time_elapsed"),
        match.get("match_status"),
        match.get("live_badge"),
        match.get("raw_live_badge"),
        raw_provider_status.get("status"),
        raw_provider_status.get("statusTitle"),
        raw_provider_status.get("status_title"),
    )
    normalized_values = {normalize_status_text(value) for value in values if value not in (None, "")}
    combined_text = " ".join(str(repair_text(value) or "").strip().lower() for value in values)

    if normalized_values.intersection(ACTIVE_BREAK_STATUSES) or any(
        marker in combined_text for marker in ACTIVE_BREAK_MARKERS
    ):
        if "\u067e\u0627\u06cc\u0627\u0646 \u0646\u06cc\u0645\u0647" in combined_text or "\u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647" in combined_text:
            return "HT"
        if "half" in combined_text or "ht" in normalized_values:
            return "HT"
        if "penalt" in combined_text or "\u067e\u0646\u0627\u0644\u062a\u06cc" in combined_text:
            return "\u0636\u0631\u0628\u0627\u062a \u067e\u0646\u0627\u0644\u062a\u06cc"
        return "\u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647"

    return ""


def live_minute_badge(value):
    text = normalize_digits(repair_text(value) or "").strip()
    match = re.fullmatch(r"(\d{1,3}(?:\s*\+\s*\d{1,2})?)\s*['\u2032\u2019]?", text)
    if not match:
        return ""
    minute = re.sub(r"\s+", "", match.group(1))
    return f"{minute}'"


LIVE_PHASE_LABELS = {
    "first_half": ("\u0646\u06cc\u0645\u0647 \u0627\u0648\u0644", "First half"),
    "half_time": ("\u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647", "Half-time"),
    "second_half": ("\u0646\u06cc\u0645\u0647 \u062f\u0648\u0645", "Second half"),
    "extra_time_first_half": ("\u0648\u0642\u062a \u0627\u0636\u0627\u0641\u0647 \u0627\u0648\u0644", "Extra time first half"),
    "extra_time_break": ("\u0628\u06cc\u0646 \u062f\u0648 \u0648\u0642\u062a \u0627\u0636\u0627\u0641\u0647", "Extra-time break"),
    "extra_time_second_half": ("\u0648\u0642\u062a \u0627\u0636\u0627\u0641\u0647 \u062f\u0648\u0645", "Extra time second half"),
    "penalty_shootout": ("\u0636\u0631\u0628\u0627\u062a \u067e\u0646\u0627\u0644\u062a\u06cc", "Penalty shootout"),
}


def derive_live_phase(match):
    raw_provider_status = match.get("raw_provider_status")
    raw_provider_status = raw_provider_status if isinstance(raw_provider_status, dict) else {}
    values = (
        match.get("status"),
        match.get("raw_live_badge"),
        match.get("live_badge"),
        match.get("time_elapsed"),
        match.get("raw_minute"),
        match.get("minute"),
        match.get("status_title"),
        match.get("statusTitle"),
        match.get("match_status"),
        raw_provider_status.get("status"),
        raw_provider_status.get("statusTitle"),
        raw_provider_status.get("status_title"),
    )
    normalized_values = {
        normalize_status_text(value) for value in values if value not in (None, "")
    }
    combined_text = " ".join(
        str(repair_text(value) or "").strip().lower() for value in values if value not in (None, "")
    )

    penalty_markers = {"penalty", "penalties", "penalty_shootout", "shootout"}
    extra_break_markers = {"extra_time_break", "extra_time_halftime"}
    half_time_markers = {"ht", "half_time", "halftime"}

    if normalized_values.intersection(penalty_markers) or "penalty shootout" in combined_text or "\u0636\u0631\u0628\u0627\u062a \u067e\u0646\u0627\u0644\u062a\u06cc" in combined_text:
        phase = "penalty_shootout"
    elif (
        normalized_values.intersection(extra_break_markers)
        or "extra time break" in combined_text
        or "\u0627\u0633\u062a\u0631\u0627\u062d\u062a \u0648\u0642\u062a \u0627\u0636\u0627\u0641\u0647" in combined_text
    ):
        phase = "extra_time_break"
    elif (
        normalized_values.intersection(half_time_markers)
        or "half time" in combined_text
        or "half-time" in combined_text
        or "\u067e\u0627\u06cc\u0627\u0646 \u0646\u06cc\u0645\u0647 \u0627\u0648\u0644" in combined_text
        or "\u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647" in combined_text
        or "\u0627\u0633\u062a\u0631\u0627\u062d\u062a \u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647" in combined_text
    ):
        phase = "half_time"
    else:
        minute_token = ""
        minute_values = (
            match.get("raw_live_badge"),
            match.get("live_badge"),
            match.get("time_elapsed"),
            match.get("raw_minute"),
            match.get("minute"),
            match.get("status_title"),
            match.get("statusTitle"),
            raw_provider_status.get("statusTitle"),
            raw_provider_status.get("status_title"),
        )
        for value in minute_values:
            text = normalize_digits(repair_text(value) or "")
            minute_match = re.search(r"(?<!\d)(\d{1,3}(?:\s*\+\s*\d{1,2})?)(?!\d)", text)
            if minute_match:
                minute_token = re.sub(r"\s+", "", minute_match.group(1))
                break

        base_minute = coerce_int(minute_token.split("+", 1)[0]) if minute_token else None
        explicit_phases = (
            ("extra_time_first_half", "extra_time_first_half"),
            ("extra_time_second_half", "extra_time_second_half"),
            ("1h", "first_half"),
            ("2h", "second_half"),
            ("first_half", "first_half"),
            ("second_half", "second_half"),
        )
        phase = next(
            (phase_name for marker, phase_name in explicit_phases if marker in normalized_values),
            "",
        )
        if not phase and base_minute is not None:
            if 1 <= base_minute <= 45:
                phase = "first_half"
            elif 46 <= base_minute <= 90:
                phase = "second_half"
            elif 91 <= base_minute <= 105:
                phase = "extra_time_first_half"
            elif base_minute >= 106:
                phase = "extra_time_second_half"

        if not phase:
            return {
                "live_phase": "",
                "live_phase_fa": "",
                "live_phase_en": "",
                "live_display_fa": "",
                "live_display_en": "",
            }

        label_fa, label_en = LIVE_PHASE_LABELS[phase]
        return {
            "live_phase": phase,
            "live_phase_fa": label_fa,
            "live_phase_en": label_en,
            "live_display_fa": f"{label_fa} - {minute_token}'" if minute_token else label_fa,
            "live_display_en": f"{label_en} - {minute_token}'" if minute_token else label_en,
        }

    label_fa, label_en = LIVE_PHASE_LABELS[phase]
    return {
        "live_phase": phase,
        "live_phase_fa": label_fa,
        "live_phase_en": label_en,
        "live_display_fa": label_fa,
        "live_display_en": label_en,
    }


def best_live_badge(match, active_break_label=""):
    phase_info = derive_live_phase(match)
    if phase_info["live_display_fa"]:
        return phase_info["live_display_fa"]

    if active_break_label:
        return active_break_label

    values = (
        match.get("raw_live_badge"),
        match.get("live_badge"),
        match.get("time_elapsed"),
        match.get("raw_minute"),
        match.get("minute"),
        match.get("status_title"),
        match.get("statusTitle"),
    )
    for value in values:
        minute_badge = live_minute_badge(value)
        if minute_badge:
            return minute_badge

    return "LIVE"


def raw_live_signal(match):
    values = (match.get("raw_live_badge"), match.get("live_badge"), match.get("time_elapsed"))
    for value in values:
        normalized = normalize_status_text(value)
        if normalized in {"live", "1h", "2h", "ht", "et"} or live_minute_badge(value):
            return True
    return False


def explicit_full_time_signal(match, raw_provider_status):
    values = (
        match.get("status_title"),
        match.get("statusTitle"),
        match.get("time_elapsed"),
        raw_provider_status.get("statusTitle"),
        raw_provider_status.get("status_title"),
    )
    normalized = {normalize_status_text(value) for value in values if value not in (None, "")}
    final_markers = {"ft", "full_time", "fulltime", "final", "final_score", "match_finished", "result"}
    combined = " ".join(str(repair_text(value) or "").lower() for value in values)
    return bool(normalized.intersection(final_markers)) or str(raw_provider_status.get("status") or "") in {"7", "90", "100"} or "\u0646\u062a\u06cc\u062c\u0647 \u0646\u0647\u0627\u06cc\u06cc" in combined


def is_true_like(value):
    if value is True:
        return True

    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def has_match_score(match):
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = first_value(match, ("home_score", "homeScore", "home_goals", "homeGoals"))
    away_score = first_value(match, ("away_score", "awayScore", "away_goals", "awayGoals"))

    if home_score is None:
        home_score = score.get("home")

    if away_score is None:
        away_score = score.get("away")

    return home_score is not None and away_score is not None


def score_values(match):
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = first_value(match, ("home_score", "homeScore", "home_goals", "homeGoals"))
    away_score = first_value(match, ("away_score", "awayScore", "away_goals", "awayGoals"))

    if home_score is None:
        home_score = score.get("home")

    if away_score is None:
        away_score = score.get("away")

    return coerce_int(home_score), coerce_int(away_score)


def raw_score_is_placeholder(match):
    home_score, away_score = score_values(match)
    return home_score == 0 and away_score == 0


def kickoff_is_safely_past(match, hours_after_kickoff=3):
    kickoff_utc = parse_match_datetime(match)

    if kickoff_utc is None:
        return False

    return kickoff_utc + timedelta(hours=hours_after_kickoff) < datetime.now(UTC_TZ)


def kickoff_is_past(match):
    kickoff_utc = parse_match_datetime(match)

    if kickoff_utc is None:
        return False

    return kickoff_utc < datetime.now(UTC_TZ)


def has_trusted_result_signal(match):
    score_source = match.get("score_source") or match.get("_score_source")
    if score_source in {"raw_final", "raw_score", "events", "scorers", "score_override", "worldcup_wrapper"}:
        return True

    if match.get("needs_score_sync") is True:
        return True

    if match.get("result"):
        return True

    return has_match_score(match)


def can_show_in_results(match):
    status = normalize_status_text(match.get("status"))

    if match.get("is_finished") is True or status == "finished":
        return True

    return status == "pending_result" and kickoff_is_past(match) and has_trusted_result_signal(match)


def event_button_visibility(match):
    if not match.get("id"):
        return False, "missing_internal_id"

    status = normalize_status_text(match.get("status"))

    if match.get("is_live") is True or status == "live":
        return True, "live"

    if match.get("is_finished") is True or status == "finished":
        return True, "finished"

    if status == "pending_result" and kickoff_is_past(match):
        return True, "pending_past_match"

    return False, "upcoming"


def can_show_event_button(match):
    return event_button_visibility(match)[0]


def attach_visibility_flags(match):
    item = dict(match)
    event_button, event_button_reason = event_button_visibility(item)
    item["can_show_in_results"] = can_show_in_results(item)
    item["can_show_event_button"] = event_button
    item["event_button_reason"] = event_button_reason
    return item


def normalize_match_status(match):
    phase_info = derive_live_phase(match)
    raw_provider_status = match.get("raw_provider_status")
    raw_provider_status = raw_provider_status if isinstance(raw_provider_status, dict) else {}
    raw_status_value = None
    raw_status_title = ""
    raw_is_live = False

    if raw_provider_status:
        raw_status_value = raw_provider_status.get("status")
        raw_status_title = str(repair_text(raw_provider_status.get("statusTitle")) or "")
        raw_is_live = is_true_like(raw_provider_status.get("isLive"))

    status_candidates = [
        match.get("status"),
        match.get("status_title"),
        match.get("time_elapsed"),
        match.get("match_status"),
        match.get("statusTitle"),
        match.get("raw_status"),
        match.get("live_badge"),
        match.get("raw_live_badge"),
        raw_status_title,
    ]
    normalized_candidates = {
        normalize_status_text(value)
        for value in status_candidates
        if value is not None and value != ""
    }
    finished_statuses = {
        "finished",
        "finish",
        "ft",
        "full_time",
        "fulltime",
        "ended",
        "end",
        "complete",
        "completed",
        "final",
        "final_score",
        "match_finished",
        "result",
    }
    live_statuses = {
        "live", "in_progress", "ongoing", "1h", "2h", "ht", "half_time",
        "halftime", "break", "et", "extra_time_break", "penalties",
        "penalty_shootout", "shootout", "first_half", "second_half",
        "intermission", "pause", "extra_time_halftime",
    }
    cancelled_statuses = {
        "cancelled",
        "canceled",
        "postponed",
        "suspended",
        "abandoned",
        "delayed",
    }
    raw_status_text = " ".join(str(repair_text(value) or "") for value in status_candidates)
    is_cancelled_or_postponed = bool(normalized_candidates.intersection(cancelled_statuses))
    is_safely_past = kickoff_is_safely_past(match)
    score_source = match.get("_score_source")
    home_score, away_score = score_values(match)
    has_reliable_time_fallback_score = (
        score_source in {"events", "scorers"}
        or (
            has_match_score(match)
            and home_score is not None
            and away_score is not None
            and (home_score != 0 or away_score != 0)
        )
    )

    # Half-time and other active breaks must win over generic final/title checks.
    active_break_label = match_active_break_label(match)
    has_raw_live_signal = raw_live_signal(match)
    if active_break_label or (has_raw_live_signal and not explicit_full_time_signal(match, raw_provider_status)):
        return {
            "status": "live",
            "is_finished": False,
            "is_live": True,
            "is_upcoming": False,
            "live_badge": best_live_badge(match, active_break_label),
            **phase_info,
        }

    if (
        is_true_like(match.get("finished"))
        or match.get("is_finished") is True
        or normalized_candidates.intersection(finished_statuses)
        or str(raw_status_value) in {"3", "7", "90", "100", "finished"}
        or "\u0646\u062a\u06cc\u062c\u0647 \u0646\u0647\u0627\u06cc\u06cc" in raw_status_title
        or "\u067e\u0627\u06cc\u0627\u0646" in raw_status_text
        or (
            is_safely_past
            and has_reliable_time_fallback_score
            and not is_cancelled_or_postponed
            and not raw_is_live
            and match.get("is_live") is not True
        )
    ):
        return {
            "status": "finished",
            "is_finished": True,
            "is_live": False,
            "is_upcoming": False,
            "live_badge": "",
            **phase_info,
        }

    if (
        raw_is_live
        or match.get("is_live") is True
        or normalized_candidates.intersection(live_statuses)
    ):
        return {
            "status": "live",
            "is_finished": False,
            "is_live": True,
            "is_upcoming": False,
            "live_badge": best_live_badge(match),
            **phase_info,
        }

    if (
        is_safely_past
        and raw_score_is_placeholder(match)
        and match.get("_score_source") == "unresolved"
        and not is_cancelled_or_postponed
    ):
        return {
            "status": "pending_result",
            "is_finished": False,
            "is_live": False,
            "is_upcoming": False,
            "live_badge": "",
            **phase_info,
        }

    return {
        "status": "upcoming",
        "is_finished": False,
        "is_live": False,
        "is_upcoming": True,
        "live_badge": "",
        **phase_info,
    }


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
    def event_layers():
        current = event
        seen = set()

        for _ in range(4):
            if not isinstance(current, dict):
                break

            marker = id(current)
            if marker in seen:
                break

            seen.add(marker)
            yield current
            current = current.get("raw_event")

    def first_layer_value(keys):
        for layer in event_layers():
            value = first_value(layer, keys)

            if value is not None and value != "":
                return value

        return None

    def all_event_text():
        values = []

        for layer in event_layers():
            for key in ("description", "title", "label", "eventTitle", "typeTitle", "decisionTitle", "name"):
                value = layer.get(key)

                if value is not None and value != "":
                    values.append(str(repair_text(value) or value))

        return " ".join(values).strip().lower()

    text = all_event_text()
    raw_event_type = coerce_int(first_layer_value(("eventType", "raw_type")))
    card_type = coerce_int(first_layer_value(("cardType", "card_type")))

    if (
        raw_event_type == 5
        or "گل رد شده" in text
        or ("گل" in text and "مردود" in text)
        or ("گل" in text and "کمک داور ویدیویی" in text)
        or ("goal" in text and ("disallowed" in text or "disallow" in text))
    ):
        return "var_disallowed_goal"

    if card_type == 3 or "کارت قرمز" in text or "red card" in text:
        return "red_card"

    if card_type == 1 or "کارت زرد" in text or "yellow card" in text:
        return "yellow_card"

    normalized = str(
        first_value(event, ("normalized_type", "type", "event_type", "eventType")) or ""
    ).strip().lower().replace("-", "_").replace(" ", "_")

    aliases = {
        "yellow": "yellow_card",
        "yellowcard": "yellow_card",
        "card_yellow": "yellow_card",
        "red": "red_card",
        "redcard": "red_card",
        "card_red": "red_card",
        "penalty": "penalty_event",
        "missed_penalty": "penalty_missed",
        "var_disallowed": "var_disallowed_goal",
        "disallowed_var_goal": "var_disallowed_goal",
        "disallowed_goal": "var_disallowed_goal",
        "sub": "substitution",
        "subst": "substitution",
        "substitute": "substitution",
        "change": "substitution",
    }
    normalized = aliases.get(normalized, normalized)

    allowed = {
        "goal",
        "yellow_card",
        "red_card",
        "substitution",
        "var",
        "penalty_goal",
        "penalty_event",
        "own_goal",
        "var_disallowed_goal",
        "disallowed_goal",
        "penalty_missed",
        "injury",
        "half_time",
        "full_time",
        "unknown",
    }

    return normalized if normalized in allowed else "unknown"


def parse_card_player_from_description(description):
    text = str(repair_text(description) or "").strip()
    if not text:
        return ""

    text = re.sub(r"^\s*\u06a9\u0627\u0631\u062a\s+(?:\u0632\u0631\u062f|\u0642\u0631\u0645\u0632)\s*", "", text)
    text = re.sub(rf"^\s*\u062f\u0642\u06cc\u0642\u0647\s*{minute_token_pattern()}\s*", "", text)
    text = re.sub(rf"^\s*{minute_token_pattern()}\s*", "", text)
    player = text.strip(" -:\u200c")
    return "" if is_minute_token(player) else player


def parse_substitution_description(description):
    text = str(repair_text(description) or "").strip()
    if not text:
        return None, None

    text = re.sub(
        rf"^\s*\u062a\u0639\u0648\u06cc\u0636\s+\u062f\u0642\u06cc\u0642\u0647\s*{minute_token_pattern()}\s*",
        "",
        text,
    )
    text = re.sub(r"^\s*\u062a\u0639\u0648\u06cc\u0636\s*", "", text)
    text = re.sub(rf"^\s*\u062f\u0642\u06cc\u0642\u0647\s*{minute_token_pattern()}\s*", "", text)
    parts = [
        part.strip(" -:\u200c")
        for part in re.split(r"\s+[-\u2013\u2014]\s+", text)
        if part.strip(" -:\u200c") and not is_minute_token(part)
    ]

    if len(parts) >= 2:
        return parts[0], parts[1]

    return None, None


parse_substitution_from_description = parse_substitution_description


def normalize_event(event):
    if not isinstance(event, dict):
        return None

    side = first_value(event, ("team_side", "side", "home_or_away", "homeAway"))
    side = str(side or "").strip().lower().replace("-", "_").replace(" ", "_")

    if side in {"host", "home_team"}:
        side = "home"

    if side in {"guest", "away_team"}:
        side = "away"

    if side not in {"home", "away"}:
        side = ""

    normalized_type = normalize_event_type(event)
    raw_type = first_value(event, ("raw_type", "eventType", "event_type_code"))
    description = repair_text(first_value(event, ("description", "title", "label")))
    player = repair_text(
        first_value(
            event,
            ("player", "player_name", "playerName", "scorer", "goal_scorer", "card_player"),
        )
    )
    player_in = repair_text(first_value(event, ("player_in", "playerIn", "in_player", "player_entered")))
    player_out = repair_text(first_value(event, ("player_out", "playerOut", "out_player", "player_left")))
    assist = repair_text(
        first_value(
            event,
            ("assist", "assist_name", "assistName", "pass", "pass_name", "passName", "assistantName"),
        )
    )

    if normalized_type in {"yellow_card", "red_card"} and not player:
        player = parse_card_player_from_description(description)

    if normalized_type == "substitution" and (not player_in or not player_out):
        parsed_player_in, parsed_player_out = parse_substitution_from_description(description)
        player_in = player_in or parsed_player_in
        player_out = player_out or parsed_player_out

    raw_minute_value = first_value(event, ("display_minute", "displayMinute", "raw_minute", "rawMinute"))
    raw_minute = format_minute_token(raw_minute_value)
    description_minute = extract_minute_from_description(description)

    if description_minute and "+" in description_minute and "+" not in raw_minute:
        raw_minute = description_minute

    if not raw_minute:
        raw_minute = description_minute

    minute = coerce_int(first_value(event, ("minute", "time", "elapsed")))

    if minute is None and raw_minute:
        minute = coerce_int(raw_minute.split("+", 1)[0])

    return {
        "id": event.get("id"),
        "minute": minute or 0,
        "raw_minute": raw_minute,
        "display_minute": raw_minute,
        "type": normalized_type,
        "raw_type": raw_type,
        "normalized_type": normalized_type,
        "is_scoring_event": normalized_type in SCORING_EVENT_TYPES,
        "team": side,
        "team_side": side,
        "team_name": repair_text(first_value(event, ("team_name", "teamName"))),
        "player": str(player or "").strip(),
        "player_name": str(player or "").strip(),
        "scorer": repair_text(first_value(event, ("scorer", "goal_scorer"))) or player,
        "assist": assist,
        "assist_name": assist,
        "assistName": assist,
        "player_in": player_in,
        "playerIn": player_in,
        "player_out": player_out,
        "playerOut": player_out,
        "description": description,
        "video_url": event.get("video_url"),
        "created_at": event.get("created_at"),
        "raw_event": event,
    }


def normalize_events(events):
    normalized_events = []

    for event in events if isinstance(events, list) else []:
        normalized_event = normalize_event(event)

        if normalized_event is not None:
            normalized_events.append(normalized_event)

    return normalized_events


def normalize_provider_event(event, index):
    side_value = event.get("side")
    side = "home" if side_value == 0 else "away" if side_value == 1 else ""
    event_type_value = event.get("eventType", event.get("type"))
    normalized_type = normalize_event_type(event)
    player_object = event.get("player") if isinstance(event.get("player"), dict) else {}
    assist_object = event.get("assist") if isinstance(event.get("assist"), dict) else {}
    player = (
        event.get("playerName")
        or event.get("strickerName")
        or event.get("strikerName")
        or event.get("kickerName")
        or player_object.get("name")
    )
    assist = (
        event.get("assistName")
        or event.get("assistantName")
        or event.get("assistPlayerName")
        or assist_object.get("name")
    )

    return {
        "id": event.get("id") or event.get("eventId") or index,
        "minute": event.get("time") or event.get("minute") or event.get("eventTime"),
        "raw_minute": event.get("time") or event.get("minute") or event.get("eventTime"),
        "event_type": normalized_type or event_type_value,
        "type": normalized_type or event_type_value,
        "raw_type": event_type_value,
        "normalized_type": normalized_type,
        "is_scoring_event": normalized_type in SCORING_EVENT_TYPES,
        "team_side": side,
        "side": side,
        "player": player,
        "scorer": event.get("strickerName") or event.get("strikerName") or event.get("kickerName"),
        "assist": assist,
        "description": event.get("description") or event.get("title") or event.get("eventTitle") or event.get("typeTitle"),
        "video_url": event.get("videoUrl") or event.get("video_url"),
        "created_at": event.get("createdAt") or event.get("created_at"),
        "raw_event": event,
    }


def count_goal_events_by_side(events):
    score = {"home": 0, "away": 0}

    for event in events:
        event_type = event.get("normalized_type") or event.get("type")

        if event_type not in SCORING_EVENT_TYPES:
            continue

        side = str(event.get("team_side") or event.get("team") or "").strip().lower()

        if side in {"home", "away"}:
            score[side] += 1

    return score["home"], score["away"]


def derive_score_from_provider_events(match, match_id):
    candidate_ids = []

    for candidate_id in (match_id,):
        if candidate_id is not None and candidate_id != "" and candidate_id not in candidate_ids:
            candidate_ids.append(candidate_id)

    for candidate_id in candidate_ids:
        payload = fetch_json(f"/match/{candidate_id}/events")
        events = normalize_events(raw_events_from_payload(payload))
        home_score, away_score = count_goal_events_by_side(events)

        if home_score or away_score:
            return home_score, away_score

    return None, None


def derive_score_from_scorers(match):
    home_events = events_from_scorers({"id": match.get("id"), "home_scorers": match.get("home_scorers")})
    away_events = events_from_scorers({"id": match.get("id"), "away_scorers": match.get("away_scorers")})
    events = normalize_events(home_events + away_events)
    home_score, away_score = count_goal_events_by_side(events)

    if home_score or away_score:
        return home_score, away_score

    return None, None


def explicit_final_status(match):
    raw_provider_status = match.get("raw_provider_status") if isinstance(match.get("raw_provider_status"), dict) else {}
    status_candidates = [
        match.get("status"),
        match.get("status_title"),
        match.get("time_elapsed"),
        match.get("match_status"),
        match.get("statusTitle"),
        match.get("raw_status"),
        raw_provider_status.get("statusTitle"),
    ]
    normalized_candidates = {
        normalize_status_text(value)
        for value in status_candidates
        if value is not None and value != ""
    }
    raw_status_title = str(raw_provider_status.get("statusTitle") or match.get("statusTitle") or "")
    raw_status_text = " ".join(str(value or "") for value in status_candidates)

    return (
        is_true_like(match.get("finished"))
        or match.get("is_finished") is True
        or normalized_candidates.intersection({
            "finished",
            "finish",
            "ft",
            "full_time",
            "fulltime",
            "ended",
            "end",
            "complete",
            "completed",
            "final",
            "final_score",
            "match_finished",
            "result",
        })
        or str(raw_provider_status.get("status") or match.get("statusCode") or match.get("state") or "") in {"3", "7", "90", "100", "finished"}
        or "\u0646\u062a\u06cc\u062c\u0647 \u0646\u0647\u0627\u06cc\u06cc" in raw_status_title
        or "\u067e\u0627\u06cc\u0627\u0646" in raw_status_text
    )


def resolve_match_score(match, match_id):
    raw_home_score, raw_away_score = score_values(match)

    if explicit_final_status(match) and raw_home_score is not None and raw_away_score is not None:
        return raw_home_score, raw_away_score, "raw_final"

    scorer_home_score, scorer_away_score = derive_score_from_scorers(match)

    if scorer_home_score is not None and scorer_away_score is not None:
        return scorer_home_score, scorer_away_score, "scorers"

    if kickoff_is_safely_past(match) and raw_score_is_placeholder(match):
        event_home_score, event_away_score = derive_score_from_provider_events(match, match_id)

        if event_home_score is not None and event_away_score is not None:
            return event_home_score, event_away_score, "events"

    if raw_home_score is not None and raw_away_score is not None and (raw_home_score != 0 or raw_away_score != 0):
        return raw_home_score, raw_away_score, "raw_score"

    return raw_home_score, raw_away_score, "unresolved"


def override_status_is_finished(override):
    return normalize_status_text(override.get("status")) in {
        "finished",
        "finish",
        "ft",
        "full_time",
        "fulltime",
        "completed",
        "complete",
    }


def apply_local_score_overrides(matches):
    try:
        from db_service import get_all_match_score_overrides_from_db
    except Exception as exc:
        warn(f"Local score overrides unavailable: {exc}")
        return matches

    try:
        overrides = get_all_match_score_overrides_from_db()
    except Exception as exc:
        warn(f"Local score overrides failed: {exc}")
        return matches

    if not overrides:
        return matches

    adjusted_matches = []

    for match in matches:
        item = dict(match)
        override = overrides.get(item.get("id"))

        if not is_trusted_score_override(override):
            adjusted_matches.append(attach_visibility_flags(item))
            continue

        home_score = override.get("home_score")
        away_score = override.get("away_score")

        if home_score is None or away_score is None:
            adjusted_matches.append(attach_visibility_flags(item))
            continue

        item["home_score"] = home_score
        item["away_score"] = away_score
        item["score"] = {
            "home": home_score,
            "away": away_score,
        }
        item["result"] = override.get("result") or item.get("result")
        item["score_source"] = override.get("source") or "score_override"
        item["needs_score_sync"] = False

        current_status = normalize_match_status(item)
        if not current_status["is_live"] and (
            override_status_is_finished(override) or kickoff_is_safely_past(item, hours_after_kickoff=0)
        ):
            item["status"] = "finished"
            item["is_finished"] = True
            item["is_live"] = False
            item["is_upcoming"] = False
            item["live_badge"] = False

        adjusted_matches.append(attach_visibility_flags(item))

    return adjusted_matches


def normalize_match(match):
    if not isinstance(match, dict):
        return None

    match = dict(match)
    incoming_score_source = match.get("score_source") or match.get("source")
    if is_football_data_source(incoming_score_source):
        for key in ("home_score", "homeScore", "away_score", "awayScore", "result"):
            match[key] = None
        match["score"] = {}

    match_id = first_value(match, ("id", "internal_match_id", "match_id", "matchId"))
    normalized_match_id = coerce_int(match_id)
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = first_value(match, ("home_score", "homeScore"))
    away_score = first_value(match, ("away_score", "awayScore"))

    if home_score is None:
        home_score = score.get("home")

    if away_score is None:
        away_score = score.get("away")

    resolved_home_score, resolved_away_score, score_source = resolve_match_score(match, normalized_match_id if normalized_match_id is not None else match_id)
    home_score = resolved_home_score
    away_score = resolved_away_score
    match_for_status = {
        **match,
        "home_score": home_score,
        "away_score": away_score,
        "score": {
            "home": home_score,
            "away": away_score,
        },
        "_score_source": score_source,
    }
    status_info = normalize_match_status(match_for_status)
    status = status_info["status"]

    home_name_en = first_team_text(match, "home", language="en")
    away_name_en = first_team_text(match, "away", language="en")
    home_name_fa = first_team_text(match, "home", language="fa") or placeholder_fa(home_name_en)
    away_name_fa = first_team_text(match, "away", language="fa") or placeholder_fa(away_name_en)
    normalized_score_source = score_source if score_source != "unresolved" else "worldcup_wrapper"
    visible_result = visible_match_result(
        {**match, "home_en": home_name_en, "away_en": away_name_en},
        match.get("result"),
        normalized_score_source,
        coerce_int(home_score),
        coerce_int(away_score),
    )
    home_flag = match.get("home_flag") or match.get("home_team_flag") or ""
    away_flag = match.get("away_flag") or match.get("away_team_flag") or ""
    stage, stage_label = resolve_stage(match)
    wrapper_kickoff = match.get("kickoff")
    wrapper_kickoff_utc = match.get("kickoff_utc")
    wrapper_kickoff_iso = match.get("kickoff_iso") or wrapper_kickoff
    wrapper_date = match.get("date")
    wrapper_date_iran = match.get("date_iran")
    wrapper_time_iran = match.get("time_iran")
    wrapper_datetime_iran = match.get("datetime_iran")
    kickoff_utc = parse_match_datetime(match)
    kickoff_tehran = kickoff_utc.astimezone(TEHRAN_TZ) if kickoff_utc else None
    fallback_kickoff_iso = kickoff_tehran.isoformat() if kickoff_tehran else ""
    fallback_kickoff_utc_iso = kickoff_utc.isoformat().replace("+00:00", "Z") if kickoff_utc else ""
    date_iran = wrapper_date_iran or format_date_label_fa(
        kickoff_utc,
        match.get("persian_date") or "",
    )
    time_iran = wrapper_time_iran or format_tehran_time(kickoff_utc) or ""
    datetime_iran = wrapper_datetime_iran or (
        f"{date_iran} {time_iran}" if date_iran and time_iran else ""
    )
    date_label_fa = match.get("date_label_fa") or date_iran
    weekday_fa = match.get("weekday_fa") or format_weekday_fa(kickoff_utc)
    date_key = kickoff_date_key(kickoff_utc)
    should_debug_status = normalized_match_id in range(45, 61)

    if should_debug_status:
        raw_provider_status = match.get("raw_provider_status") if isinstance(match.get("raw_provider_status"), dict) else {}
        warn(
            "[WORLDCUP_DEBUG_STATUS] "
            f"id={normalized_match_id if normalized_match_id is not None else match_id} "
            f"external={match.get('external_match_id') or match.get('raw_provider_match_id') or ''} "
            f"teams={match.get('home_team_name_en') or match.get('home_en') or match.get('home_team') or match.get('home_team_id')} vs "
            f"{match.get('away_team_name_en') or match.get('away_en') or match.get('away_team') or match.get('away_team_id')} "
            f"raw_status={match.get('status') or match.get('time_elapsed') or ''} "
            f"raw_statusTitle={match.get('statusTitle') or match.get('status_title') or raw_provider_status.get('statusTitle') or ''} "
            f"raw_state={match.get('state') or match.get('statusCode') or raw_provider_status.get('status') or ''} "
            f"raw_date={match.get('local_date') or match.get('localDate') or match.get('persian_date') or ''} "
            f"raw_score={first_value(match, ('home_score', 'homeScore'))}-{first_value(match, ('away_score', 'awayScore'))} "
            f"normalized_status={status} "
            f"is_finished={status_info['is_finished']} "
            f"is_live={status_info['is_live']}"
        )
        warn(
            "[WORLDCUP_SCORE_RESOLVE] "
            f"id={normalized_match_id if normalized_match_id is not None else match_id} "
            f"external={match.get('external_match_id') or match.get('raw_provider_match_id') or ''} "
            f"teams={match.get('home_team_name_en') or match.get('home_en') or match.get('home_team') or match.get('home_team_id')} vs "
            f"{match.get('away_team_name_en') or match.get('away_en') or match.get('away_team') or match.get('away_team_id')} "
            f"raw_status={match.get('status') or match.get('time_elapsed') or ''} "
            f"raw_score={first_value(match, ('home_score', 'homeScore'))}-{first_value(match, ('away_score', 'awayScore'))} "
            f"score_source={score_source} "
            f"derived_score={home_score}-{away_score} "
            f"normalized_status={status}"
        )

    normalized_item = {
        **match,
        "id": normalized_match_id if normalized_match_id is not None else match_id,
        "internal_match_id": match.get("internal_match_id") or match_id,
        "external_match_id": match.get("external_match_id") or match.get("raw_provider_match_id"),
        "provider": match.get("provider") or "worldcup2026",
        "home_en": home_name_en,
        "away_en": away_name_en,
        "home_fa": home_name_fa,
        "away_fa": away_name_fa,
        "home_flag_url": home_flag,
        "away_flag_url": away_flag,
        "home_flag": display_flag(home_flag),
        "away_flag": display_flag(away_flag),
        "home_team": home_name_en,
        "away_team": away_name_en,
        "home_score": coerce_int(home_score),
        "away_score": coerce_int(away_score),
        "score": {
            "home": coerce_int(home_score),
            "away": coerce_int(away_score),
        },
        "status": status,
        "status_title": repair_text(match.get("status_title") or match.get("statusTitle")) or "",
        "is_finished": status_info["is_finished"],
        "is_live": status_info["is_live"],
        "is_upcoming": status_info["is_upcoming"],
        "live_badge": status_info.get("live_badge") or ("LIVE" if status == "live" else ""),
        "live_phase": status_info.get("live_phase") or "",
        "live_phase_fa": status_info.get("live_phase_fa") or "",
        "live_phase_en": status_info.get("live_phase_en") or "",
        "live_display_fa": status_info.get("live_display_fa") or "",
        "live_display_en": status_info.get("live_display_en") or "",
        "raw_live_badge": match.get("raw_live_badge") or match.get("live_badge"),
        "events": normalize_events(match.get("events") or []),
        "score_source": normalized_score_source,
        "needs_score_sync": score_source == "unresolved" and kickoff_is_safely_past(match) and raw_score_is_placeholder(match),
        "kickoff": wrapper_kickoff or wrapper_kickoff_utc or fallback_kickoff_iso,
        "kickoff_utc": wrapper_kickoff_utc or wrapper_kickoff or fallback_kickoff_utc_iso,
        "kickoff_iso": wrapper_kickoff_iso or fallback_kickoff_iso,
        "kickoff_ts": int(kickoff_utc.timestamp()) if kickoff_utc else None,
        "kickoff_timestamp": int(kickoff_utc.timestamp()) if kickoff_utc else None,
        "date_key": date_key,
        "date": wrapper_date or "",
        "local_date": match.get("local_date") or match.get("localDate") or "",
        "source_timezone": source_timezone_for_match(match).key,
        "stadium_id": match.get("stadium_id") or match.get("stadiumId") or "",
        "date_iran": date_iran,
        "date_label_fa": date_label_fa,
        "weekday_fa": weekday_fa,
        "time_iran": time_iran,
        "datetime_iran": datetime_iran,
        "group": match.get("group") or "",
        "stage": stage,
        "stage_label": stage_label,
        "stadium": match.get("stadium") or match.get("stadium_name_en") or "",
        "city": match.get("city") or match.get("stadium_city_en") or "",
        "result": visible_result,
        "last_updated": match.get("last_updated"),
    }
    event_button, event_button_reason = event_button_visibility(normalized_item)
    normalized_item["can_show_in_results"] = can_show_in_results(normalized_item)
    normalized_item["can_show_event_button"] = event_button
    normalized_item["event_button_reason"] = event_button_reason
    return normalized_item


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


def build_lookup(items):
    lookup = {}

    for item in items:
        item_id = item.get("id")

        if item_id is not None:
            lookup[str(item_id)] = item

    return lookup


def enrich_game(game, team_lookup, stadium_lookup):
    item = dict(game)
    home_team = team_lookup.get(str(item.get("home_team_id") or ""))
    away_team = team_lookup.get(str(item.get("away_team_id") or ""))
    stadium = stadium_lookup.get(str(item.get("stadium_id") or ""))

    if home_team:
        item.setdefault("home_team_name_en", home_team.get("name_en"))
        item.setdefault("home_team_name_fa", home_team.get("name_fa"))
        item.setdefault("home_team_flag", home_team.get("flag"))

    if away_team:
        item.setdefault("away_team_name_en", away_team.get("name_en"))
        item.setdefault("away_team_name_fa", away_team.get("name_fa"))
        item.setdefault("away_team_flag", away_team.get("flag"))

    if stadium:
        item.setdefault("stadium_name_en", stadium.get("name_en"))
        item.setdefault("stadium_city_en", stadium.get("city_en"))
        item.setdefault("stadium_region", stadium.get("region"))

    return item


def fetch_matches_from_wrapper():
    payload = fetch_json("/matches")
    matches = []
    games = payload_list(payload, ("games", "matches", "data", "results", "items"))

    if not games:
        payload = fetch_json("/get/games")
        games = payload_list(payload, ("matches", "games", "data", "results", "items"))

    teams_payload = fetch_json("/get/teams")
    stadiums_payload = fetch_json("/get/stadiums")
    team_lookup = build_lookup(payload_list(teams_payload, ("teams", "data", "results", "items")))
    stadium_lookup = build_lookup(payload_list(stadiums_payload, ("stadiums", "data", "results", "items")))
    provider_matches = []

    for match in games:
        enriched_match = enrich_game(match, team_lookup, stadium_lookup)
        enriched_match = enrich_match_provider_identity(enriched_match, provider_matches)
        normalized_match = normalize_match(enriched_match)

        if normalized_match is not None:
            matches.append(normalized_match)

    return matches


def fetch_teams_from_wrapper():
    payload = fetch_json("/get/teams")
    if payload is None:
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
        "kickoff_iso",
        "kickoff_ts",
        "kickoff_timestamp",
        "date_key",
        "date",
        "date_iran",
        "date_label_fa",
        "weekday_fa",
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
        "is_finished",
        "is_live",
        "is_upcoming",
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


def raw_events_from_payload(payload):
    if isinstance(payload, dict) and isinstance(payload.get("match"), dict):
        match_events = payload_list(payload["match"], ("events", "timeline", "data", "items"))

        if match_events:
            return match_events

    return payload_list(payload, ("events", "timeline", "data", "items"))


def parse_scorer_list(value):
    if isinstance(value, list):
        return value

    normalized = str(value or "").strip()

    if not normalized or normalized.lower() == "null":
        return []

    normalized = normalized.strip("{}[]")
    return [
        item.strip().strip('"').strip("'")
        for item in re.split(r"[,;،]", normalized)
        if item.strip()
    ]


def parse_scorer_entry(entry):
    if isinstance(entry, dict):
        scorer = repair_text(first_value(entry, ("scorer", "player", "player_name", "playerName", "name")))
        raw_minute = format_minute_token(first_value(entry, ("display_minute", "raw_minute", "minute", "time", "elapsed")))
        minute = coerce_int(raw_minute.split("+", 1)[0]) if raw_minute else coerce_int(entry.get("minute"))

        return {
            "scorer": scorer or "",
            "minute": minute,
            "raw_minute": raw_minute,
        }

    text = repair_text(entry) or ""
    normalized = normalize_digits(text)
    minute_match = re.search(
        r"(\d{1,3}(?:\s*\+\s*\d{1,2})?)\s*(?:['\u2019\u2032])?(?:\([^)]*\))?\s*$",
        normalized,
    )
    raw_minute = re.sub(r"\s+", "", minute_match.group(1)) if minute_match else ""
    scorer = normalized

    if minute_match:
        scorer = normalized[:minute_match.start()] + normalized[minute_match.end():]

    scorer = re.sub(r"\([^)]*\)", "", scorer)
    scorer = scorer.strip(" -:\u200c'")

    return {
        "scorer": scorer,
        "minute": coerce_int(raw_minute.split("+", 1)[0]) if raw_minute else None,
        "raw_minute": raw_minute,
    }


def events_from_scorers(game):
    events = []

    for side, key in (("home", "home_scorers"), ("away", "away_scorers")):
        for index, scorer_entry in enumerate(parse_scorer_list(game.get(key)), start=1):
            parsed_scorer = parse_scorer_entry(scorer_entry)

            if not parsed_scorer["scorer"]:
                continue

            events.append(
                {
                    "id": f"{game.get('id')}-{side}-goal-{index}",
                    "minute": parsed_scorer["minute"],
                    "raw_minute": parsed_scorer["raw_minute"],
                    "display_minute": parsed_scorer["raw_minute"],
                    "type": "goal",
                    "normalized_type": "goal",
                    "team": side,
                    "team_side": side,
                    "player": parsed_scorer["scorer"],
                    "player_name": parsed_scorer["scorer"],
                    "scorer": parsed_scorer["scorer"],
                    "description": "goal",
                }
            )

    return events


def find_match_by_id(match_id):
    try:
        normalized_match_id = int(match_id)
    except (TypeError, ValueError):
        normalized_match_id = match_id

    for match in get_matches_from_worldcup_wrapper():
        candidate_ids = (
            match.get("id"),
            match.get("internal_match_id"),
            match.get("external_match_id"),
        )

        if normalized_match_id in candidate_ids or str(normalized_match_id) in {
            str(candidate_id) for candidate_id in candidate_ids if candidate_id is not None
        }:
            return match

    return None


def external_match_id_for(match_id):
    match = find_match_by_id(match_id)

    if match is None:
        return match_id, None

    return match.get("external_match_id") or match.get("raw_provider_match_id"), match


def fetch_single_game(match_id):
    payload = fetch_json(f"/get/game/{match_id}")

    if isinstance(payload, dict) and isinstance(payload.get("game"), dict):
        return payload["game"], payload

    return None, payload


def fetch_events_from_wrapper(match_id, metadata_match=None):
    resolved_metadata = enrich_match_provider_identity(metadata_match or {"id": match_id}, provider_matches=[])
    local_match_id = resolved_metadata.get("id") if resolved_metadata else match_id
    external_match_id = resolved_metadata.get("external_match_id") if resolved_metadata else None
    provider = resolved_metadata.get("provider") if resolved_metadata else None
    resolve_method = resolved_metadata.get("event_id_resolution_method") if resolved_metadata else "failed"
    teams = (
        f"{resolved_metadata.get('home_en') or resolved_metadata.get('home_team_name_en') or ''} vs "
        f"{resolved_metadata.get('away_en') or resolved_metadata.get('away_team_name_en') or ''}"
        if resolved_metadata
        else ""
    )
    candidate_ids = []

    for candidate_id in (local_match_id,):
        if candidate_id is not None and candidate_id != "" and candidate_id not in candidate_ids:
            candidate_ids.append(candidate_id)

    warn(
        "Events requested: "
        f"internal_match_id={local_match_id}, "
        f"external_match_id={external_match_id or ''}, "
        f"provider={provider or ''}"
    )

    for candidate_id in candidate_ids:
        event_path = f"/match/{candidate_id}/events"
        payload = fetch_json(event_path)
        raw_events = raw_events_from_payload(payload)
        events = normalize_events(raw_events)
        warn(
            "Events provider response: "
            f"internal_match_id={local_match_id}, "
            f"provider_match_id={candidate_id}, "
            f"raw_event_count={len(raw_events)}, "
            f"normalized_event_count={len(events)}"
        )

        if events:
            warn(
                "[EVENT_RESOLVE_AUDIT] "
                f"id={local_match_id} teams={teams} external={external_match_id or ''} "
                f"method={resolve_method or 'wrapper_events'} event_count={len(events)}"
            )
            return events

        live_path = f"/match/{candidate_id}/live"
        live_payload = fetch_json(live_path)
        live_raw_events = raw_events_from_payload(live_payload)
        live_events = normalize_events(live_raw_events)
        warn(
            "Live events provider response: "
            f"internal_match_id={local_match_id}, "
            f"provider_match_id={candidate_id}, "
            f"raw_event_count={len(live_raw_events)}, "
            f"normalized_event_count={len(live_events)}"
        )

        if live_events:
            warn(
                "[EVENT_RESOLVE_AUDIT] "
                f"id={local_match_id} teams={teams} external={external_match_id or ''} "
                f"method={resolve_method or 'wrapper_live'} event_count={len(live_events)}"
            )
            return live_events

    game = None
    game_payload = None

    for candidate_id in candidate_ids:
        game, game_payload = fetch_single_game(candidate_id)

        if game:
            break

    scorer_events = events_from_scorers(game or resolved_metadata or metadata_match or {})
    normalized_scorer_events = normalize_events(scorer_events)
    warn(
        "Fallback scorer events: "
        f"internal_match_id={local_match_id}, "
        f"external_match_id={external_match_id or ''}, "
        f"raw_scorer_event_count={len(scorer_events)}, "
        f"normalized_event_count={len(normalized_scorer_events)}"
    )

    if normalized_scorer_events:
        warn(
            "[EVENT_RESOLVE_AUDIT] "
            f"id={local_match_id} teams={teams} external={external_match_id or ''} "
            f"method=scorer_fallback event_count={len(normalized_scorer_events)}"
        )
        return normalized_scorer_events

    warn(
        "Events empty: "
        f"internal_match_id={local_match_id}, "
        f"external_match_id={external_match_id or ''}, "
        f"provider={provider or ''}, "
        f"candidate_ids={candidate_ids}, "
        f"game_response={payload_debug_summary(game_payload)}"
    )
    warn(
        "[EVENT_RESOLVE_AUDIT] "
        f"id={local_match_id} teams={teams} external={external_match_id or ''} method=failed event_count=0"
    )

    return []


def fetch_events_payload_on_demand(match_id):
    payload, request_error = fetch_json_with_error(f"/match/{match_id}/events")
    raw_events = raw_events_from_payload(payload)
    events = normalize_events(raw_events)
    warning = payload.get("warning") if isinstance(payload, dict) else None
    wrapper_error = payload.get("error") if isinstance(payload, dict) else None

    return {
        "events": events,
        "warning": warning,
        "error": wrapper_error or request_error,
        "external_match_id": payload.get("external_match_id") if isinstance(payload, dict) else None,
        "provider": payload.get("provider") if isinstance(payload, dict) else None,
    }


def refresh_cache():
    matches = apply_local_score_overrides(fetch_matches_from_wrapper())
    finished_count = sum(1 for match in matches if match.get("is_finished") is True)
    live_count = sum(1 for match in matches if match.get("is_live") is True)
    upcoming_count = sum(1 for match in matches if match.get("is_upcoming") is True)
    pending_count = sum(1 for match in matches if match.get("status") == "pending_result")
    score_sources = {}

    for match in matches:
        source = match.get("score_source") or "unknown"
        score_sources[source] = score_sources.get(source, 0) + 1

    with _cache_lock:
        events = dict(_cache.get("events") or {})

        for match in matches:
            match_id = match.get("id")
            refreshed_events = match.get("events") or []

            if match_id is None:
                continue

            if refreshed_events:
                events[match_id] = refreshed_events
            elif match_id not in events:
                events[match_id] = []

        _cache["matches"] = matches
        _cache["events"] = events
        _cache["last_refresh"] = time.time()

    warn(
        "Matches normalized: "
        f"total={len(matches)}, "
        f"finished={finished_count}, "
        f"live={live_count}, "
        f"upcoming={upcoming_count}, "
        f"pending={pending_count}, "
        f"score_sources={score_sources}"
    )


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

    _external_match_id, metadata_match = external_match_id_for(normalized_match_id)

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

    _external_match_id, metadata_match = external_match_id_for(normalized_match_id)

    if metadata_match:
        metadata_match = enrich_match_provider_identity(metadata_match, provider_matches=[])

    external_match_id = None

    if metadata_match:
        external_match_id = metadata_match.get("external_match_id") or metadata_match.get("raw_provider_match_id") or None
    fetched = fetch_events_payload_on_demand(normalized_match_id)
    events = fetched["events"]
    warning = fetched.get("warning")
    error = fetched.get("error")
    stale = False

    print(
        f"[MATCH_EVENTS_FETCH] match_id={normalized_match_id} "
        f"events={len(events)} warning={warning or ''} error={error or ''}"
    )

    with _cache_lock:
        cached_events = list(_cache["events"].get(normalized_match_id) or [])

        if events:
            _cache["events"][normalized_match_id] = events
        elif (warning or error) and cached_events:
            events = cached_events
            stale = True

    if stale:
        print(
            f"[MATCH_EVENTS_CACHE_FALLBACK] match_id={normalized_match_id} "
            f"cached_events={len(events)}"
        )

    response = {
        "match_id": normalized_match_id,
        "external_match_id": fetched.get("external_match_id") or external_match_id,
        "provider": fetched.get("provider") or (metadata_match.get("provider") if metadata_match else None),
        "events": events,
    }

    if warning:
        response["warning"] = warning

    if error:
        response["error"] = error

    if stale:
        response["stale"] = True

    return response


def get_teams_from_worldcup_wrapper():
    return fetch_teams_from_wrapper()


# Backward-compatible names used by existing MatchPulse backend imports.
start_varzesh3_poller = start_worldcup_wrapper_poller
get_matches_from_varzesh3 = get_matches_from_worldcup_wrapper
get_live_matches_from_varzesh3 = get_live_matches_from_worldcup_wrapper
get_match_live_from_varzesh3 = get_match_live_from_worldcup_wrapper
get_match_events_from_varzesh3 = get_match_events_from_worldcup_wrapper
