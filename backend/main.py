import os
import asyncio
import sqlite3
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    get_groups_for_season,
    get_knockout_for_season,
    get_match_live_for_season,
    get_matches_for_competition,
    get_matches_for_season,
    get_standings_for_season,
    get_teams_for_competition,
    get_teams_for_season,
)
from season_service import get_season, get_seasons
from news_service import filter_news
from prediction_service import prediction_is_locked, prediction_is_predictable
from real_data_service import get_match_events, get_real_matches, get_real_teams, get_worldcup_summary
from services.worldcup_adapter import get_match_live_from_worldcup_wrapper, start_worldcup_wrapper_poller

from db_service import (
    init_db,
    save_user_to_db,
    get_all_users_from_db,
    save_favorite_team_to_db,
    get_favorite_teams_from_db,
    get_all_favorite_teams_from_db,
    delete_favorite_team_from_db,
    save_reminder_to_db,
    get_reminders_from_db,
    get_all_reminders_from_db,
    delete_reminder_from_db,
    calculate_prediction_stats,
    get_user_predictions_v2,
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
    team_id: int | str | None = None
    team_key: str = ""
    team_name: str = ""
    name_en: str = ""
    name_fa: str = ""
    emoji: str = ""


class ReminderData(BaseModel):
    telegram_id: int
    match_id: int


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
    try:
        matches = get_prediction_matches_for_season(competition_key, season_key)
    except CompetitionDataProviderError as error:
        raise HTTPException(
            status_code=502, detail="Prediction match provider unavailable"
        ) from error

    predictable_matches = [match for match in matches if prediction_is_predictable(match)]
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

    events = get_match_events_for_season(competition_key, season_key, match_id)
    if events is None:
        raise HTTPException(status_code=501, detail="Competition season events data source not configured")

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


@api.post("/favorite-team")
def save_favorite_team(data: FavoriteTeamData):
    teams = get_real_teams()
    selected_team = None

    for team in teams:
        if str(team.get("id")) == str(data.team_id):
            selected_team = team
            break

    if selected_team is None:
        selected_team = {
            "id": data.team_id or data.team_key or data.team_name or data.name_en or data.name_fa,
            "team_key": data.team_key,
            "team_name": data.team_name or data.name_en or data.name_fa,
            "name_en": data.name_en or data.team_name,
            "name_fa": data.name_fa or data.team_name or data.name_en,
            "emoji": data.emoji or "\u26bd",
        }

    save_favorite_team_to_db(data.telegram_id, selected_team)

    favorite_teams[data.telegram_id] = get_favorite_teams_from_db(data.telegram_id)

    return {
        "success": True,
        "telegram_id": data.telegram_id,
        "favorite_teams": favorite_teams[data.telegram_id],
    }


@api.get("/favorite-teams/{telegram_id}")
def get_favorite_teams(telegram_id: int):
    teams = get_favorite_teams_from_db(telegram_id)
    favorite_teams[telegram_id] = teams

    return {
        "telegram_id": telegram_id,
        "count": len(teams),
        "favorite_teams": teams,
    }


@api.delete("/favorite-team")
def delete_favorite_team(data: FavoriteTeamData):
    deleted = delete_favorite_team_from_db(data.telegram_id, data.team_id, data.team_key)
    favorite_teams[data.telegram_id] = get_favorite_teams_from_db(data.telegram_id)

    return {
        "success": True,
        "deleted": deleted,
        "telegram_id": data.telegram_id,
        "favorite_teams": favorite_teams[data.telegram_id],
    }


@api.post("/reminder")
def save_reminder(data: ReminderData):
    matches = get_real_matches(status="all")
    selected_match = None

    for match in matches:
        if match["id"] == data.match_id:
            selected_match = match
            break

    if selected_match is None:
        return {
            "success": False,
            "message": "Match not found",
        }

    save_reminder_to_db(data.telegram_id, selected_match)

    reminders[data.telegram_id] = get_reminders_from_db(data.telegram_id)

    return {
        "success": True,
        "telegram_id": data.telegram_id,
        "reminders": reminders[data.telegram_id],
    }


@api.get("/reminders/{telegram_id}")
def get_reminders(telegram_id: int):
    user_reminders = get_reminders_from_db(telegram_id)
    reminders[telegram_id] = user_reminders

    return {
        "telegram_id": telegram_id,
        "count": len(user_reminders),
        "reminders": user_reminders,
    }


@api.delete("/reminder")
def delete_reminder(data: ReminderData):
    deleted = delete_reminder_from_db(data.telegram_id, data.match_id)
    reminders[data.telegram_id] = get_reminders_from_db(data.telegram_id)

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
    try:
        match = get_match_for_season(competition_key, season_key, request["match_id"])
    except CompetitionDataProviderError as error:
        raise HTTPException(status_code=502, detail="Prediction match provider unavailable") from error
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    if prediction_is_locked(match):
        raise HTTPException(status_code=409, detail="Prediction is locked")

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

    matches_by_identity = {}
    for prediction in predictions:
        identity = (
            prediction["competition_key"],
            prediction["season_key"],
            prediction["match_id"],
        )
        stored_competition = get_competition(prediction["competition_key"])
        stored_season = get_season(prediction["competition_key"], prediction["season_key"])
        if (
            not stored_competition
            or not stored_season
            or stored_competition.get("supports_predictions") is not True
        ):
            matches_by_identity[identity] = None
            continue
        try:
            matches_by_identity[identity] = get_match_for_season(*identity)
        except CompetitionDataProviderError as error:
            raise HTTPException(
                status_code=502, detail="Prediction match provider unavailable"
            ) from error

    return calculate_prediction_stats(predictions, matches_by_identity)


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
