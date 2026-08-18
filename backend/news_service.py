VALID_NEWS_CATEGORIES = frozenset({"iran", "world", "national", "transfers"})


def filter_news(items, category=None, competition_key=None, team_id=None):
    if category is not None and category not in VALID_NEWS_CATEGORIES:
        raise ValueError("Invalid news category")

    filtered = list(items)

    if category is not None:
        filtered = [item for item in filtered if item.get("category") == category]

    if competition_key is not None:
        filtered = [
            item
            for item in filtered
            if competition_key in item.get("related_competition_keys", [])
        ]

    if team_id is not None:
        requested_team_id = str(team_id)
        filtered = [
            item
            for item in filtered
            if requested_team_id
            in {str(related_id) for related_id in item.get("related_team_ids", [])}
        ]

    return filtered
