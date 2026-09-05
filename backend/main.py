import os
import asyncio
import sqlite3
import time
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, StrictInt, StrictStr

from scheduler_service import start_scheduler
from data import NEWS
from aggregate_match_service import aggregate_matches_by_date
from competition_service import get_competition, get_competitions
from competition_data_service import (
    CompetitionDataProviderError,
    CompetitionGroupsProviderError,
    CompetitionKnockoutProviderError,
    CompetitionKnockoutUnavailableError,
    CompetitionStandingsUnavailableError,
    get_match_for_season,
    get_prediction_matches_for_season,
    get_match_events_for_season,
    has_match_events_source_for_season,
    get_groups_for_season,
    get_knockout_for_season,
    get_match_live_for_season,
    get_matches_for_competition,
    get_matches_for_season,
    get_standings_for_season,
    get_team_for_competition,
    get_teams_for_competition,
    get_teams_for_season,
)
from season_service import get_season, get_seasons
from news_service import filter_news, filter_news_for_favorites
from favorite_service import (
    FavoriteTeamTypeError,
    favorite_response_item,
    favorite_team_type,
    resolve_favorite_identities,
)
from prediction_service import prediction_is_locked
from prediction_scope_service import select_prediction_scope_matches
from prediction_evaluation_service import (
    calculate_prediction_stats,
    evaluate_predictions,
    public_display_name,
    resolve_prediction_matches,
)
from real_data_service import get_match_events, get_real_matches, get_real_teams, get_worldcup_summary
from services.worldcup_adapter import get_match_live_from_worldcup_wrapper, start_worldcup_wrapper_poller
from reminder_service import (
    ReminderCapabilityError,
    ReminderCompetitionNotFoundError,
    ReminderEligibilityError,
    ReminderMatchNotFoundError,
    ReminderProviderError,
    ReminderRequestError,
    ReminderSeasonNotFoundError,
    normalize_reminder_request,
    prepare_reminder_snapshot,
)

from db_service import (
    init_db,
    save_user_to_db,
    get_all_users_from_db,
    get_all_favorite_teams_from_db,
    FavoriteTeamsV2RequiredError,
    delete_favorite_team_v2_from_db,
    get_favorite_team_identities_v2_from_db,
    save_favorite_team_v2_to_db,
    save_reminder_to_db,
    get_reminders_from_db,
    get_all_reminders_from_db,
    delete_reminder_from_db,
    get_predictions_v2,
    get_user_predictions_v2,
    get_users_by_telegram_ids,
    save_prediction_v2,
    validate_prediction_shape,
)

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")

api = FastAPI()

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

users = {}
favorite_teams = {}
reminders = {}


class UserData(BaseModel):
    telegram_id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    language_code: str = ""


class FavoriteTeamData(BaseModel):
    telegram_id: int
    competition_key: str | None = None
    team_id: StrictInt | StrictStr | None = None
    team_key: str = ""
    team_name: str = ""
    name_en: str = ""
    name_fa: str = ""
    emoji: str = ""

    class Config:
        extra = "forbid"


class ReminderData(BaseModel):
    telegram_id: int
    match_id: StrictInt | StrictStr
    competition_key: str | None = None
    season_key: str | None = None


class PredictionData(BaseModel):
    telegram_id: int
    match_id: str | int
    competition_key: str | None = None
    season_key: str | None = None
    prediction_type: str | None = None
    predicted_result: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    prediction: str | None = None


def load_memory_from_db():
    users.clear()
    favorite_teams.clear()
    reminders.clear()

    for user in get_all_users_from_db():
        users[user["telegram_id"]] = user

    favorite_teams.update(get_all_favorite_teams_from_db())
    reminders.update(get_all_reminders_from_db())

    print("Memory loaded from database...")


@api.get("/")
def home():
    return {"status": "MatchPulse backend is running"}


@api.get("/competitions")
def list_competitions():
    competitions = get_competitions()
    return {"competitions": competitions}


@api.get("/competitions/{competition_key}/matches")
def get_competition_matches(competition_key: str, status: str = Query("all")):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    try:
        matches = get_matches_for_competition(competition_key, status=status)
    except CompetitionDataProviderError as error:
        raise HTTPException(status_code=502, detail="Matches provider unavailable") from error
    if matches is None:
        raise HTTPException(status_code=501, detail="Competition data source not configured")

    return {
        "count": len(matches),
        "status": status,
        "matches": matches,
    }


