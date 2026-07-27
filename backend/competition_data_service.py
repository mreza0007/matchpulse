from real_data_service import get_real_matches, get_real_teams


def normalize_competition_key(value):
    return str(value or "").strip().lower()


COMPETITION_DATA_PROVIDERS = {
    "worldcup2026": {
        "matches": get_real_matches,
        "teams": get_real_teams,
    },
}


def get_matches_for_competition(competition_key, status="all"):
    provider = COMPETITION_DATA_PROVIDERS.get(normalize_competition_key(competition_key))
    if not provider or not provider.get("matches"):
        return None

    return provider["matches"](status=status)


def get_teams_for_competition(competition_key):
    provider = COMPETITION_DATA_PROVIDERS.get(normalize_competition_key(competition_key))
    if not provider or not provider.get("teams"):
        return None

    return provider["teams"]()
