import os
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

from db_service import mark_reminder_notified

scheduler = BackgroundScheduler()

scheduler_state = {
    "bot_app": None,
    "reminders": None,
    "favorite_teams": None,
    "get_matches": None,
    "sent_notifications": set(),
}


def build_match_message(match, reason):
    return (
        f"\U0001f514 {reason}\n\n"
        f"{match.get('home_flag', '\u26bd')} {match.get('home_en')} "
        f"vs "
        f"{match.get('away_flag', '\u26bd')} {match.get('away_en')}\n\n"
        f"\U0001f552 {match.get('date_iran')} - {match.get('time_iran')}\n"
        f"\U0001f3df {match.get('stadium')}\n"
        f"\U0001f4cd {match.get('city')}\n\n"
        f"\u0628\u0627\u0632\u06cc \u062a\u0627 \u062d\u062f\u0648\u062f \u06cc\u06a9 \u0633\u0627\u0639\u062a \u062f\u06cc\u06af\u0631 \u0634\u0631\u0648\u0639 \u0645\u06cc\u200c\u0634\u0648\u062f."
    )


def parse_kickoff(kickoff):
    if not kickoff:
        return None

    try:
        return datetime.fromisoformat(str(kickoff).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


async def send_telegram_message(bot_app, telegram_id, text):
    await bot_app.bot.send_message(
        chat_id=telegram_id,
        text=text,
    )


def should_notify(match):
    now = datetime.now(timezone.utc)
    kickoff = parse_kickoff(match.get("kickoff"))

    if kickoff is None:
        return False

    notify_from = kickoff - timedelta(minutes=65)
    notify_until = kickoff - timedelta(minutes=55)

    return notify_from <= now <= notify_until


def check_manual_reminders():
    bot_app = scheduler_state["bot_app"]
    reminders = scheduler_state["reminders"]
    sent_notifications = scheduler_state["sent_notifications"]

    if bot_app is None or reminders is None:
        print("Manual reminders skipped: missing bot or reminders.")
        return

    for telegram_id, user_reminders in reminders.items():
        for match in user_reminders:
            if match.get("notified"):
                continue

            if not should_notify(match):
                continue

            notification_key = f"manual:{telegram_id}:{match['id']}"

            if notification_key in sent_notifications:
                continue

            text = build_match_message(
                match,
                "\u06cc\u0627\u062f\u0622\u0648\u0631\u06cc \u0645\u0633\u0627\u0628\u0642\u0647",
            )

            try:
                import asyncio
                asyncio.run(send_telegram_message(bot_app, telegram_id, text))
                mark_reminder_notified(telegram_id, match["id"])
                match["notified"] = True
                sent_notifications.add(notification_key)
                print(f"Manual reminder sent to {telegram_id} for match {match['id']}")
            except Exception as error:
                print(f"Failed to send manual reminder: {error}")


def team_is_in_match(team, match):
    team_name = team.get("name_en")

    return (
        team_name == match.get("home_en")
        or team_name == match.get("away_en")
    )


def check_favorite_team_matches():
    bot_app = scheduler_state["bot_app"]
    favorite_teams = scheduler_state["favorite_teams"]
    get_matches = scheduler_state["get_matches"]
    sent_notifications = scheduler_state["sent_notifications"]

    if bot_app is None or favorite_teams is None or get_matches is None:
        print("Favorite team reminders skipped: missing data.")
        return

    matches = get_matches(status="upcoming")

    for telegram_id, teams in favorite_teams.items():
        for team in teams:
            for match in matches:
                if not team_is_in_match(team, match):
                    continue

                if not should_notify(match):
                    continue

                notification_key = f"favorite:{telegram_id}:{team['id']}:{match['id']}"

                if notification_key in sent_notifications:
                    continue

                text = build_match_message(
                    match,
                    f"\u0645\u0633\u0627\u0628\u0642\u0647 \u062a\u06cc\u0645 \u0645\u062d\u0628\u0648\u0628 \u0634\u0645\u0627: {team.get('emoji', '\u2b50')} {team.get('name_en')}",
                )

                try:
                    import asyncio
                    asyncio.run(send_telegram_message(bot_app, telegram_id, text))
                    sent_notifications.add(notification_key)
                    print(
                        f"Favorite team reminder sent to {telegram_id} "
                        f"for team {team['name_en']} match {match['id']}"
                    )
                except Exception as error:
                    print(f"Failed to send favorite team reminder: {error}")


def check_all_notifications():
    print("Checking notifications...")
    check_manual_reminders()
    check_favorite_team_matches()


def start_scheduler(bot_app, reminders, favorite_teams, get_matches):
    scheduler_state["bot_app"] = bot_app
    scheduler_state["reminders"] = reminders
    scheduler_state["favorite_teams"] = favorite_teams
    scheduler_state["get_matches"] = get_matches

    if not scheduler.running:
        scheduler.add_job(
            check_all_notifications,
            "interval",
            minutes=1,
            id="matchpulse_notifications",
            replace_existing=True,
        )
        scheduler.start()
        print("Scheduler started...")
