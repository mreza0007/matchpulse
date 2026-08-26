import re
import time

from prediction_service import prediction_is_predictable, trusted_prediction_kickoff


LEAGUE_NEXT_ROUND = "league_next_round"
KNOCKOUT_NEXT_STAGE = "knockout_next_stage"
VALID_PREDICTION_SCOPES = frozenset({LEAGUE_NEXT_ROUND, KNOCKOUT_NEXT_STAGE})

PERSIAN_AND_ARABIC_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
LEAGUE_ROUND_PATTERN = re.compile(
    r"^(?:(?:week|matchweek|round|هفته)\s*[:._-]?\s*)?(\d+)$",
    re.IGNORECASE,
)


def normalized_scope_token(value):
    if value is None or isinstance(value, bool):
        return None
    text = str(value).translate(PERSIAN_AND_ARABIC_DIGITS).strip().casefold()
    text = " ".join(text.split())
    return text or None


def league_round_number(match):
    if not isinstance(match, dict):
        return None
    for value in (match.get("round"), match.get("stage")):
        token = normalized_scope_token(value)
        if token is None:
            continue
        match_result = LEAGUE_ROUND_PATTERN.fullmatch(token)
        if match_result:
            return int(match_result.group(1))
    return None


def provider_stage_token(match):
    if not isinstance(match, dict):
        return None
    for value in (match.get("stage"), match.get("round")):
        token = normalized_scope_token(value)
        if token is not None:
            return token
    return None


def normalized_status(match):
    return re.sub(
        r"[-\s]+",
        "_",
        str(match.get("status") or "").strip().casefold(),
    )


def match_is_upcoming(match):
    return (
        isinstance(match, dict)
        and match.get("is_upcoming") is True
        and normalized_status(match) == "upcoming"
        and match.get("is_live") is not True
        and match.get("is_finished") is not True
    )


def match_has_started(match, now_timestamp):
    if not isinstance(match, dict):
        return False
    if match.get("is_live") is True or match.get("is_finished") is True:
        return True
    if normalized_status(match) in {"live", "finished"}:
        return True
    kickoff = trusted_prediction_kickoff(match)
    return kickoff is not None and kickoff <= now_timestamp


def choose_scheduled_token(groups, now_timestamp):
    ranked = []
    for token, items in groups.items():
        future_kickoffs = [
            kickoff
            for _, match in items
            if (kickoff := trusted_prediction_kickoff(match)) is not None
            and kickoff > now_timestamp
        ]
        first_index = items[0][0]
        if future_kickoffs:
            ranked.append((0, min(future_kickoffs), first_index, token))
        else:
            ranked.append((1, float("inf"), first_index, token))
    return min(ranked)[-1] if ranked else None


def select_league_round(matches, now_timestamp):
    matches_by_round = {}
    for match in matches:
        round_number = league_round_number(match)
        if round_number is not None:
            matches_by_round.setdefault(round_number, []).append(match)

    progression_round = None
    for round_number in sorted(matches_by_round):
        if not any(match_has_started(match, now_timestamp) for match in matches_by_round[round_number]):
            break
        progression_round = round_number

    numbered_groups = {}
    labeled_groups = {}
    for index, match in enumerate(matches):
        if not match_is_upcoming(match):
            continue
        round_number = league_round_number(match)
        if round_number is not None:
            if progression_round is None or round_number >= progression_round:
                numbered_groups.setdefault(round_number, []).append((index, match))
            continue
        token = provider_stage_token(match)
        if token is not None:
            labeled_groups.setdefault(token, []).append((index, match))

    if numbered_groups:
        selected_round = min(numbered_groups)
        return [match for _, match in numbered_groups[selected_round]]

    selected_token = choose_scheduled_token(labeled_groups, now_timestamp)
    return [match for _, match in labeled_groups.get(selected_token, [])]


def select_knockout_stage(matches, now_timestamp):
    groups = {}
    for index, match in enumerate(matches):
        if not match_is_upcoming(match):
            continue
        token = provider_stage_token(match)
        if token is not None:
            groups.setdefault(token, []).append((index, match))

    selected_token = choose_scheduled_token(groups, now_timestamp)
    return [match for _, match in groups.get(selected_token, [])]


def select_prediction_scope_matches(competition, matches, now_timestamp=None):
    if not isinstance(competition, dict) or not isinstance(matches, list):
        return []
    scope = competition.get("prediction_scope")
    current_timestamp = time.time() if now_timestamp is None else now_timestamp
    if scope == LEAGUE_NEXT_ROUND:
        scoped_matches = select_league_round(matches, current_timestamp)
    elif scope == KNOCKOUT_NEXT_STAGE:
        scoped_matches = select_knockout_stage(matches, current_timestamp)
    else:
        return []

    return [
        match
        for match in scoped_matches
        if prediction_is_predictable(match, current_timestamp)
    ]
