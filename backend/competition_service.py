VALID_COMPETITION_FORMATS = frozenset({
    "league",
    "group_knockout",
    "knockout_only",
})


COMPETITIONS = [
    {
        "competition_key": "worldcup2026",
        "season_key": "2026",
        "name_fa": "جام جهانی ۲۰۲۶",
        "name_en": "World Cup 2026",
        "type": "international",
        "format": "group_knockout",
        "status": "archived",
        "is_active": True,
        "supports_matches": True,
        "supports_groups": True,
        "supports_knockout": True,
        "supports_standings": False,
        "supports_predictions": True,
        "supports_archive": True,
        "default_tab": "archive",
    },
    {
        "competition_key": "premier_league",
        "season_key": "2026-2027",
        "name_fa": "لیگ برتر انگلیس",
        "name_en": "Premier League",
        "type": "club",
        "format": "league",
        "status": "active",
        "is_active": True,
        "supports_matches": True,
        "supports_groups": False,
        "supports_knockout": False,
        "supports_standings": True,
        "supports_predictions": False,
        "supports_archive": False,
    },
]


def validated_competition(competition):
    competition_format = competition.get("format")
    if competition_format not in VALID_COMPETITION_FORMATS:
        competition_key = competition.get("competition_key", "<missing>")
        raise ValueError(
            f"Invalid competition format for {competition_key!r}: {competition_format!r}"
        )

    return competition.copy()


def get_competitions():
    return [validated_competition(competition) for competition in COMPETITIONS]


def get_competition(competition_key):
    normalized_key = str(competition_key or "").strip().lower()
    for competition in COMPETITIONS:
        if competition["competition_key"].lower() == normalized_key:
            return validated_competition(competition)

    return None
