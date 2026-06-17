import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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

    if status == "past" and item.get("result") is None:
        item["result"] = "نتیجه هنوز ثبت نشده"

    return item


def get_real_matches(status="all"):
    now_utc = datetime.now(timezone.utc)
    all_matches = get_all_cached_matches()

    matches = []

    for match in all_matches:
        match_status = "past" if match["kickoff_dt"] < now_utc else "upcoming"

        if status != "all" and status != match_status:
            continue

        matches.append(clean_match_for_json(match, match_status))

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