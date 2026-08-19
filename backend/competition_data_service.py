from functools import partial

from real_data_service import get_real_matches, get_real_teams, get_worldcup_knockout_rounds
from season_service import get_default_season
from services.worldcup_adapter import (
    WorldCupGroupsProviderError,
    WorldCupKnockoutProviderError,
    WorldCupKnockoutUnavailableError,
    get_groups_from_worldcup_wrapper,
)
from services.generic_football_adapter import (
    GenericFootballProviderError,
    GenericStandingsUnavailableError,
    get_match_events as get_generic_match_events,
    get_match_live as get_generic_match_live,
    get_season_matches as get_generic_season_matches,
    get_season_standings as get_generic_season_standings,
    get_season_teams as get_generic_season_teams,
)


class CompetitionDataProviderError(RuntimeError):
    pass


class CompetitionStandingsUnavailableError(RuntimeError):
    pass


class CompetitionGroupsProviderError(RuntimeError):
    pass


class CompetitionKnockoutProviderError(RuntimeError):
    pass


class CompetitionKnockoutUnavailableError(RuntimeError):
    pass


def normalize_competition_key(value):
    return str(value or "").strip().lower()


def normalize_season_key(value):
    return str(value or "").strip().lower()


COMPETITION_DATA_PROVIDERS = {
    "worldcup2026": {
        "seasons": {
            "2026": {
                "groups": get_groups_from_worldcup_wrapper,
                "knockout": get_worldcup_knockout_rounds,
                "matches": get_real_matches,
                "teams": get_real_teams,
            },
        },
    },
    "premier_league": {
        "seasons": {
            "2026-2027": {
                "matches": partial(get_generic_season_matches, "premier_league", "2026-2027"),
                "standings": partial(get_generic_season_standings, "premier_league", "2026-2027"),
                "teams": partial(get_generic_season_teams, "premier_league", "2026-2027"),
                "live": get_generic_match_live,
                "events": get_generic_match_events,
            },
        },
    },
}


def get_season_provider(competition_key, season_key):
    provider = COMPETITION_DATA_PROVIDERS.get(normalize_competition_key(competition_key))
    if not provider:
        return None

    seasons = provider.get("seasons") or {}
    return seasons.get(normalize_season_key(season_key))


def get_matches_for_competition(competition_key, status="all"):
    default_season = get_default_season(competition_key)
    if not default_season:
        return None

    return get_matches_for_season(competition_key, default_season["season_key"], status=status)


def get_matches_for_season(competition_key, season_key, status="all"):
    season_provider = get_season_provider(competition_key, season_key)
    if not season_provider or not season_provider.get("matches"):
        return None

    return season_provider["matches"](status=status)


def get_match_for_season(competition_key, season_key, match_id):
    try:
        matches = get_matches_for_season(competition_key, season_key, status="all")
    except CompetitionDataProviderError:
        raise
    except Exception as error:
        raise CompetitionDataProviderError() from error

    if matches is None:
        return None

    requested_match_id = str(match_id)
    return next(
        (
            match
            for match in matches
            if isinstance(match, dict) and str(match.get("id")) == requested_match_id
        ),
        None,
    )


def get_prediction_matches_for_season(competition_key, season_key):
    try:
        matches = get_matches_for_season(competition_key, season_key, status="all")
    except CompetitionDataProviderError:
        raise
    except Exception as error:
        raise CompetitionDataProviderError() from error

    if matches is None:
        raise CompetitionDataProviderError()
    return matches


def get_teams_for_competition(competition_key):
    default_season = get_default_season(competition_key)
    if not default_season:
        return None

    return get_teams_for_season(competition_key, default_season["season_key"])


def get_teams_for_season(competition_key, season_key):
    season_provider = get_season_provider(competition_key, season_key)
    if not season_provider or not season_provider.get("teams"):
        return None

    return season_provider["teams"]()


def get_standings_for_season(competition_key, season_key):
    season_provider = get_season_provider(competition_key, season_key)
    if not season_provider or not season_provider.get("standings"):
        return None

    try:
        return season_provider["standings"]()
    except GenericStandingsUnavailableError as error:
        raise CompetitionStandingsUnavailableError() from error
    except GenericFootballProviderError as error:
        raise CompetitionDataProviderError() from error


def get_groups_for_season(competition_key, season_key):
    season_provider = get_season_provider(competition_key, season_key)
    if not season_provider or not season_provider.get("groups"):
        return None

    try:
        return season_provider["groups"]()
    except WorldCupGroupsProviderError as error:
        raise CompetitionGroupsProviderError() from error


def get_knockout_for_season(competition_key, season_key):
    season_provider = get_season_provider(competition_key, season_key)
    if not season_provider or not season_provider.get("knockout"):
        return None

    try:
        return season_provider["knockout"]()
    except WorldCupKnockoutUnavailableError as error:
        raise CompetitionKnockoutUnavailableError() from error
    except WorldCupKnockoutProviderError as error:
        raise CompetitionKnockoutProviderError() from error


def get_match_live_for_season(competition_key, season_key, match_id):
    season_provider = get_season_provider(competition_key, season_key)
    if not season_provider or not season_provider.get("live"):
        return None

    return season_provider["live"](match_id)


def get_match_events_for_season(competition_key, season_key, match_id):
    season_provider = get_season_provider(competition_key, season_key)
    if not season_provider or not season_provider.get("events"):
        return None

    return season_provider["events"](match_id)
