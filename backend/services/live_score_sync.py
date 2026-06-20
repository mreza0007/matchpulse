import re
import unicodedata
from datetime import datetime, timedelta, timezone

from db_service import save_match_score_override_to_db
from real_data_service import get_all_cached_matches
from services import football_api

LIVE_STATUSES = {"IN_PLAY", "LIVE", "PAUSED"}
PERSIST_STATUSES = LIVE_STATUSES | {"FINISHED"}
MAX_KICKOFF_DELTA_SECONDS = 12 * 60 * 60

TEAM_ALIASES = {
    "czech republic": "czechia",
    "czechia": "czechia",
    "korea republic": "south korea",
    "south korea": "south korea",
    "usa": "united states",
    "united states of america": "united states",
    "united states": "united states",
    "turkey": "turkiye",
    "turkiye": "turkiye",
    "türkiye": "turkiye",
    "cote d ivoire": "cote divoire",
    "cote divoire": "cote divoire",
    "côte d’ivoire": "cote divoire",
    "côte d'ivoire": "cote divoire",
    "ivory coast": "cote divoire",
    "cape verde": "cabo verde",
    "cabo verde": "cabo verde",
    "bosnia herzegovina": "bosnia and herzegovina",
    "bosnia and herzegovina": "bosnia and herzegovina",
    "dr congo": "congo dr",
    "congo dr": "congo dr",
    "ir iran": "ir iran",
    "iran": "ir iran",
}


def normalize_team_name(name):
    if not name:
        return ""

    normalized = unicodedata.normalize("NFKD", str(name))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    normalized = re.sub(r"\s+", " ", normalized)

    return TEAM_ALIASES.get(normalized, normalized)


def parse_external_date(match):
    utc_date = match.get("utcDate")

    if not utc_date:
        return None


