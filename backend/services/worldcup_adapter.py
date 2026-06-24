import os
import re
import threading
import time
from datetime import datetime, time as datetime_time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests

REFRESH_INTERVAL_SECONDS = 10
DEFAULT_TIMEOUT_SECONDS = 10
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


def count_persian_chars(value):
    return len(re.findall(r"[\u0600-\u06ff]", str(value or "")))


def repair_text(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return ""

    candidates = [text]

    for encoding in ("latin1", "cp1252"):
        try:
            candidate = text.encode(encoding).decode("utf-8").strip()
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        if candidate and candidate not in candidates:
            candidates.append(candidate)

    return max(candidates, key=lambda candidate: (count_persian_chars(candidate), -candidate.count("\ufffd")))


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
    local_datetime = first_value(
        match,
        ("datetime_iran", "local_datetime", "localDateTime", "date_time", "dateTime"),
    )
    local_date = first_value(
        match,
        ("local_date", "localDate", "date_iran", "persian_date", "date", "match_date"),
    )
    local_time = first_value(match, ("time_iran", "local_time", "localTime", "time"))
    source_timezone = source_timezone_for_match(match)

    if local_datetime and not local_date:
        local_date = local_datetime

    parsed_date = None

    if local_date:
        parsed_date = parse_numeric_date(local_date, prefer_jalali="persian" in str(local_date).lower())

        if parsed_date is None and local_date == match.get("persian_date"):
            parsed_date = parse_numeric_date(local_date, prefer_jalali=True)

    if parsed_date is None:
        for key in ("kickoff_iso", "kickoff_utc", "kickoff", "datetime", "start_time", "date"):
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

    if normalized in {"live", "in_progress", "ongoing", "1h", "2h", "ht", "et"}:
        return "live"

    if normalized in {"finished", "finish", "ft", "ended", "complete", "completed"}:
        return "finished"

    return "upcoming"


def is_true_like(value):
    if value is True:
        return True

    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def normalize_match_status(match):
    raw_provider_status = match.get("raw_provider_status")
    raw_status_value = None
    raw_status_title = ""
    raw_is_live = False

    if isinstance(raw_provider_status, dict):
        raw_status_value = raw_provider_status.get("status")
        raw_status_title = str(raw_provider_status.get("statusTitle") or "")
        raw_is_live = bool(raw_provider_status.get("isLive"))

    status_candidates = [
        match.get("status"),
        match.get("status_title"),
        match.get("time_elapsed"),
        match.get("live_badge"),
        raw_status_title,
    ]
    normalized_candidates = {
        str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        for value in status_candidates
        if value is not None and value != ""
    }

    if (
        is_true_like(match.get("finished"))
        or normalized_candidates.intersection({"finished", "ft", "complete", "completed", "full_time"})
        or str(raw_status_value) == "7"
        or "\u0646\u062a\u06cc\u062c\u0647 \u0646\u0647\u0627\u06cc\u06cc" in raw_status_title
    ):
        return {
            "status": "finished",
            "is_finished": True,
            "is_live": False,
            "is_upcoming": False,
        }

    if (
        raw_is_live
        or normalized_candidates.intersection({"live", "in_progress", "ongoing", "1h", "2h", "ht", "et"})
    ):
        return {
            "status": "live",
            "is_finished": False,
            "is_live": True,
            "is_upcoming": False,
        }

    return {
        "status": "upcoming",
        "is_finished": False,
        "is_live": False,
        "is_upcoming": True,
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
        "normalized_type": normalized_type,
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


def normalize_match(match):
    if not isinstance(match, dict):
        return None

    match_id = first_value(match, ("id", "internal_match_id", "match_id", "matchId"))
    normalized_match_id = coerce_int(match_id)
    status_info = normalize_match_status(match)
    status = status_info["status"]
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = first_value(match, ("home_score", "homeScore"))
    away_score = first_value(match, ("away_score", "awayScore"))

    if home_score is None:
        home_score = score.get("home")

    if away_score is None:
        away_score = score.get("away")

    home_flag = match.get("home_flag") or match.get("home_team_flag") or ""
    away_flag = match.get("away_flag") or match.get("away_team_flag") or ""
    kickoff_utc = parse_match_datetime(match)
    kickoff_tehran = kickoff_utc.astimezone(TEHRAN_TZ) if kickoff_utc else None
    kickoff_iso = kickoff_tehran.isoformat() if kickoff_tehran else ""
    kickoff_utc_iso = kickoff_utc.isoformat().replace("+00:00", "Z") if kickoff_utc else ""
    date_label_fa = match.get("date_label_fa") or format_date_label_fa(
        kickoff_utc,
        match.get("date_iran") or match.get("persian_date") or "",
    )
    weekday_fa = match.get("weekday_fa") or format_weekday_fa(kickoff_utc)
    date_key = kickoff_date_key(kickoff_utc)

    return {
        **match,
        "id": normalized_match_id if normalized_match_id is not None else match_id,
        "internal_match_id": match.get("internal_match_id") or match_id,
        "external_match_id": match.get("external_match_id") or match.get("raw_provider_match_id"),
        "provider": match.get("provider") or "worldcup2026",
        "home_en": match.get("home_en") or match.get("home_team_name_en") or match.get("home_team") or "",
        "away_en": match.get("away_en") or match.get("away_team_name_en") or match.get("away_team") or "",
        "home_fa": match.get("home_fa") or match.get("home_team_name_fa") or "",
        "away_fa": match.get("away_fa") or match.get("away_team_name_fa") or "",
        "home_flag_url": home_flag,
        "away_flag_url": away_flag,
        "home_flag": flag_emoji(home_flag),
        "away_flag": flag_emoji(away_flag),
        "home_team": match.get("home_en") or match.get("home_team_name_en") or match.get("home_team") or "",
        "away_team": match.get("away_en") or match.get("away_team_name_en") or match.get("away_team") or "",
        "home_score": coerce_int(home_score),
        "away_score": coerce_int(away_score),
        "score": {
            "home": coerce_int(home_score),
            "away": coerce_int(away_score),
        },
        "status": status,
        "is_finished": status_info["is_finished"],
        "is_live": status_info["is_live"],
        "is_upcoming": status_info["is_upcoming"],
        "live_badge": status == "live",
        "raw_live_badge": match.get("live_badge"),
        "events": normalize_events(match.get("events") or []),
        "score_source": "worldcup_wrapper",
        "kickoff": kickoff_iso or match.get("kickoff") or match.get("kickoff_utc") or "",
        "kickoff_utc": kickoff_utc_iso or match.get("kickoff_utc") or match.get("kickoff") or "",
        "kickoff_iso": kickoff_iso,
        "kickoff_ts": int(kickoff_utc.timestamp()) if kickoff_utc else None,
        "kickoff_timestamp": int(kickoff_utc.timestamp()) if kickoff_utc else None,
        "date_key": date_key,
        "date": match.get("date") or "",
        "local_date": match.get("local_date") or match.get("localDate") or "",
        "source_timezone": source_timezone_for_match(match).key,
        "stadium_id": match.get("stadium_id") or match.get("stadiumId") or "",
        "date_iran": date_label_fa,
        "date_label_fa": date_label_fa,
        "weekday_fa": weekday_fa,
        "time_iran": format_tehran_time(kickoff_utc) or match.get("time_iran") or "",
        "datetime_iran": match.get("datetime_iran") or "",
        "group": match.get("group") or "",
        "stage": match.get("stage") or "",
        "stage_label": match.get("stage_label") or match.get("stage") or "",
        "stadium": match.get("stadium") or match.get("stadium_name_en") or "",
        "city": match.get("city") or match.get("stadium_city_en") or "",
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
    payload = fetch_json("/get/games")
    matches = []
    games = payload_list(payload, ("games", "matches", "data", "results", "items"))

    if not games:
        payload = fetch_json("/matches")
        games = payload_list(payload, ("matches", "games", "data", "results", "items"))

    teams_payload = fetch_json("/get/teams")
    stadiums_payload = fetch_json("/get/stadiums")
    team_lookup = build_lookup(payload_list(teams_payload, ("teams", "data", "results", "items")))
    stadium_lookup = build_lookup(payload_list(stadiums_payload, ("stadiums", "data", "results", "items")))

    for match in games:
        normalized_match = normalize_match(enrich_game(match, team_lookup, stadium_lookup))

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
    normalized = str(value or "").strip()

    if not normalized or normalized.lower() == "null":
        return []

    normalized = normalized.strip("{}[]")
    return [item.strip().strip('"').strip("'") for item in normalized.split(",") if item.strip()]


def events_from_scorers(game):
    events = []

    for side, key in (("home", "home_scorers"), ("away", "away_scorers")):
        for index, scorer in enumerate(parse_scorer_list(game.get(key)), start=1):
            events.append(
                {
                    "id": f"{game.get('id')}-{side}-goal-{index}",
                    "minute": None,
                    "type": "goal",
                    "normalized_type": "goal",
                    "team": side,
                    "team_side": side,
                    "player": scorer,
                    "scorer": scorer,
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

    return match.get("external_match_id") or match.get("id") or match_id, match


def fetch_single_game(match_id):
    payload = fetch_json(f"/get/game/{match_id}")

    if isinstance(payload, dict) and isinstance(payload.get("game"), dict):
        return payload["game"], payload

    return None, payload


def fetch_events_from_wrapper(match_id, metadata_match=None):
    local_match_id = metadata_match.get("id") if metadata_match else match_id
    event_path = f"/match/{local_match_id}/events"
    payload = fetch_json(event_path)
    raw_events = raw_events_from_payload(payload)
    events = normalize_events(raw_events)

    if events:
        return events

    live_path = f"/match/{local_match_id}/live"
    live_payload = fetch_json(live_path)
    live_raw_events = raw_events_from_payload(live_payload)
    live_events = normalize_events(live_raw_events)

    if live_events:
        return live_events

    game, game_payload = fetch_single_game(local_match_id)
    scorer_events = events_from_scorers(game or metadata_match or {})

    if scorer_events:
        return normalize_events(scorer_events)

    warn(
        "Events empty: "
        f"internal_match_id={local_match_id}, "
        f"external_match_id={metadata_match.get('external_match_id') if metadata_match else ''}, "
        f"provider={metadata_match.get('provider') if metadata_match else ''}, "
        f"event_endpoint={build_url(event_path)}, "
        f"event_response={payload_debug_summary(payload)}, "
        f"live_endpoint={build_url(live_path)}, "
        f"live_response={payload_debug_summary(live_payload)}, "
        f"game_endpoint={build_url(f'/get/game/{local_match_id}')}, "
        f"game_response={payload_debug_summary(game_payload)}"
    )

    return []


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

    external_match_id, metadata_match = external_match_id_for(normalized_match_id)
    events = fetch_events_from_wrapper(normalized_match_id, metadata_match)

    with _cache_lock:
        _cache["events"][normalized_match_id] = events

    return {
        "match_id": normalized_match_id,
        "external_match_id": external_match_id,
        "provider": metadata_match.get("provider") if metadata_match else None,
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
