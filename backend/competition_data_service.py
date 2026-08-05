from real_data_service import get_real_matches, get_real_teams
from season_service import get_default_season


def normalize_competition_key(value):
    return str(value or "").strip().lower()


def normalize_season_key(value):
    return str(value or "").strip().lower()


COMPETITION_DATA_PROVIDERS = {
    "worldcup2026": {
        "seasons": {
            "2026": {
                "matches": get_real_matches,
                "teams": get_real_teams,
            },
        },
    },
}


def get_matches_for_competition(competition_key, status="all"):
    default_season = get_default_season(competition_key)
    if not default_season:
        return None

    return get_matches_for_season(competition_key, default_season["season_key"], status=status)


def get_matches_for_season(competition_key, season_key, status="all"):
    provider = COMPETITION_DATA_PROVIDERS.get(normalize_competition_key(competition_key))
    if not provider:
        return None

    seasons = provider.get("seasons") or {}
    season_provider = seasons.get(normalize_season_key(season_key))
    if not season_provider or not season_provider.get("matches"):
        return None

    return season_provider["matches"](status=status)


def get_teams_for_competition(competition_key):
    default_season = get_default_season(competition_key)
    if not default_season:
        return None

    return get_teams_for_season(competition_key, default_season["season_key"])


def get_teams_for_season(competition_key, season_key):
    provider = COMPETITION_DATA_PROVIDERS.get(normalize_competition_key(competition_key))
    if not provider:
        return None

    seasons = provider.get("seasons") or {}
    season_provider = seasons.get(normalize_season_key(season_key))
    if not season_provider or not season_provider.get("teams"):
        return None

    return season_provider["teams"]()
