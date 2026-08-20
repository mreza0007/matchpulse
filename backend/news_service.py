VALID_NEWS_CATEGORIES = frozenset({"iran", "world", "national", "transfers"})


def filter_news(items, category=None, competition_key=None, team_id=None):
    if category is not None and category not in VALID_NEWS_CATEGORIES:
        raise ValueError("Invalid news category")
    if team_id is not None and competition_key is None:
        raise ValueError("competition_key is required with team_id")

    filtered = list(items)

    if category is not None:
        filtered = [item for item in filtered if item.get("category") == category]

    if competition_key is not None and team_id is None:
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
            if any(
                isinstance(relation, dict)
                and relation.get("competition_key") == competition_key
                and relation.get("team_id") is not None
                and str(relation["team_id"]) == requested_team_id
                for relation in item.get("related_teams", [])
            )
        ]

    return filtered


def filter_news_for_favorites(items, favorite_identities, category=None):
    filtered = filter_news(items, category=category)
    favorite_keys = {
        (identity.get("competition_key"), str(identity["team_id"]))
        for identity in favorite_identities
        if isinstance(identity, dict)
        and identity.get("competition_key") is not None
        and identity.get("team_id") is not None
    }
    if not favorite_keys:
        return []

    matched = []
    seen_ids = set()
    for item in filtered:
        item_id = item.get("id")
        if item_id in seen_ids:
            continue
        relations = item.get("related_teams", [])
        is_related = any(
            isinstance(relation, dict)
            and relation.get("competition_key") is not None
            and relation.get("team_id") is not None
            and (relation["competition_key"], str(relation["team_id"]))
            in favorite_keys
            for relation in relations
        )
        if is_related:
            matched.append(item)
            seen_ids.add(item_id)
    return matched
