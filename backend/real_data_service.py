from services.worldcup_adapter import (
    attach_visibility_flags,
    get_match_events_from_worldcup_wrapper,
    get_matches_from_worldcup_wrapper,
    get_teams_from_worldcup_wrapper,
    event_button_visibility,
    is_trusted_score_override,
    normalize_match_status,
    visible_match_result,
)
from db_service import get_all_match_score_overrides_from_db
import time


def normalized_status(status):
    return status if status in {"live", "upcoming", "finished", "pending_result"} else "upcoming"


def status_matches_filter(requested_status, match_status):
    if requested_status == "past":
        requested_status = "finished"

    if requested_status == "scheduled":
        requested_status = "upcoming"

    if requested_status == "all":
        return True

    return requested_status == match_status


def get_match_events(match_id):
    return get_match_events_from_worldcup_wrapper(match_id)


def is_finished_override(override):
    status = str(override.get("status") or "").strip().lower()
    return status in {"finished", "finish", "ft", "full_time", "fulltime", "completed", "complete"}


def kickoff_is_past(match):
    try:
        return float(match.get("kickoff_ts") or match.get("kickoff_timestamp")) < time.time()
    except (TypeError, ValueError):
        return False


def apply_score_override(item, override):
    if not is_trusted_score_override(override):
        return item

    home_score = override.get("home_score")
    away_score = override.get("away_score")

    if home_score is None or away_score is None:
        return item

    item["home_score"] = home_score
    item["away_score"] = away_score
    item["score"] = {
        "home": home_score,
        "away": away_score,
    }
    item["result"] = override.get("result") or item.get("result")
    item["score_source"] = override.get("source") or "score_override"
    item["result"] = visible_match_result(
        item,
        item.get("result"),
        item["score_source"],
        home_score,
        away_score,
    )

    current_status = normalize_match_status(item)
    if not current_status["is_live"] and (is_finished_override(override) or kickoff_is_past(item)):
        item["status"] = "finished"
        item["is_finished"] = True
        item["is_live"] = False
        item["is_upcoming"] = False
        item["live_badge"] = False

    return item


def get_real_matches(status="all"):
    matches = []
    all_matches = []
    score_overrides = get_all_match_score_overrides_from_db()

    for match in get_matches_from_worldcup_wrapper():
        item = dict(match)
        override = score_overrides.get(item.get("id"))
        if not is_trusted_score_override(override):
            override = None

        if override:
            item = apply_score_override(item, override)

        status_info = normalize_match_status(item)

        if item.get("needs_score_sync") and not override and not status_info["is_live"]:
            item["status"] = "pending_result"
            item["is_finished"] = False
            item["is_live"] = False
            item["is_upcoming"] = False
            item["live_badge"] = False
        else:
            item["status"] = normalized_status(status_info["status"])
            item["is_finished"] = status_info["is_finished"]
            item["is_live"] = status_info["is_live"]
            item["is_upcoming"] = status_info["is_upcoming"]
            item["live_badge"] = status_info.get("live_badge") or ("LIVE" if item["status"] == "live" else "")

        if override:
            item = apply_score_override(item, override)

        item = attach_visibility_flags(item)
        event_button, event_reason = event_button_visibility(item)
        teams = f"{item.get('home_en')} vs {item.get('away_en')}"
        print(
            "[RESULTS_AUDIT] "
            f"id={item.get('id')} teams={teams} status={item.get('status')} "
            f"score_source={item.get('score_source')} visible={item.get('can_show_in_results')} "
            f"event_button={event_button} external={item.get('external_match_id') or item.get('raw_provider_match_id') or ''}"
        )
        print(
            "[EVENT_BUTTON_AUDIT] "
            f"id={item.get('id')} teams={teams} can_show={event_button} reason={event_reason}"
        )

        all_matches.append(item)

        if status_matches_filter(status, item["status"]):
            matches.append(item)

    print(
        "[MATCHPULSE_MATCHES] "
        f"requested_status={status}, "
        f"total={len(all_matches)}, "
        f"finished={sum(1 for match in all_matches if match.get('is_finished') is True)}, "
        f"live={sum(1 for match in all_matches if match.get('is_live') is True)}, "
        f"upcoming={sum(1 for match in all_matches if match.get('is_upcoming') is True)}, "
        f"pending={sum(1 for match in all_matches if match.get('status') == 'pending_result')}, "
        f"returned={len(matches)}"
    )

    result_matches = [
        match
        for match in all_matches
        if match.get("is_finished") is True or match.get("status") == "pending_result"
    ]
    result_matches.sort(
        key=lambda match: float(match.get("kickoff_ts") or match.get("kickoff_timestamp") or 0),
        reverse=True,
    )

    if result_matches:
        first_result = result_matches[0]
        last_result = result_matches[-1]
        print(
            "[RESULTS_DEBUG] "
            f"first_result={first_result.get('home_en')} vs {first_result.get('away_en')}, "
            f"last_result={last_result.get('home_en')} vs {last_result.get('away_en')}, "
            f"count={len(result_matches)}"
        )

    return matches


def get_real_teams():
    teams = get_teams_from_worldcup_wrapper()

    if teams:
        return teams

    team_names = set()

    for match in get_real_matches(status="all"):
        home = match.get("home_en")
        away = match.get("away_en")

        if home:
            team_names.add(home)

        if away:
            team_names.add(away)

    return [
        {
            "id": index,
            "name_en": name,
            "name_fa": name,
            "emoji": "\u26bd",
        }
        for index, name in enumerate(sorted(team_names), start=1)
    ]
