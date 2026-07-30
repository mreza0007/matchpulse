SEASONS = [
    {
        "competition_key": "worldcup2026",
        "season_key": "2026",
        "name_fa": "جام جهانی ۲۰۲۶",
        "name_en": "World Cup 2026",
        "status": "archived",
        "is_default": True,
    },
]


def normalize_key(value):
    return str(value or "").strip().lower()


def get_seasons(competition_key):
    normalized_competition_key = normalize_key(competition_key)
    return [
        season.copy()
        for season in SEASONS
        if normalize_key(season.get("competition_key")) == normalized_competition_key
    ]


def get_season(competition_key, season_key):
    normalized_competition_key = normalize_key(competition_key)
    normalized_season_key = normalize_key(season_key)

    for season in SEASONS:
        if (
            normalize_key(season.get("competition_key")) == normalized_competition_key
            and normalize_key(season.get("season_key")) == normalized_season_key
        ):
            return season.copy()

    return None
