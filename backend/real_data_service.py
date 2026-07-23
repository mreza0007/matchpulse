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


def match_score(match):
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = match.get("home_score")
    away_score = match.get("away_score")

    if home_score is None:
        home_score = score.get("home")

    if away_score is None:
        away_score = score.get("away")

    try:
        home_score = int(home_score)
        away_score = int(away_score)
    except (TypeError, ValueError):
        return None, None

    return home_score, away_score


def match_result_side(match):
    result = str(match.get("penalty_winner_side") or match.get("result") or "").strip().lower()
    if result in {"home", "away"}:
        return result

    home_score, away_score = match_score(match)
    if home_score is None or away_score is None:
        return ""
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def summary_team(match, side):
    return {
        "side": side,
        "name_fa": match.get(f"{side}_fa") or match.get(f"{side}_en") or "",
        "name_en": match.get(f"{side}_en") or match.get(f"{side}_fa") or "",
        "flag": match.get(f"{side}_flag") or "",
        "flag_url": match.get(f"{side}_flag_url") or "",
    }


def other_side(side):
    return "away" if side == "home" else "home"


def summary_match(match):
    if not match:
        return None

    home_score, away_score = match_score(match)
    return {
        "id": match.get("id"),
        "home_fa": match.get("home_fa") or match.get("home_en") or "",
        "home_en": match.get("home_en") or match.get("home_fa") or "",
        "away_fa": match.get("away_fa") or match.get("away_en") or "",
        "away_en": match.get("away_en") or match.get("away_fa") or "",
        "home_flag": match.get("home_flag") or "",
        "away_flag": match.get("away_flag") or "",
        "home_flag_url": match.get("home_flag_url") or "",
        "away_flag_url": match.get("away_flag_url") or "",
        "score": {
            "home": home_score,
            "away": away_score,
        },
        "home_score": home_score,
        "away_score": away_score,
        "result": match.get("result") or match_result_side(match),
        "home_penalty_score": match.get("home_penalty_score"),
        "away_penalty_score": match.get("away_penalty_score"),
        "penalty_winner_side": match.get("penalty_winner_side"),
        "penalty_winner_fa": match.get("penalty_winner_fa"),
        "penalty_winner_en": match.get("penalty_winner_en"),
        "penalty_summary_fa": match.get("penalty_summary_fa"),
        "penalty_summary_en": match.get("penalty_summary_en"),
        "win_method": match.get("win_method"),
    }


def summary_match_with_total(match):
    item = summary_match(match)
    if not item:
        return None

    home_score = item["score"]["home"]
    away_score = item["score"]["away"]
    item["total_goals"] = (home_score or 0) + (away_score or 0)
    return item


def summary_match_with_goal_diff(match):
    item = summary_match(match)
    if not item:
        return None

    home_score = item["score"]["home"]
    away_score = item["score"]["away"]
    item["goal_diff"] = abs((home_score or 0) - (away_score or 0))
    return item


def match_team_names(match, side):
    return {
        str(match.get(f"{side}_en") or "").strip().lower(),
        str(match.get(f"{side}_fa") or "").strip().lower(),
        str(match.get(f"{side}_team_label") or "").strip().lower(),
    }


def find_match_by_teams_and_score(matches, home_names, away_names, score):
    normalized_home_names = {str(name).strip().lower() for name in home_names if name}
    normalized_away_names = {str(name).strip().lower() for name in away_names if name}

    for match in matches:
        home_score, away_score = match_score(match)
        if (home_score, away_score) != score:
            continue

        home_match_names = match_team_names(match, "home")
        away_match_names = match_team_names(match, "away")
        if home_match_names & normalized_home_names and away_match_names & normalized_away_names:
            return match

    return None


def manual_best_win_summary():
    return {
        "id": "portugal-uzbekistan-best-win",
        "home_fa": "پرتغال",
        "home_en": "Portugal",
        "away_fa": "ازبکستان",
        "away_en": "Uzbekistan",
        "home_flag": "🇵🇹",
        "away_flag": "🇺🇿",
        "home_flag_url": "",
        "away_flag_url": "",
        "score": {
            "home": 5,
            "away": 0,
        },
        "home_score": 5,
        "away_score": 0,
        "result": "home",
        "goal_diff": 5,
    }


def team_lookup_from_matches(matches):
    lookup = {}
    for match in matches:
        for side in ("home", "away"):
            team = summary_team(match, side)
            for name in (team["name_en"], team["name_fa"]):
                if name:
                    lookup.setdefault(name.lower(), team)
    return lookup


