SEASONS = [
    {
        "competition_key": "worldcup2026",
        "season_key": "2026",
        "name_fa": "جام جهانی ۲۰۲۶",
        "name_en": "World Cup 2026",
        "status": "archived",
        "is_default": True,
    },
    {
        "competition_key": "premier_league",
        "season_key": "2026-2027",
        "name_fa": "لیگ برتر انگلیس ۲۰۲۶-۲۰۲۷",
        "name_en": "Premier League 2026-2027",
        "status": "active",
        "is_default": True,
    },
]

SEASONS.extend([
    {
        "competition_key": "persian_gulf_pro_league",
        "season_key": "1405-1406",
        "name_fa": "لیگ برتر خلیج فارس ۱۴۰۵-۱۴۰۶",
        "name_en": "Persian Gulf Pro League 1405-1406",
        "status": "active",
        "is_default": True,
    },
    {
        "competition_key": "la_liga",
        "season_key": "2026-2027",
        "name_fa": "لالیگا ۲۰۲۶-۲۰۲۷",
        "name_en": "La Liga 2026-2027",
        "status": "active",
        "is_default": True,
    },
    {
        "competition_key": "serie_a",
        "season_key": "2026-2027",
        "name_fa": "سری آ ۲۰۲۶-۲۰۲۷",
        "name_en": "Serie A 2026-2027",
        "status": "active",
        "is_default": True,
    },
    {
        "competition_key": "bundesliga",
        "season_key": "2026-2027",
        "name_fa": "بوندس‌لیگا ۲۰۲۶-۲۰۲۷",
        "name_en": "Bundesliga 2026-2027",
        "status": "active",
        "is_default": True,
    },
    {
        "competition_key": "ligue_1",
        "season_key": "2026-2027",
        "name_fa": "لیگ ۱ فرانسه ۲۰۲۶-۲۰۲۷",
        "name_en": "Ligue 1 2026-2027",
        "status": "active",
        "is_default": True,
    },
    {
        "competition_key": "champions_league",
        "season_key": "2026-2027",
        "name_fa": "لیگ قهرمانان اروپا ۲۰۲۶-۲۰۲۷",
        "name_en": "UEFA Champions League 2026-2027",
        "status": "active",
        "is_default": True,
    },
    {
        "competition_key": "europa_league",
        "season_key": "2026-2027",
        "name_fa": "لیگ اروپا ۲۰۲۶-۲۰۲۷",
        "name_en": "UEFA Europa League 2026-2027",
        "status": "active",
        "is_default": True,
    },
])


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


def get_default_season(competition_key):
    normalized_competition_key = normalize_key(competition_key)

    for season in SEASONS:
        if (
            normalize_key(season.get("competition_key")) == normalized_competition_key
            and season.get("is_default") is True
        ):
            return season.copy()

    return None
