from services.worldcup_adapter import (
    get_match_events_from_worldcup_wrapper,
    get_matches_from_worldcup_wrapper,
    get_teams_from_worldcup_wrapper,
)


def normalized_status(status):
    return status if status in {"live", "upcoming", "finished"} else "upcoming"


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


def get_real_matches(status="all"):
    matches = []

    for match in get_matches_from_worldcup_wrapper():
        item = dict(match)
        item["status"] = normalized_status(item.get("status"))
        item["live_badge"] = item["status"] == "live"

        if status_matches_filter(status, item["status"]):
            matches.append(item)

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
