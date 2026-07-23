COMPETITIONS = [
    {
        "competition_key": "worldcup2026",
        "season_key": "2026",
        "name_fa": "جام جهانی ۲۰۲۶",
        "name_en": "World Cup 2026",
        "type": "international",
        "status": "archived",
        "is_active": True,
        "supports_matches": True,
        "supports_standings": False,
        "supports_predictions": True,
        "supports_archive": True,
        "default_tab": "archive",
    },
]


def get_competitions():
    return [competition.copy() for competition in COMPETITIONS]


def get_competition(competition_key):
    normalized_key = str(competition_key or "").strip().lower()
    for competition in COMPETITIONS:
        if competition["competition_key"].lower() == normalized_key:
            return competition.copy()

    return None
