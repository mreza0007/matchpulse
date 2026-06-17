from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

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
        f"🔔 {reason}\n\n"
        f"{match.get('home_flag', '⚽')} {match.get('home_en')} "
        f"vs "
        f"{match.get('away_flag', '⚽')} {match.get('away_en')}\n\n"
        f"🕒 {match.get('date_iran')} - {match.get('time_iran')}\n"
        f"🏟 {match.get('stadium')}\n"
        f"📍 {match.get('city')}\n\n"
        f"بازی تا حدود یک ساعت دیگر شروع می‌شود."
    )


def parse_kickoff(kickoff):
    return datetime.fromisoformat(kickoff.replace("Z", "+00:00"))


async def send_telegram_message(bot_app, telegram_id, text):
    await bot_app.bot.send_message(
        chat_id=telegram_id,
        text=text,
    )


def should_notify(match):
    now = datetime.now(timezone.utc)
    kickoff = parse_kickoff(match["kickoff"])

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
            if not should_notify(match):
                continue

            notification_key = f"manual:{telegram_id}:{match['id']}"

            if notification_key in sent_notifications:
                continue

            text = build_match_message(
                match,
                "یادآوری مسابقه",
            )

            try:
                import asyncio
                asyncio.run(send_telegram_message(bot_app, telegram_id, text))
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
                    f"مسابقه تیم محبوب شما: {team.get('emoji', '⭐')} {team.get('name_en')}",
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