@api.get("/competitions/{competition_key}/teams")
def get_competition_teams(competition_key: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    teams = get_teams_for_competition(competition_key)
    if teams is None:
        raise HTTPException(status_code=501, detail="Competition data source not configured")

    return {
        "count": len(teams),
        "teams": teams,
    }


@api.get("/competitions/{competition_key}/seasons")
def list_competition_seasons(competition_key: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    seasons = get_seasons(competition_key)

    return {
        "competition_key": competition["competition_key"],
        "count": len(seasons),
        "seasons": seasons,
    }


@api.get("/competitions/{competition_key}/seasons/{season_key}/matches")
def get_competition_season_matches(competition_key: str, season_key: str, status: str = Query("all")):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    season = get_season(competition_key, season_key)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    try:
        matches = get_matches_for_season(competition_key, season_key, status=status)
    except CompetitionDataProviderError as error:
        raise HTTPException(status_code=502, detail="Matches provider unavailable") from error
    if matches is None:
        raise HTTPException(status_code=501, detail="Competition season data source not configured")

    return {
        "count": len(matches),
        "status": status,
        "matches": matches,
    }


@api.get("/competitions/{competition_key}/seasons/{season_key}/teams")
def get_competition_season_teams(competition_key: str, season_key: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    season = get_season(competition_key, season_key)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    teams = get_teams_for_season(competition_key, season_key)
    if teams is None:
        raise HTTPException(status_code=501, detail="Competition season data source not configured")

    return {
        "count": len(teams),
        "teams": teams,
    }


@api.get("/competitions/{competition_key}/seasons/{season_key}/predictable-matches")
def get_competition_season_predictable_matches(competition_key: str, season_key: str):
    competition_key, season_key = validate_prediction_scope(competition_key, season_key)
    competition = get_competition(competition_key)
    try:
        matches = get_prediction_matches_for_season(competition_key, season_key)
    except CompetitionDataProviderError as error:
        raise HTTPException(
            status_code=502, detail="Prediction match provider unavailable"
        ) from error

    predictable_matches = select_prediction_scope_matches(competition, matches)
    return {
        "competition_key": competition_key,
        "season_key": season_key,
        "count": len(predictable_matches),
        "matches": predictable_matches,
    }


@api.get("/competitions/{competition_key}/seasons/{season_key}/standings")
def get_competition_season_standings(competition_key: str, season_key: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    season = get_season(competition_key, season_key)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    if competition.get("supports_standings") is not True:
        raise HTTPException(status_code=501, detail="Competition standings not supported")

    try:
        standings = get_standings_for_season(competition_key, season_key)
    except CompetitionStandingsUnavailableError as error:
        raise HTTPException(status_code=501, detail="Competition standings not available") from error
    except CompetitionDataProviderError as error:
        raise HTTPException(status_code=502, detail="Standings provider unavailable") from error

    if standings is None:
        raise HTTPException(status_code=501, detail="Competition standings data source not configured")

    return {
        "competition_key": competition["competition_key"],
        "season_key": season["season_key"],
        "count": len(standings),
        "standings": standings,
    }


@api.get("/competitions/{competition_key}/seasons/{season_key}/groups")
def get_competition_season_groups(competition_key: str, season_key: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    season = get_season(competition_key, season_key)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    if competition.get("format") != "group_knockout":
        raise HTTPException(status_code=501, detail="Competition groups not supported")

    if competition.get("supports_groups") is not True:
        raise HTTPException(status_code=501, detail="Competition groups not available")

    try:
        groups = get_groups_for_season(competition_key, season_key)
    except CompetitionGroupsProviderError as error:
        raise HTTPException(status_code=502, detail="Groups provider unavailable") from error

    if groups is None:
        raise HTTPException(status_code=501, detail="Competition groups data source not configured")

    return {
        "competition_key": competition["competition_key"],
        "season_key": season["season_key"],
        "count": len(groups),
        "groups": groups,
    }


@api.get("/competitions/{competition_key}/seasons/{season_key}/knockout")
def get_competition_season_knockout(competition_key: str, season_key: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    season = get_season(competition_key, season_key)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    if competition.get("supports_knockout") is not True:
        raise HTTPException(status_code=501, detail="Competition knockout not supported")

    try:
        rounds = get_knockout_for_season(competition_key, season_key)
    except CompetitionKnockoutUnavailableError as error:
        raise HTTPException(status_code=501, detail="Competition knockout not available") from error
    except CompetitionKnockoutProviderError as error:
        raise HTTPException(status_code=502, detail="Knockout provider unavailable") from error

    if rounds is None:
        raise HTTPException(status_code=501, detail="Competition knockout data source not configured")

    return {
        "competition_key": competition["competition_key"],
        "season_key": season["season_key"],
        "rounds": rounds,
    }


@api.get("/competitions/{competition_key}/seasons/{season_key}/matches/{match_id}/live")
def get_competition_season_match_live(competition_key: str, season_key: str, match_id: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    season = get_season(competition_key, season_key)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    live = get_match_live_for_season(competition_key, season_key, match_id)
    if live is None:
        raise HTTPException(status_code=501, detail="Competition season live data source not configured")

    return live


@api.get("/competitions/{competition_key}/seasons/{season_key}/matches/{match_id}/events")
def get_competition_season_match_events(competition_key: str, season_key: str, match_id: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    season = get_season(competition_key, season_key)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    canonical_competition_key = competition["competition_key"]
    canonical_season_key = season["season_key"]
    if not has_match_events_source_for_season(canonical_competition_key, canonical_season_key):
        raise HTTPException(status_code=501, detail="Competition season events data source not configured")

    if not str(match_id).startswith("mp_match_"):
        raise HTTPException(status_code=404, detail="Match not found")

    try:
        match = get_match_for_season(canonical_competition_key, canonical_season_key, match_id)
    except CompetitionDataProviderError as error:
        raise HTTPException(status_code=502, detail="Events provider unavailable") from error
    if (
        not match
        or str(match.get("id") or "") != str(match_id)
        or str(match.get("competition_key") or "").strip().lower()
        != canonical_competition_key.lower()
        or str(match.get("season_key") or "").strip().lower()
        != canonical_season_key.lower()
    ):
        raise HTTPException(status_code=404, detail="Match not found")

    try:
        events = get_match_events_for_season(
            canonical_competition_key,
            canonical_season_key,
            match_id,
        )
    except CompetitionDataProviderError as error:
        raise HTTPException(status_code=502, detail="Events provider unavailable") from error
    if events is None:
        raise HTTPException(status_code=501, detail="Competition season events data source not configured")
    if (
        not isinstance(events, dict)
        or str(events.get("competition_key") or "").strip().lower()
        != canonical_competition_key.lower()
        or str(events.get("season_key") or "").strip().lower()
        != canonical_season_key.lower()
        or str(events.get("match_id") or "") != str(match_id)
    ):
        raise HTTPException(status_code=502, detail="Events provider unavailable")
    return events


@api.get("/competitions/{competition_key}/seasons/{season_key}")
def get_competition_season_details(competition_key: str, season_key: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    season = get_season(competition_key, season_key)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    return season


@api.get("/competitions/{competition_key}")
def get_competition_details(competition_key: str):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    return competition


@api.post("/user")
def save_user(user: UserData):
    users[user.telegram_id] = {
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "language_code": user.language_code,
    }

    save_user_to_db(user)

    return {
        "success": True,
        "total_users": len(users),
        "user": users[user.telegram_id],
    }


@api.get("/users")
def get_users():
    return {
        "count": len(users),
        "users": list(users.values()),
    }


@api.get("/matches")
def get_matches(status: str = Query("all")):
    matches = get_real_matches(status=status)

    return {
        "count": len(matches),
        "status": status,
        "matches": matches,
    }


@api.get("/matches/by-date")
def get_matches_by_date(date: str = Query(...)):
    try:
        return aggregate_matches_by_date(date)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@api.get("/worldcup/summary")
def get_worldcup_archive_summary():
    return get_worldcup_summary()


@api.get("/match/{match_id}/events")
@api.get("/matches/{match_id}/events")
def get_events(match_id: int):
    return get_match_events(match_id)


@api.get("/match/{match_id}/live")
def get_match_live(match_id: int):
    return get_match_live_from_worldcup_wrapper(match_id)


@api.get("/news")
def get_news(
    category: str | None = Query(None),
    competition_key: str | None = Query(None),
    team_id: str | None = Query(None),
):
    try:
        news = filter_news(
            NEWS,
            category=category,
            competition_key=competition_key,
            team_id=team_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {
        "count": len(news),
        "news": news,
    }


@api.get("/teams")
def get_teams():
    teams = get_real_teams()

    return {
        "count": len(teams),
        "teams": teams,
    }


def validate_favorite_telegram_id(telegram_id):
    if telegram_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid telegram_id")


def favorite_request_has_legacy_display_data(data):
    return any(
        value
        for value in (
            data.team_key,
            data.team_name,
            data.name_en,
            data.name_fa,
            data.emoji,
        )
    )


def normalize_favorite_request(data):
    validate_favorite_telegram_id(data.telegram_id)

    if data.competition_key is None:
        if not isinstance(data.team_id, int) or isinstance(data.team_id, bool) or data.team_id <= 0:
            raise HTTPException(
                status_code=422,
                detail="Legacy favorites require a numeric World Cup team_id",
            )
        competition = get_competition("worldcup2026")
        team_id = str(data.team_id)
        is_legacy = True
    else:
        competition = get_competition(data.competition_key)
        if not competition:
            raise HTTPException(status_code=404, detail="Competition not found")
        if data.team_id is None or str(data.team_id) == "":
            raise HTTPException(status_code=422, detail="team_id is required")
        team_id = str(data.team_id)
        is_legacy = False

    try:
        favorite_team_type(competition)
    except FavoriteTeamTypeError as error:
        raise HTTPException(
            status_code=422, detail="Competition team type is unsupported"
        ) from error
    return competition, team_id, is_legacy


def resolve_favorite_team(competition, team_id):
    try:
        team = get_team_for_competition(competition["competition_key"], team_id)
    except CompetitionDataProviderError as error:
        raise HTTPException(status_code=502, detail="Teams provider unavailable") from error
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


def favorite_storage_http_error(error):
    if isinstance(error, FavoriteTeamsV2RequiredError) and str(error) == "legacy":
        return HTTPException(status_code=503, detail="Favorites V2 migration required")
    return HTTPException(status_code=503, detail="Favorites storage unavailable")


@api.get("/news/favorites/{telegram_id}")
def get_favorite_news(
    telegram_id: int,
    category: str | None = Query(None),
):
    validate_favorite_telegram_id(telegram_id)
    try:
        identities = get_favorite_team_identities_v2_from_db(telegram_id)
        news = filter_news_for_favorites(NEWS, identities, category=category)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (FavoriteTeamsV2RequiredError, sqlite3.Error) as error:
        raise favorite_storage_http_error(error) from error

    return {
        "count": len(news),
        "news": news,
    }


def favorite_list_payload(telegram_id):
    identities = get_favorite_team_identities_v2_from_db(telegram_id)
    resolution = resolve_favorite_identities(identities)
    return {
        "count": len(identities),
        "resolution_errors": resolution["resolution_errors"],
        "unresolved_count": resolution["unresolved_count"],
        "favorite_teams": resolution["favorite_teams"],
    }


@api.post("/favorite-team")
def save_favorite_team(data: FavoriteTeamData):
    competition, team_id, is_legacy = normalize_favorite_request(data)
    if competition.get("supports_favorites") is not True:
        raise HTTPException(
            status_code=501,
            detail="Competition favorites not supported",
        )
    if not is_legacy and favorite_request_has_legacy_display_data(data):
        raise HTTPException(
            status_code=422,
            detail="Favorite display metadata must not be supplied",
        )

    team = resolve_favorite_team(competition, team_id)
    try:
        created = save_favorite_team_v2_to_db(
            data.telegram_id, competition["competition_key"], team_id
        )
        payload = favorite_list_payload(data.telegram_id)
    except (FavoriteTeamsV2RequiredError, sqlite3.Error) as error:
        raise favorite_storage_http_error(error) from error

    favorite_teams[data.telegram_id] = payload["favorite_teams"]
    return {
        "success": True,
        "created": created,
        "telegram_id": data.telegram_id,
        "favorite": favorite_response_item(
            {
                "competition_key": competition["competition_key"],
                "team_id": team_id,
            },
            competition=competition,
            team=team,
        ),
        **payload,
    }


@api.get("/favorite-teams/{telegram_id}")
def get_favorite_teams(telegram_id: int):
    validate_favorite_telegram_id(telegram_id)
    try:
        payload = favorite_list_payload(telegram_id)
    except (FavoriteTeamsV2RequiredError, sqlite3.Error) as error:
        raise favorite_storage_http_error(error) from error
    favorite_teams[telegram_id] = payload["favorite_teams"]
    return {"telegram_id": telegram_id, **payload}


@api.delete("/favorite-team")
def delete_favorite_team(data: FavoriteTeamData):
    competition, team_id, is_legacy = normalize_favorite_request(data)
    if not is_legacy and favorite_request_has_legacy_display_data(data):
        raise HTTPException(
            status_code=422,
            detail="Favorite display metadata must not be supplied",
        )
    if is_legacy:
        resolve_favorite_team(competition, team_id)

    try:
        deleted = delete_favorite_team_v2_from_db(
            data.telegram_id, competition["competition_key"], team_id
        )
        payload = favorite_list_payload(data.telegram_id)
    except (FavoriteTeamsV2RequiredError, sqlite3.Error) as error:
        raise favorite_storage_http_error(error) from error

    favorite_teams[data.telegram_id] = payload["favorite_teams"]
    return {
        "success": True,
        "deleted": deleted,
        "telegram_id": data.telegram_id,
        **payload,
    }


@api.post("/reminder")
def save_reminder(data: ReminderData):
    try:
        request = normalize_reminder_request(data)
        selected_match = prepare_reminder_snapshot(request)
    except ReminderRequestError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ReminderCompetitionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Competition not found") from error
    except ReminderSeasonNotFoundError as error:
        raise HTTPException(status_code=404, detail="Season not found") from error
    except ReminderCapabilityError as error:
        raise HTTPException(
            status_code=501,
            detail="Competition reminders not supported",
        ) from error
    except ReminderMatchNotFoundError as error:
        raise HTTPException(status_code=404, detail="Match not found") from error
    except ReminderProviderError as error:
        raise HTTPException(status_code=502, detail="Matches provider unavailable") from error
    except ReminderEligibilityError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    try:
        created = save_reminder_to_db(
            data.telegram_id,
            selected_match,
            request["competition_key"],
            request["season_key"],
        )
        user_reminders = get_reminders_from_db(data.telegram_id)
    except (RuntimeError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail="Reminder storage unavailable") from error

    reminders[data.telegram_id] = user_reminders

    return {
        "success": True,
        "created": created,
        "telegram_id": data.telegram_id,
        "reminders": reminders[data.telegram_id],
    }


@api.get("/reminders/{telegram_id}")
def get_reminders(telegram_id: int):
    try:
        user_reminders = get_reminders_from_db(telegram_id)
    except (RuntimeError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail="Reminder storage unavailable") from error
    reminders[telegram_id] = user_reminders

    return {
        "telegram_id": telegram_id,
        "count": len(user_reminders),
        "reminders": user_reminders,
    }


@api.delete("/reminder")
def delete_reminder(data: ReminderData):
    try:
        request = normalize_reminder_request(data)
    except ReminderRequestError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        if request["is_legacy"]:
            deleted = delete_reminder_from_db(data.telegram_id, data.match_id)
        else:
            deleted = delete_reminder_from_db(
                data.telegram_id,
                request["match_id"],
                request["competition_key"],
                request["season_key"],
            )
        user_reminders = get_reminders_from_db(data.telegram_id)
    except (RuntimeError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail="Reminder storage unavailable") from error
    reminders[data.telegram_id] = user_reminders

    return {
        "success": True,
        "deleted": deleted,
        "telegram_id": data.telegram_id,
        "reminders": reminders[data.telegram_id],
    }


def normalize_prediction_request(data):
    has_v2_fields = any(
        value is not None
        for value in (
            data.competition_key,
            data.season_key,
            data.prediction_type,
            data.predicted_result,
            data.home_score,
            data.away_score,
        )
    )
    is_legacy = (
        data.prediction is not None
        and not has_v2_fields
        and isinstance(data.match_id, int)
        and not isinstance(data.match_id, bool)
    )

    if is_legacy:
        if data.match_id <= 0:
            raise ValueError("Invalid match_id")
        prediction = data.prediction.strip().lower()
        predicted_result, home_score, away_score = validate_prediction_shape(
            "result", prediction, None, None
        )
        return {
            "competition_key": "worldcup2026",
            "season_key": "2026",
            "match_id": str(data.match_id),
            "prediction_type": "result",
            "predicted_result": predicted_result,
            "home_score": home_score,
            "away_score": away_score,
        }

    if data.prediction is not None:
        raise ValueError("Legacy prediction body cannot include V2 fields")
    if not data.competition_key or not data.season_key or data.prediction_type is None:
        raise ValueError("Competition, season, and prediction type are required")

    prediction_type = data.prediction_type.strip().lower()
    predicted_result = (
        data.predicted_result.strip().lower()
        if isinstance(data.predicted_result, str)
        else data.predicted_result
    )
    predicted_result, home_score, away_score = validate_prediction_shape(
        prediction_type,
        predicted_result,
        data.home_score,
        data.away_score,
    )
    match_id = str(data.match_id).strip()
    if not match_id:
        raise ValueError("Invalid match_id")
    return {
        "competition_key": data.competition_key.strip().lower(),
        "season_key": data.season_key.strip().lower(),
        "match_id": match_id,
        "prediction_type": prediction_type,
        "predicted_result": predicted_result,
        "home_score": home_score,
        "away_score": away_score,
    }


def validate_prediction_scope(competition_key, season_key, require_capability=True):
    competition = get_competition(competition_key)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    season = get_season(competition["competition_key"], season_key)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")
    if require_capability and competition.get("supports_predictions") is not True:
        raise HTTPException(status_code=501, detail="Competition predictions not supported")
    return competition["competition_key"], season["season_key"]


def normalize_prediction_filters(competition_key, season_key):
    normalized_competition = competition_key.strip().lower() if competition_key else None
    normalized_season = season_key.strip().lower() if season_key else None
    if normalized_competition:
        competition = get_competition(normalized_competition)
        if not competition:
            raise HTTPException(status_code=404, detail="Competition not found")
        normalized_competition = competition["competition_key"]
        if normalized_season and not get_season(normalized_competition, normalized_season):
            raise HTTPException(status_code=404, detail="Season not found")
    elif normalized_season and not any(
        get_season(competition["competition_key"], normalized_season)
        for competition in get_competitions()
    ):
        raise HTTPException(status_code=404, detail="Season not found")
    return normalized_competition, normalized_season


def prediction_scope_supports_evaluation(prediction):
    competition = get_competition(prediction.get("competition_key"))
    season = get_season(
        prediction.get("competition_key"), prediction.get("season_key")
    )
    return bool(
        competition
        and season
        and (
            competition.get("supports_predictions") is True
            or competition.get("supports_prediction_history") is True
        )
    )


def resolve_prediction_evaluations(predictions):
    matches_by_identity, evaluation_errors = resolve_prediction_matches(
        predictions,
        get_match_for_season,
        CompetitionDataProviderError,
        should_resolve=prediction_scope_supports_evaluation,
    )
    evaluations, stats = evaluate_predictions(predictions, matches_by_identity)
    return evaluations, stats, evaluation_errors


def prediction_history_item(prediction, evaluation):
    return {
        "competition_key": prediction["competition_key"],
        "season_key": prediction["season_key"],
        "match_id": prediction["match_id"],
        "prediction_type": prediction["prediction_type"],
        "predicted_result": prediction["predicted_result"],
        "home_score": prediction["home_score"],
        "away_score": prediction["away_score"],
        "points_awarded": prediction["points_awarded"],
        "created_at": prediction["created_at"],
        "updated_at": prediction["updated_at"],
        "evaluation": evaluation,
    }


@api.post("/prediction")
def create_or_update_prediction(data: PredictionData):
    if data.telegram_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid telegram_id")
    try:
        request = normalize_prediction_request(data)
    except (AttributeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    competition_key, season_key = validate_prediction_scope(
        request["competition_key"], request["season_key"]
    )
    competition = get_competition(competition_key)
    try:
        matches = get_prediction_matches_for_season(competition_key, season_key)
    except CompetitionDataProviderError as error:
        raise HTTPException(status_code=502, detail="Prediction match provider unavailable") from error
    requested_match_id = str(request["match_id"])
    match = next(
        (
            candidate
            for candidate in matches
            if isinstance(candidate, dict) and str(candidate.get("id")) == requested_match_id
        ),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    now_timestamp = time.time()
    if prediction_is_locked(match, now_timestamp):
        raise HTTPException(status_code=409, detail="Prediction is locked")
    predictable_matches = select_prediction_scope_matches(competition, matches, now_timestamp)
    if not any(str(candidate.get("id")) == requested_match_id for candidate in predictable_matches):
        raise HTTPException(status_code=409, detail="Match is outside the current prediction scope")

    try:
        save_prediction_v2(
            data.telegram_id,
            competition_key,
            season_key,
            request["match_id"],
            request["prediction_type"],
            request["predicted_result"],
            request["home_score"],
            request["away_score"],
        )
        predictions = get_user_predictions_v2(data.telegram_id)
    except sqlite3.Error as error:
        raise HTTPException(status_code=503, detail="Prediction storage unavailable") from error
    return {"success": True, "count": len(predictions), "predictions": predictions}


@api.get("/predictions/{telegram_id}")
def get_predictions(
    telegram_id: int,
    competition_key: str | None = Query(None),
    season_key: str | None = Query(None),
):
    if telegram_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid telegram_id")
    competition_key, season_key = normalize_prediction_filters(competition_key, season_key)
    try:
        predictions = get_user_predictions_v2(telegram_id, competition_key, season_key)
    except sqlite3.Error as error:
        raise HTTPException(status_code=503, detail="Prediction storage unavailable") from error
    return {"count": len(predictions), "predictions": predictions}


@api.get("/prediction-history/{telegram_id}")
def prediction_history(
    telegram_id: int,
    competition_key: str | None = Query(None),
    season_key: str | None = Query(None),
):
    if telegram_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid telegram_id")
    competition_key, season_key = normalize_prediction_filters(
        competition_key, season_key
    )
    try:
        predictions = get_user_predictions_v2(
            telegram_id, competition_key, season_key
        )
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=503, detail="Prediction storage unavailable"
        ) from error

    evaluations, _, evaluation_errors = resolve_prediction_evaluations(predictions)
    history = [
        prediction_history_item(prediction, evaluation)
        for prediction, evaluation in zip(predictions, evaluations)
    ]
    return {
        "count": len(history),
        "evaluation_errors": evaluation_errors,
        "history": history,
    }


@api.get("/prediction-leaderboard")
def prediction_leaderboard(
    competition_key: str | None = Query(None),
    season_key: str | None = Query(None),
):
    competition_key, season_key = normalize_prediction_filters(
        competition_key, season_key
    )
    try:
        predictions = get_predictions_v2(competition_key, season_key)
        predictions = [
            prediction
            for prediction in predictions
            if prediction_scope_supports_evaluation(prediction)
        ]
        users = get_users_by_telegram_ids(
            prediction["telegram_id"] for prediction in predictions
        )
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=503, detail="Prediction storage unavailable"
        ) from error

    matches_by_identity, evaluation_errors = resolve_prediction_matches(
        predictions,
        get_match_for_season,
        CompetitionDataProviderError,
        should_resolve=prediction_scope_supports_evaluation,
    )

    predictions_by_user = {}
    for prediction in predictions:
        predictions_by_user.setdefault(prediction["telegram_id"], []).append(prediction)

    leaderboard = []
    for telegram_id, user_predictions in predictions_by_user.items():
        stats = calculate_prediction_stats(user_predictions, matches_by_identity)
        leaderboard.append({
            "display_name": public_display_name(users.get(telegram_id)),
            **stats,
        })

    leaderboard.sort(
        key=lambda entry: (
            -entry["points"],
            -entry["correct"],
            entry["display_name"].casefold(),
        )
    )
    rank = 0
    previous_rank_values = None
    for entry in leaderboard:
        rank_values = (entry["points"], entry["correct"])
        if rank_values != previous_rank_values:
            rank += 1
            previous_rank_values = rank_values
        entry["rank"] = rank

    return {
        "count": len(leaderboard),
        "evaluation_errors": evaluation_errors,
        "leaderboard": leaderboard,
    }


@api.get("/prediction-stats/{telegram_id}")
def prediction_stats(
    telegram_id: int,
    competition_key: str | None = Query(None),
    season_key: str | None = Query(None),
):
    if telegram_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid telegram_id")
    competition_key, season_key = normalize_prediction_filters(competition_key, season_key)
    try:
        predictions = get_user_predictions_v2(telegram_id, competition_key, season_key)
    except sqlite3.Error as error:
        raise HTTPException(status_code=503, detail="Prediction storage unavailable") from error

    _, stats, evaluation_errors = resolve_prediction_evaluations(predictions)
    if evaluation_errors:
        raise HTTPException(
            status_code=502, detail="Prediction match provider unavailable"
        )
    return stats


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                text="⚽ Open MatchPulse App",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ]
    ]

    await update.message.reply_text(
        "به MatchPulse خوش اومدی ⚽\n\n"
        "برای باز کردن اپ، دکمه زیر رو بزن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def create_bot_app():
    if not BOT_TOKEN:
        print("Telegram bot disabled: BOT_TOKEN is not configured.")
        return None

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    return app


bot_app = create_bot_app()


@api.get("/test-notification/{telegram_id}")
async def test_notification(telegram_id: int):
    if bot_app is None:
        return {
            "success": False,
            "message": "Telegram bot is not configured",
            "telegram_id": telegram_id,
        }

    try:
        await bot_app.bot.send_message(
            chat_id=telegram_id,
            text=(
                "🔔 پیام تست MatchPulse\n\n"
                "اگر این پیام را می‌بینی، ارسال اعلان تلگرام درست کار می‌کند."
            ),
        )

        return {
            "success": True,
            "message": "Test notification sent",
            "telegram_id": telegram_id,
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "telegram_id": telegram_id,
        }


@api.get("/test-match-reminder/{telegram_id}/{match_id}")
async def test_match_reminder(telegram_id: int, match_id: int):
    if bot_app is None:
        return {
            "success": False,
            "message": "Telegram bot is not configured",
            "telegram_id": telegram_id,
            "match_id": match_id,
        }

    matches = get_real_matches(status="all")
    selected_match = None

    for match in matches:
        if match["id"] == match_id:
            selected_match = match
            break

    if selected_match is None:
        return {
            "success": False,
            "message": "Match not found",
            "telegram_id": telegram_id,
            "match_id": match_id,
        }

    text = (
        "🔔 یادآوری مسابقه MatchPulse\n\n"
        f"{selected_match.get('home_flag', '⚽')} {selected_match.get('home_en')} "
        f"vs "
        f"{selected_match.get('away_flag', '⚽')} {selected_match.get('away_en')}\n\n"
        f"🕒 {selected_match.get('date_iran')} - {selected_match.get('time_iran')}\n"
        f"🏟 {selected_match.get('stadium')}\n"
        f"📍 {selected_match.get('city')}\n\n"
        "این یک پیام تست برای اعلان مسابقه است."
    )

    try:
        await bot_app.bot.send_message(
            chat_id=telegram_id,
            text=text,
        )

        return {
            "success": True,
            "message": "Match reminder test sent",
            "telegram_id": telegram_id,
            "match_id": match_id,
            "match": selected_match,
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "telegram_id": telegram_id,
            "match_id": match_id,
        }


@api.on_event("startup")
async def startup():
    init_db()
    load_memory_from_db()
    start_worldcup_wrapper_poller()

    start_scheduler(
        bot_app=bot_app,
        reminders=reminders,
        favorite_teams=favorite_teams,
        get_matches=get_real_matches,
        get_events=get_match_events,
        event_loop=asyncio.get_running_loop(),
    )

    if bot_app is None:
        print("Backend started without Telegram polling.")
        return

    try:
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        print("Telegram bot started...")
    except Exception as error:
        print(f"Telegram bot failed to start: {error}")
        print("Backend is still running without Telegram polling.")


@api.on_event("shutdown")
async def shutdown():
    if bot_app is None:
        return

    try:
        if bot_app.updater.running:
            await bot_app.updater.stop()

        if bot_app.running:
            await bot_app.stop()

        await bot_app.shutdown()
        print("Telegram bot stopped...")
    except Exception as error:
        print(f"Telegram shutdown skipped: {error}")
