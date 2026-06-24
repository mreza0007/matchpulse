import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from scheduler_service import start_scheduler
from data import NEWS
from real_data_service import get_match_events, get_real_matches, get_real_teams
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


@api.get("/match/{match_id}/events")
def get_events(match_id: int):
    return get_match_events(match_id)


@api.get("/match/{match_id}/live")
def get_match_live(match_id: int):
    return get_match_live_from_worldcup_wrapper(match_id)


@api.get("/news")
def get_news():
    return {
        "count": len(NEWS),
        "news": NEWS,
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
