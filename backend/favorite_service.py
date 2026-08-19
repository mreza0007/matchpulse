from collections import defaultdict

from competition_data_service import CompetitionDataProviderError, get_teams_for_competition
from competition_service import get_competition


TEAM_TYPE_BY_COMPETITION_TYPE = {
    "club": "club",
    "international": "national",
}


class FavoriteTeamTypeError(RuntimeError):
    pass


def favorite_team_type(competition):
    team_type = TEAM_TYPE_BY_COMPETITION_TYPE.get(competition.get("type"))
    if not team_type:
        raise FavoriteTeamTypeError("Unsupported competition team type")
    return team_type


def favorite_response_item(identity, competition=None, team=None):
    team_id = str(identity["team_id"])
    item = {
        "competition_key": identity["competition_key"],
        "team_id": team_id,
        "id": team_id,
        "resolved": team is not None,
    }

    if competition is not None:
        try:
            item["team_type"] = favorite_team_type(competition)
        except FavoriteTeamTypeError:
            pass

    if team is None:
        return item

    if team.get("id") is not None:
        item["id"] = team["id"]

    name_en = team.get("name_en")
    name_fa = team.get("name_fa")
    if name_en not in (None, ""):
        item["team_name_en"] = name_en
        item["name_en"] = name_en
    if name_fa not in (None, ""):
        item["team_name_fa"] = name_fa
        item["name_fa"] = name_fa
    display_name = name_fa or name_en
    if display_name not in (None, ""):
        item["team_name"] = display_name

    logo = team.get("logo")
    if logo not in (None, ""):
        item["team_logo"] = logo
        item["logo"] = logo

    flag = team.get("flag")
    if flag not in (None, ""):
        item["team_flag"] = flag
        item["flag"] = flag
    flag_url = team.get("flag_url")
    if flag_url not in (None, ""):
        item["team_flag_url"] = flag_url
        item["flag_url"] = flag_url
    emoji = team.get("emoji") or flag
    if emoji not in (None, ""):
        item["emoji"] = emoji
    return item


def resolve_favorite_identities(identities):
    grouped_indexes = defaultdict(list)
    for index, identity in enumerate(identities):
        grouped_indexes[identity["competition_key"]].append(index)

    resolved_items = [None] * len(identities)
    resolution_errors = 0
    unresolved_count = 0

    for competition_key, indexes in grouped_indexes.items():
        competition = get_competition(competition_key)
        if competition is None:
            for index in indexes:
                resolved_items[index] = favorite_response_item(identities[index])
                unresolved_count += 1
            continue

        try:
            favorite_team_type(competition)
        except FavoriteTeamTypeError:
            for index in indexes:
                resolved_items[index] = favorite_response_item(
                    identities[index], competition=competition
                )
                unresolved_count += 1
            continue

        try:
            teams = get_teams_for_competition(competition_key)
        except CompetitionDataProviderError:
            teams = None
            resolution_errors += 1

        if teams is None:
            for index in indexes:
                resolved_items[index] = favorite_response_item(
                    identities[index], competition=competition
                )
                unresolved_count += 1
            continue

        teams_by_id = {
            str(team["id"]): team
            for team in teams
            if isinstance(team, dict) and team.get("id") is not None
        }
        for index in indexes:
            identity = identities[index]
            team = teams_by_id.get(str(identity["team_id"]))
            resolved_items[index] = favorite_response_item(
                identity, competition=competition, team=team
            )
            if team is None:
                unresolved_count += 1

    return {
        "favorite_teams": resolved_items,
        "resolution_errors": resolution_errors,
        "unresolved_count": unresolved_count,
    }
