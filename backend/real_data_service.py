import requests
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from db_service import get_all_match_score_overrides_from_db

FIXTURES_URL = "https://www.thestatsapi.com/world-cup/data/fixtures.json"

IRAN_TZ = ZoneInfo("Asia/Tehran")

_cached_raw_data = None
_cached_matches = None
_cached_teams = None

FLAGS = {
    "Mexico": "🇲🇽",
    "South Africa": "🇿🇦",
    "Korea Republic": "🇰🇷",
    "Czechia": "🇨🇿",
    "Canada": "🇨🇦",
    "Bosnia and Herzegovina": "🇧🇦",
    "United States": "🇺🇸",
    "Paraguay": "🇵🇾",
    "Haiti": "🇭🇹",
    "Scotland": "🏴",
    "Australia": "🇦🇺",
    "Turkiye": "🇹🇷",
    "Brazil": "🇧🇷",
    "Morocco": "🇲🇦",
    "Qatar": "🇶🇦",
    "Switzerland": "🇨🇭",
    "Cote d'Ivoire": "🇨🇮",
    "Ecuador": "🇪🇨",
    "Germany": "🇩🇪",
    "Curacao": "🇨🇼",
    "Netherlands": "🇳🇱",
    "Japan": "🇯🇵",
    "Sweden": "🇸🇪",
    "Tunisia": "🇹🇳",
    "Saudi Arabia": "🇸🇦",
    "Uruguay": "🇺🇾",
    "Spain": "🇪🇸",
    "Cabo Verde": "🇨🇻",
    "IR Iran": "🇮🇷",
    "New Zealand": "🇳🇿",
    "Belgium": "🇧🇪",
    "Egypt": "🇪🇬",
    "France": "🇫🇷",
    "Senegal": "🇸🇳",
    "Iraq": "🇮🇶",
    "Norway": "🇳🇴",
    "Argentina": "🇦🇷",
    "Algeria": "🇩🇿",
    "Austria": "🇦🇹",
    "Jordan": "🇯🇴",
    "Ghana": "🇬🇭",
    "Panama": "🇵🇦",
    "England": "🏴",
    "Croatia": "🇭🇷",
    "Portugal": "🇵🇹",
    "Congo DR": "🇨🇩",
    "Uzbekistan": "🇺🇿",
    "Colombia": "🇨🇴",
}

SCORE_FIELDS = {
    "home": (
        "home_score",
        "homeScore",
        "home_goals",
        "homeGoals",
        "home_team_score",
        "homeTeamScore",
        "score_home",
        "scoreHome",
    ),
    "away": (
        "away_score",
        "awayScore",
        "away_goals",
        "awayGoals",
        "away_team_score",
        "awayTeamScore",
        "score_away",
        "scoreAway",
    ),
}

COMPLETED_MATCH_RESULTS = {
    1: (2, 0),
    2: (2, 1),
    3: (1, 1),
    4: (4, 1),
    5: (0, 1),
    6: (2, 0),
    7: (1, 1),
    8: (1, 1),
    9: (1, 0),
    10: (7, 1),
    11: (2, 2),
    12: (5, 1),
    13: (1, 1),
    14: (0, 0),
    15: (2, 2),
    16: (1, 1),
    17: (3, 1),
    18: (1, 4),
    19: (3, 0),
    20: (3, 1),
    21: (1, 0),
    22: (4, 2),
    23: (1, 1),
    24: (1, 3),
    25: (1, 1),
}

LIVE_OVERRIDE_STATUSES = {"IN_PLAY", "LIVE", "PAUSED"}


def get_raw_worldcup_data():
    global _cached_raw_data

    if _cached_raw_data is not None:
        return _cached_raw_data

    response = requests.get(FIXTURES_URL, timeout=30)
    response.raise_for_status()

    _cached_raw_data = response.json()
    return _cached_raw_data


def parse_utc_datetime(kickoff):
    return datetime.fromisoformat(kickoff.replace("Z", "+00:00"))


def format_iran_datetime(kickoff):
    utc_dt = parse_utc_datetime(kickoff)
    iran_dt = utc_dt.astimezone(IRAN_TZ)

    return {
        "date_iran": iran_dt.strftime("%Y-%m-%d"),
        "time_iran": iran_dt.strftime("%H:%M"),
        "datetime_iran": iran_dt.strftime("%Y-%m-%d %H:%M"),
    }


def normalize_stage(stage):
    names = {
        "group-stage": "Group Stage",
        "round-of-32": "Round of 32",
        "round-of-16": "Round of 16",
        "quarter-finals": "Quarter-finals",
        "semi-finals": "Semi-finals",
        "third-place": "Third Place",
        "final": "Final",
    }

    return names.get(stage, stage)


def get_first_score_value(match, keys):
    for key in keys:
        value = match.get(key)

        if value is not None and value != "":
            return value

    return None


def parse_result_scores(result):
    if not result:
        return None

    result_text = str(result)
    match = re.search(r"(\d+)\s*[-–]\s*(\d+)", result_text)

    if match:
        return int(match.group(1)), int(match.group(2))

    match = re.search(r"\b(\d+)\s*,\s*[^,]+?\b(\d+)\b", result_text)

    if match:
        return int(match.group(1)), int(match.group(2))

    return None