def parse_external_datetime(match):
    utc_date = match.get("utcDate")

    if not utc_date:
        return None

    try:
        return datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_static_datetime(match):
    kickoff = match.get("kickoff")

    if not kickoff:
        return None

    try:
        return datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    except ValueError:
        return None

    try:
        return datetime.fromisoformat(utc_date.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def get_team_name(match, side):
    team = match.get(f"{side}Team") or {}
    return team.get("name") or team.get("shortName") or team.get("tla") or ""


def get_score_value(score, side):
    for period in ("fullTime", "regularTime", "halfTime"):
        period_score = score.get(period) or {}
        value = period_score.get(side)

        if value is not None:
            return value

    return None


def get_full_time_scores(match):
    full_time = (match.get("score") or {}).get("fullTime") or {}

    return (
        full_time.get("home"),
        full_time.get("away"),
    )


def get_scores(match):
    score = match.get("score") or {}

    return (
        get_score_value(score, "home"),
        get_score_value(score, "away"),
    )


def get_static_match_lookup():
    matches = []

    for match in get_all_cached_matches():
        matches.append(
            {
                "match": match,
                "home": normalize_team_name(match.get("home_en")),
                "away": normalize_team_name(match.get("away_en")),
                "kickoff": parse_static_datetime(match),
            }
        )

    return matches


def kickoff_is_close(static_match, external_dt):
    static_dt = static_match.get("kickoff")

    if static_dt is None or external_dt is None:
        return False

    delta = abs((static_dt - external_dt).total_seconds())
    return delta <= MAX_KICKOFF_DELTA_SECONDS


def find_static_match(external_match, static_matches):
    external_home = normalize_team_name(get_team_name(external_match, "home"))
    external_away = normalize_team_name(get_team_name(external_match, "away"))
    external_dt = parse_external_datetime(external_match)

    for static_match in static_matches:
        if static_match["home"] != external_home:
            continue

        if static_match["away"] != external_away:
            continue

        if kickoff_is_close(static_match, external_dt):
            return static_match["match"], False

    for static_match in static_matches:
        if static_match["home"] != external_away:
            continue

        if static_match["away"] != external_home:
            continue

        if kickoff_is_close(static_match, external_dt):
            return static_match["match"], True

    return None, False


def build_result(static_match, home_score, away_score):
    if home_score is None or away_score is None:
        return None

    return (
        f"{static_match['home_en']} {home_score} - "
        f"{away_score} {static_match['away_en']}"
    )


def sync_live_scores():
    summary = {
        "ok": True,
        "fetched": 0,
        "world_cup": 0,
        "matched": 0,
        "updated": 0,
        "skipped": 0,
        "unmatched": [],
    }

    if not football_api.is_configured():
        return {
            "ok": False,
            "fetched": 0,
            "world_cup": 0,
            "matched": 0,
            "updated": 0,
            "skipped": True,
            "message": "FOOTBALL_API_TOKEN is not configured",
            "unmatched": [],
        }

    today = datetime.now(timezone.utc).date()
    date_from = (today - timedelta(days=3)).isoformat()
    date_to = (today + timedelta(days=1)).isoformat()

    try:
        payload = football_api.get_matches(date_from, date_to)
        external_matches = payload.get("matches") or []
        static_matches = get_static_match_lookup()
    except Exception as error:
        summary["ok"] = False
        print(f"[LIVE_SCORE_SYNC_ERROR] Failed before sync: {error}")
        return summary

    if payload.get("ok") is False:
        summary["ok"] = False
        summary["message"] = payload.get("message", "football-data.org request failed")
        summary["skipped"] = len(external_matches)
        return summary

    world_cup_matches = [
        match
        for match in external_matches
        if (match.get("competition") or {}).get("code") == "WC"
    ]

    summary["fetched"] = len(external_matches)
    summary["world_cup"] = len(world_cup_matches)

    for external_match in world_cup_matches:
        status = external_match.get("status")

        if status not in PERSIST_STATUSES:
            summary["skipped"] += 1
            continue

        if parse_external_datetime(external_match) is None:
            summary["skipped"] += 1
            continue

        static_match, reversed_match = find_static_match(external_match, static_matches)

        if static_match is None:
            summary["unmatched"].append(
                {
                    "external_match_id": external_match.get("id"),
                    "home": get_team_name(external_match, "home"),
                    "away": get_team_name(external_match, "away"),
                    "utcDate": external_match.get("utcDate"),
                    "status": status,
                }
            )
            summary["skipped"] += 1
            continue

        if reversed_match:
            print(
                "[LIVE_SCORE_SYNC_WARNING] Reversed home/away match used "
                f"external_id={external_match.get('id')} "
                f"home={get_team_name(external_match, 'home')} "
                f"away={get_team_name(external_match, 'away')}"
            )

        summary["matched"] += 1

        if status == "FINISHED":
            home_score, away_score = get_full_time_scores(external_match)
        else:
            home_score, away_score = get_scores(external_match)

        if reversed_match:
            home_score, away_score = away_score, home_score

        if home_score is None or away_score is None:
            summary["skipped"] += 1
            continue

        override = {
            "match_id": static_match["id"],
            "external_match_id": external_match.get("id"),
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "result": build_result(static_match, home_score, away_score),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "source": "football-data.org",
        }

        try:
            save_match_score_override_to_db(override)
            summary["updated"] += 1
        except Exception as error:
            summary["ok"] = False
            print(
                "[LIVE_SCORE_SYNC_ERROR] "
                f"Failed to save match {static_match['id']}: {error}"
            )

    print(
        "[LIVE_SCORE_SYNC] "
        f"fetched={summary['fetched']} "
        f"world_cup={summary['world_cup']} "
        f"matched={summary['matched']} "
        f"updated={summary['updated']} "
        f"skipped={summary['skipped']}"
    )

    if summary["unmatched"]:
        print(f"[LIVE_SCORE_SYNC_UNMATCHED] {summary['unmatched']}")

    return summary
