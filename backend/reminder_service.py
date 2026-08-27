from copy import deepcopy
from datetime import datetime, timezone

from competition_data_service import (
    CompetitionDataProviderError,
    get_match_for_season,
)
from competition_service import get_competition
from season_service import get_season


LEGACY_COMPETITION_KEY = "worldcup2026"
LEGACY_SEASON_KEY = "2026"


class ReminderRequestError(ValueError):
    pass


class ReminderCompetitionNotFoundError(LookupError):
    pass


class ReminderSeasonNotFoundError(LookupError):
    pass


class ReminderMatchNotFoundError(LookupError):
    pass


class ReminderCapabilityError(RuntimeError):
    pass


class ReminderProviderError(RuntimeError):
    pass


class ReminderEligibilityError(RuntimeError):
    pass


def normalize_reminder_request(data):
    competition_key = getattr(data, "competition_key", None)
    season_key = getattr(data, "season_key", None)
    match_id = getattr(data, "match_id", None)
    has_scoped_identity = competition_key is not None or season_key is not None

    if not has_scoped_identity:
        if (
            not isinstance(match_id, int)
            or isinstance(match_id, bool)
            or match_id <= 0
        ):
            raise ReminderRequestError("Legacy reminder match_id must be a positive integer")
        return {
            "competition_key": LEGACY_COMPETITION_KEY,
            "season_key": LEGACY_SEASON_KEY,
            "match_id": str(match_id),
            "is_legacy": True,
        }

    normalized_competition = str(competition_key or "").strip().lower()
    normalized_season = str(season_key or "").strip().lower()
    if not normalized_competition or not normalized_season:
        raise ReminderRequestError("Competition and season are required together")
    if not isinstance(match_id, str):
        raise ReminderRequestError("Scoped reminder match_id must be text")
    normalized_match_id = str(match_id).strip()
    if not normalized_match_id:
        raise ReminderRequestError("Reminder match_id is required")

    return {
        "competition_key": normalized_competition,
        "season_key": normalized_season,
        "match_id": normalized_match_id,
        "is_legacy": False,
    }


def parse_reminder_kickoff(match):
    kickoff_value = match.get("kickoff_utc") if isinstance(match, dict) else None
    if not isinstance(kickoff_value, str) or not kickoff_value.strip():
        raise ReminderEligibilityError("Match kickoff is missing")
    try:
        kickoff = datetime.fromisoformat(
            kickoff_value.strip().replace("Z", "+00:00")
        )
    except ValueError as error:
        raise ReminderEligibilityError("Match kickoff is invalid") from error
    if kickoff.tzinfo is None or kickoff.utcoffset() is None:
        raise ReminderEligibilityError("Match kickoff is invalid")
    if kickoff.utcoffset().total_seconds() != 0:
        raise ReminderEligibilityError("Match kickoff is not UTC")
    return kickoff.astimezone(timezone.utc)


def validate_reminder_eligibility(match, now=None):
    status = (
        str(match.get("status") or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    if (
        status != "upcoming"
        or match.get("is_live") is True
        or match.get("is_finished") is True
    ):
        raise ReminderEligibilityError("Match is not upcoming")

    kickoff = parse_reminder_kickoff(match)
    current_time = datetime.now(timezone.utc) if now is None else now
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("Reminder eligibility clock must be timezone-aware")
    if kickoff <= current_time.astimezone(timezone.utc):
        raise ReminderEligibilityError("Match kickoff is not in the future")
    return kickoff


def prepare_reminder_snapshot(request, now=None):
    competition = get_competition(request["competition_key"])
    if not competition:
        raise ReminderCompetitionNotFoundError()

    season = get_season(competition["competition_key"], request["season_key"])
    if not season:
        raise ReminderSeasonNotFoundError()

    if (
        competition.get("status") != "active"
        or competition.get("is_active") is not True
        or competition.get("supports_reminders") is not True
    ):
        raise ReminderCapabilityError()

    try:
        match = get_match_for_season(
            competition["competition_key"],
            season["season_key"],
            request["match_id"],
        )
    except CompetitionDataProviderError as error:
        raise ReminderProviderError() from error

    if not isinstance(match, dict):
        raise ReminderMatchNotFoundError()
    canonical_match_id = str(match.get("id") or "").strip()
    if not canonical_match_id or canonical_match_id != request["match_id"]:
        raise ReminderMatchNotFoundError()

    validate_reminder_eligibility(match, now=now)
    snapshot = deepcopy(match)
    snapshot["competition_key"] = competition["competition_key"]
    snapshot["season_key"] = season["season_key"]
    snapshot["match_id"] = canonical_match_id
    return snapshot