def normalize_score_fields(item, status):
    home_score = get_first_score_value(item, SCORE_FIELDS["home"])
    away_score = get_first_score_value(item, SCORE_FIELDS["away"])

    if home_score is None or away_score is None:
        parsed_scores = parse_result_scores(item.get("result"))

        if parsed_scores is not None:
            home_score, away_score = parsed_scores

    if status == "past" and (home_score is None or away_score is None):
        mapped_scores = COMPLETED_MATCH_RESULTS.get(item.get("id"))

        if mapped_scores is not None:
            home_score, away_score = mapped_scores

    item["home_score"] = int(home_score) if home_score is not None else None
    item["away_score"] = int(away_score) if away_score is not None else None

    if item["home_score"] is not None and item["away_score"] is not None:
        item["result"] = (
            f"{item['home_en']} {item['home_score']} - "
            f"{item['away_score']} {item['away_en']}"
        )

    return item


def build_all_matches():
    data = get_raw_worldcup_data()

    matches = []

    for match in data["fixtures"]:
        kickoff_utc = parse_utc_datetime(match["kickoffUtc"])
        iran_time = format_iran_datetime(match["kickoffUtc"])

        matches.append(
            {
                "id": match["matchNumber"],
                "home_en": match["homeTeam"],
                "away_en": match["awayTeam"],
                "home_flag": FLAGS.get(match["homeTeam"], "⚽"),
                "away_flag": FLAGS.get(match["awayTeam"], "⚽"),
                "date": match["date"],
                "kickoff": match["kickoffUtc"],
                "kickoff_dt": kickoff_utc,
                "date_iran": iran_time["date_iran"],
                "time_iran": iran_time["time_iran"],
                "datetime_iran": iran_time["datetime_iran"],
                "group": match["group"],
                "stage": match["stage"],
                "stage_label": normalize_stage(match["stage"]),
                "stadium": match["stadium"],
                "city": match["hostCity"],
                "home_score": get_first_score_value(match, SCORE_FIELDS["home"]),
                "away_score": get_first_score_value(match, SCORE_FIELDS["away"]),
                "result": None,
            }
        )

    matches.sort(key=lambda item: item["kickoff"])

    return matches


def get_all_cached_matches():
    global _cached_matches

    if _cached_matches is None:
        _cached_matches = build_all_matches()

    return _cached_matches


def clean_match_for_json(match, status):
    item = dict(match)

    item.pop("kickoff_dt", None)

    item["status"] = status
    item = normalize_score_fields(item, status)

    if status == "live":
        item["live_badge"] = True

    if status != "past" and item.get("home_score") is None and item.get("away_score") is None:
        item["result"] = None

    if status == "past" and item.get("result") is None:
        item["result"] = "نتیجه هنوز ثبت نشده"

    return item


def get_score_overrides():
    try:
        return get_all_match_score_overrides_from_db()
    except Exception as error:
        print(f"[MATCH_SCORE_OVERRIDE_ERROR] Static matches used without overrides: {error}")
        return {}


def apply_score_override(match, override):
    if not override:
        return match

    item = dict(match)

    item["external_match_id"] = override.get("external_match_id")
    item["score_source"] = override.get("source")
    item["score_last_updated"] = override.get("last_updated")
    item["override_status"] = override.get("status")

    if override.get("home_score") is not None:
        item["home_score"] = override.get("home_score")

    if override.get("away_score") is not None:
        item["away_score"] = override.get("away_score")

    if override.get("result"):
        item["result"] = override.get("result")

    return item


def get_match_status(match, override, now_utc):
    override_status = (override or {}).get("status")

    if override_status == "FINISHED":
        return "past"

    if override_status in LIVE_OVERRIDE_STATUSES:
        return "live"

    return "past" if match["kickoff_dt"] < now_utc else "upcoming"


def status_matches_filter(requested_status, match_status):
    if requested_status == "all":
        return True

    if requested_status == "upcoming":
        return match_status in {"upcoming", "live"}

    return requested_status == match_status


def get_real_matches(status="all"):
    now_utc = datetime.now(timezone.utc)
    all_matches = get_all_cached_matches()
    overrides = get_score_overrides()

    matches = []

    for match in all_matches:
        override = overrides.get(match["id"])
        match_status = get_match_status(match, override, now_utc)

        if not status_matches_filter(status, match_status):
            continue

        match_with_override = apply_score_override(match, override)

        matches.append(clean_match_for_json(match_with_override, match_status))

    if status == "past":
        matches.sort(key=lambda item: item["kickoff"], reverse=True)
    else:
        matches.sort(key=lambda item: item["kickoff"])

    return matches


def get_real_teams():
    global _cached_teams

    if _cached_teams is not None:
        return _cached_teams

    matches = get_real_matches(status="all")
    team_names = set()

    for match in matches:
        home = match["home_en"]
        away = match["away_en"]

        if not home.startswith("Group ") and not home.startswith("Winner ") and not home.startswith("Loser "):
            team_names.add(home)

        if not away.startswith("Group ") and not away.startswith("Winner ") and not away.startswith("Loser "):
            team_names.add(away)

    teams = []

    for index, name in enumerate(sorted(team_names), start=1):
        teams.append(
            {
                "id": index,
                "name_en": name,
                "name_fa": name,
                "emoji": FLAGS.get(name, "⚽"),
            }
        )

    _cached_teams = teams
    return _cached_teams
