from datetime import datetime, timezone


OVERVIEW_UPCOMING_LIMIT = 5
OVERVIEW_FINISHED_LIMIT = 5


def _kickoff_timestamp(match):
    value = match.get("kickoff_utc") if isinstance(match, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        kickoff = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if kickoff.tzinfo is None or kickoff.utcoffset() is None:
        return None
    return kickoff.astimezone(timezone.utc).timestamp()


def _match_id(match):
    value = match.get("id") if isinstance(match, dict) else None
    return str(value or "").strip()


def _status(match):
    return str(match.get("status") or "").strip().lower()


def select_overview_matches(
    matches,
    upcoming_limit=OVERVIEW_UPCOMING_LIMIT,
    finished_limit=OVERVIEW_FINISHED_LIMIT,
):
    if not isinstance(matches, list):
        return []

    live = []
    upcoming = []
    finished = []
    seen_match_ids = set()

    for match in matches:
        match_id = _match_id(match)
        if not match_id or match_id in seen_match_ids:
            continue
        seen_match_ids.add(match_id)

        status = _status(match)
        kickoff = _kickoff_timestamp(match)
        is_live = match.get("is_live") is True or status == "live"
        is_finished = match.get("is_finished") is True or status == "finished"

        if is_live and not is_finished:
            live.append((kickoff, match_id, match))
        elif is_finished and kickoff is not None:
            finished.append((kickoff, match_id, match))
        elif status == "upcoming" and kickoff is not None:
            upcoming.append((kickoff, match_id, match))

    live.sort(key=lambda item: (item[0] is None, item[0] or 0, item[1]))
    upcoming.sort(key=lambda item: (item[0], item[1]))
    finished.sort(key=lambda item: (-item[0], item[1]))

    return [
        *(item[2] for item in live),
        *(item[2] for item in upcoming[:upcoming_limit]),
        *(item[2] for item in finished[:finished_limit]),
    ]