def award_item(name, team_name, award_en, award_fa, team_lookup, **extra):
    team = team_lookup.get(str(team_name or "").lower(), {})
    return {
        "name": name,
        "name_en": name,
        "name_fa": extra.pop("name_fa", name),
        "team": team_name,
        "team_en": team.get("name_en") or team_name,
        "team_fa": extra.pop("team_fa", None) or team.get("name_fa") or team_name,
        "team_flag": team.get("flag") or "",
        "team_flag_url": team.get("flag_url") or "",
        "award_en": award_en,
        "award_fa": award_fa,
        **extra,
    }


def get_worldcup_summary():
    matches = get_real_matches(status="all")
    match_by_id = {int(match.get("id")): match for match in matches if str(match.get("id") or "").isdigit()}
    final_match = match_by_id.get(104)
    third_place_match = match_by_id.get(103)

    final_winner_side = match_result_side(final_match or {})
    third_winner_side = match_result_side(third_place_match or {})
    champion = summary_team(final_match, final_winner_side) if final_winner_side in {"home", "away"} else None
    runner_up = summary_team(final_match, other_side(final_winner_side)) if final_winner_side in {"home", "away"} else None
    third_place = summary_team(third_place_match, third_winner_side) if third_winner_side in {"home", "away"} else None
    fourth_place = summary_team(third_place_match, other_side(third_winner_side)) if third_winner_side in {"home", "away"} else None

    finished_matches = [
        match for match in matches
        if match.get("is_finished") is True or match.get("status") == "finished"
    ]
    scored_matches = [
        match for match in finished_matches
        if match_score(match)[0] is not None and match_score(match)[1] is not None
    ]
    highest_scoring_match = max(
        scored_matches,
        key=lambda match: sum(match_score(match)),
        default=None,
    )
    best_win_match = find_match_by_teams_and_score(
        scored_matches,
        {"Portugal", "پرتغال"},
        {"Uzbekistan", "ازبکستان"},
        (5, 0),
    )
    best_win = summary_match_with_goal_diff(best_win_match) if best_win_match else manual_best_win_summary()
    biggest_wins = [best_win]

    team_lookup = team_lookup_from_matches(matches)

    return {
        "competition_key": "worldcup2026",
        "title_fa": "جام جهانی ۲۰۲۶",
        "title_en": "World Cup 2026",
        "subtitle_fa": "خلاصه و افتخارات جام",
        "subtitle_en": "Tournament summary and honors",
        "podium": {
            "champion": champion,
            "runner_up": runner_up,
            "third_place": third_place,
            "fourth_place": fourth_place,
        },
        "final_match": summary_match(final_match),
        "third_place_match": summary_match(third_place_match),
        "awards": {
            "best_player": award_item(
                "Rodri",
                "Spain",
                "Golden Ball",
                "بهترین بازیکن جام",
                team_lookup,
                name_fa="رودری",
                team_fa="اسپانیا",
            ),
            "top_scorer": award_item(
                "Kylian Mbappé",
                "France",
                "Golden Boot",
                "آقای گل",
                team_lookup,
                name_fa="کیلیان امباپه",
                team_fa="فرانسه",
                goals=10,
                goals_label_fa="۱۰ گل",
            ),
            "top_assister": award_item(
                "Michael Olise",
                "France",
                "Top Assister / Creativity Leader",
                "پاسور برتر / صدرنشین خلاقیت",
                team_lookup,
                name_fa="مایکل اولیسه",
                team_fa="فرانسه",
                assists=5,
                assists_label_fa="۵ پاس گل",
            ),
            "best_goalkeeper": award_item(
                "Unai Simón",
                "Spain",
                "Golden Glove",
                "بهترین دروازه‌بان",
                team_lookup,
                name_fa="اونای سیمون",
                team_fa="اسپانیا",
            ),
            "best_young_player": award_item(
                "Pau Cubarsí",
                "Spain",
                "Young Player Award",
                "بهترین بازیکن جوان",
                team_lookup,
                name_fa="پائو کوبارسی",
                team_fa="اسپانیا",
            ),
        },
        "highlights": {
            "highest_scoring_match": summary_match_with_total(highest_scoring_match),
            "best_win": best_win,
            "biggest_wins": biggest_wins,
        },
        "data_notes": {
            "awards_source": "manual_seeded",
        },
    }


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
        for key in ("live_phase", "live_phase_fa", "live_phase_en", "live_display_fa", "live_display_en"):
            item[key] = ""

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
            for key in ("live_phase", "live_phase_fa", "live_phase_en", "live_display_fa", "live_display_en"):
                item[key] = ""
        else:
            item["status"] = normalized_status(status_info["status"])
            item["is_finished"] = status_info["is_finished"]
            item["is_live"] = status_info["is_live"]
            item["is_upcoming"] = status_info["is_upcoming"]
            item["live_badge"] = status_info.get("live_badge") or ("LIVE" if item["status"] == "live" else "")
            for key in ("live_phase", "live_phase_fa", "live_phase_en", "live_display_fa", "live_display_en"):
                item[key] = status_info.get(key) or ""

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
