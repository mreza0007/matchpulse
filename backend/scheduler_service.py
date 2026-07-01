import asyncio
import os
import re
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from db_service import (
    get_all_favorite_teams_from_db,
    get_all_users,
    get_relevant_users_for_match,
    has_sent_notification,
    has_live_notification_been_sent,
    mark_notification_sent,
    mark_live_notification_sent,
    mark_reminder_notified,
    normalize_team_key,
)

DEFAULT_BALL = "\u26bd"
DEFAULT_STAR = "\u2b50"

scheduler = BackgroundScheduler()
pending_final_confirmations = {}

scheduler_state = {
    "bot_app": None,
    "reminders": None,
    "favorite_teams": None,
    "get_matches": None,
    "get_events": None,
    "event_loop": None,
    "seeded_existing_live_notifications": False,
    "suppressed_notifications": set(),
}


def match_id(match):
    return match.get("id") or match.get("internal_match_id")


def team_display(match, side):
    return {
        "key": normalize_team_key(match.get(f"{side}_en") or match.get(f"{side}_fa") or match.get(f"{side}_team")),
        "name": match.get(f"{side}_fa") or match.get(f"{side}_en") or match.get(f"{side}_team") or "",
        "name_en": match.get(f"{side}_en") or match.get(f"{side}_team") or "",
        "flag": match.get(f"{side}_flag") or DEFAULT_BALL,
    }


def score_line(match):
    home_score = match.get("home_score")
    away_score = match.get("away_score")

    if home_score is None:
        home_score = match.get("score", {}).get("home") if isinstance(match.get("score"), dict) else "-"

    if away_score is None:
        away_score = match.get("score", {}).get("away") if isinstance(match.get("score"), dict) else "-"

    home = team_display(match, "home")
    away = team_display(match, "away")
    return f"{home['flag']} {home['name']} {home_score} - {away_score} {away['name']} {away['flag']}"


def fixture_line(match):
    home = team_display(match, "home")
    away = team_display(match, "away")
    return f"{home['flag']} {home['name']} - {away['flag']} {away['name']}"


def build_match_message(match, reason):
    return (
        f"\U0001f514 {reason}\n\n"
        f"{fixture_line(match)}\n\n"
        f"\U0001f552 {match.get('date_iran')} - {match.get('time_iran')}\n"
        f"\U0001f3df {match.get('stadium')}\n"
        f"\U0001f4cd {match.get('city')}\n\n"
        "\u0628\u0627\u0632\u06cc \u062a\u0627 \u062d\u062f\u0648\u062f \u06cc\u06a9 \u0633\u0627\u0639\u062a \u062f\u06cc\u06af\u0631 \u0634\u0631\u0648\u0639 \u0645\u06cc\u200c\u0634\u0648\u062f."
    )


def parse_kickoff(match):
    timestamp = match.get("kickoff_ts") or match.get("kickoff_timestamp")

    if timestamp is not None:
        try:
            return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass

    kickoff = match.get("kickoff_utc") or match.get("kickoff") or match.get("kickoff_iso")

    if not kickoff:
        return None

    try:
        parsed = datetime.fromisoformat(str(kickoff).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def send_telegram_message(bot_app, telegram_id, text):
    await bot_app.bot.send_message(chat_id=telegram_id, text=text)


def env_flag(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def live_notifications_enabled():
    return env_flag("ENABLE_LIVE_NOTIFICATIONS", True)


def live_notification_interval_seconds():
    try:
        return max(10, int(os.getenv("LIVE_NOTIFICATION_INTERVAL_SECONDS", "30")))
    except (TypeError, ValueError):
        return 30


def notification_dry_run():
    return env_flag("NOTIFICATION_DRY_RUN", False)


def send_once(bot_app, telegram_id, text, notification_key, match_id_value=None, log_label="notification"):
    if notification_already_handled(notification_key):
        print(f"Skipped duplicate notification: {notification_key}")
        return False

    if notification_dry_run():
        print(f"DRY RUN {log_label} to {telegram_id}: {notification_key}\n{text}")
        return False

    try:
        event_loop = scheduler_state.get("event_loop")

        if event_loop is None or event_loop.is_closed():
            raise RuntimeError("Telegram application event loop is not available.")

        future = asyncio.run_coroutine_threadsafe(
            send_telegram_message(bot_app, telegram_id, text),
            event_loop,
        )
        future.result(timeout=30)
        mark_notification_sent(notification_key, user_id=telegram_id, match_id=match_id_value)
        print(f"Sent {log_label} to {telegram_id}: {notification_key}")
        return True
    except Exception as error:
        print(f"Failed {log_label} for user_id={telegram_id}: {error}")
        return False


def notification_already_handled(notification_key):
    return notification_key in scheduler_state["suppressed_notifications"] or has_sent_notification(notification_key)


def should_notify(match):
    now = datetime.now(timezone.utc)
    kickoff = parse_kickoff(match)

    if kickoff is None:
        return False

    notify_from = kickoff - timedelta(minutes=65)
    notify_until = kickoff - timedelta(minutes=55)

    return notify_from <= now <= notify_until


def normalized_status(match):
    return str(match.get("status") or "").strip().lower().replace("-", "_").replace(" ", "_")


def raw_provider_status(match):
    raw_status = match.get("raw_provider_status")

    if isinstance(raw_status, dict):
        return raw_status

    return {}


def provider_status_values(match):
    raw_status = raw_provider_status(match)
    values = {
        normalized_status(match),
        str(match.get("status_title") or "").strip().lower(),
        str(raw_status.get("status") or "").strip().lower(),
        str(raw_status.get("statusTitle") or "").strip().lower(),
        str(raw_status.get("status_title") or "").strip().lower(),
    }

    return {value for value in values if value}


def provider_status_known(match):
    return bool(provider_status_values(match))


def provider_status_is_live(match):
    live_values = {
        "live",
        "in_progress",
        "ongoing",
        "1h",
        "2h",
        "ht",
        "et",
        "first_half",
        "second_half",
    }
    values = provider_status_values(match)

    return bool(values.intersection(live_values)) or match.get("is_live") is True


def match_has_started(match):
    if match.get("is_finished") is True or match.get("status") == "finished":
        return False

    status = normalized_status(match)

    if status in {"finished", "upcoming", "scheduled", "notstarted", "not_started"}:
        return False

    if provider_status_is_live(match):
        return True

    if provider_status_known(match):
        return False

    kickoff = parse_kickoff(match)

    if kickoff is None:
        return False

    now = datetime.now(timezone.utc)
    return kickoff <= now <= kickoff + timedelta(minutes=10)


def match_is_finished(match):
    return is_definitely_finished(match)


def is_active_or_transitional(match):
    if match.get("is_live") is True:
        return True

    status_values = provider_status_values(match)
    active_statuses = {
        "live",
        "in_progress",
        "ongoing",
        "1h",
        "2h",
        "ht",
        "halftime",
        "half_time",
        "break",
        "et",
        "extra_time",
        "penalties",
        "penalty",
        "penalty_shootout",
        "shootout",
        "pending_result",
        "scheduled",
        "upcoming",
        "notstarted",
        "not_started",
    }

    if status_values.intersection(active_statuses):
        return True

    title_text = " ".join(
        str(value or "").strip().lower()
        for value in (
            match.get("status_title"),
            match.get("live_badge"),
            match.get("raw_live_badge"),
            raw_provider_status(match).get("statusTitle"),
            raw_provider_status(match).get("status_title"),
        )
        if value is not None
    )
    transitional_markers = (
        "half time",
        "halftime",
        "break",
        "extra time",
        "penalty shootout",
        "penalties",
        "نیمه",
        "استراحت",
        "وقت اضافه",
        "ضربات پنالتی",
    )
    return any(marker in title_text for marker in transitional_markers)


def is_definitely_finished(match):
    if is_active_or_transitional(match):
        return False

    if match.get("is_finished") is True or normalized_status(match) == "finished":
        return True

    if str(match.get("raw_live_badge") or "").strip().upper() == "FT":
        return True

    title_text = " ".join(
        str(value or "").strip()
        for value in (
            match.get("status_title"),
            raw_provider_status(match).get("statusTitle"),
            raw_provider_status(match).get("status_title"),
        )
        if value is not None
    )
    lowered_title = title_text.lower()
    return (
        "نتیجه نهایی" in title_text
        or "finished" in lowered_title
        or "full time" in lowered_title
        or re.search(r"\bft\b", lowered_title) is not None
    )


def has_final_score(match):
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = match.get("home_score")
    away_score = match.get("away_score")

    if home_score is None:
        home_score = score.get("home")

    if away_score is None:
        away_score = score.get("away")

    return home_score is not None and away_score is not None


def user_favorite_for_match(user_favorites, match):
    home = team_display(match, "home")
    away = team_display(match, "away")
    match_keys = {home["key"], away["key"]}

    for favorite in user_favorites:
        favorite_keys = {
            normalize_team_key(favorite.get("team_key")),
            normalize_team_key(favorite.get("team_name")),
            normalize_team_key(favorite.get("name_en")),
            normalize_team_key(favorite.get("name_fa")),
        }

        if favorite_keys.intersection(match_keys):
            return favorite

    return None


def team_is_in_match(team, match):
    return user_favorite_for_match([team], match) is not None


def favorite_team_context(favorite, match):
    home = team_display(match, "home")
    away = team_display(match, "away")
    favorite_keys = {
        normalize_team_key(favorite.get("team_key")),
        normalize_team_key(favorite.get("team_name")),
        normalize_team_key(favorite.get("name_en")),
        normalize_team_key(favorite.get("name_fa")),
    }

    if home["key"] in favorite_keys:
        return home, away

    return away, home


def has_user_match_specific_notification(notification_type, match, telegram_id):
    match_id_value = match_id(match)
    home = team_display(match, "home")
    away = team_display(match, "away")

    return any(
        notification_already_handled(f"{notification_type}:{match_id_value}:{team['key']}:{telegram_id}")
        for team in (home, away)
    )


def suppress_notification_key(notification_key, telegram_id=None, match_id_value=None):
    scheduler_state["suppressed_notifications"].add(notification_key)

    if not notification_dry_run():
        mark_notification_sent(notification_key, user_id=telegram_id, match_id=match_id_value)


def user_start_key(match, telegram_id, favorite=None):
    match_id_value = match_id(match)

    if favorite:
        favorite_team, _opponent = favorite_team_context(favorite, match)
        return f"favorite_match_start:{match_id_value}:{favorite_team['key']}:{telegram_id}"

    return f"global_match_start:{match_id_value}:{telegram_id}"


def user_finished_key(match, telegram_id, favorite=None):
    match_id_value = match_id(match)

    if favorite:
        favorite_team, _opponent = favorite_team_context(favorite, match)
        return f"favorite_match_finished:{match_id_value}:{favorite_team['key']}:{telegram_id}"

    return f"global_match_finished:{match_id_value}:{telegram_id}"


def event_id(event, index):
    return event.get("id") or f"{event.get('display_minute') or event.get('raw_minute') or event.get('minute')}-{event.get('type')}-{index}"


def scoring_side(event, match):
    side = str(event.get("team_side") or event.get("team") or "").strip().lower()

    if side in {"home", "host", "home_team"}:
        return "home"

    if side in {"away", "guest", "away_team"}:
        return "away"

    team_name_key = normalize_team_key(event.get("team_name") or event.get("teamName"))
    home = team_display(match, "home")
    away = team_display(match, "away")

    if team_name_key and team_name_key in {home["key"], normalize_team_key(home["name"])}:
        return "home"

    if team_name_key and team_name_key in {away["key"], normalize_team_key(away["name"])}:
        return "away"

    return ""


def scorer_name(event):
    return event.get("scorer") or event.get("player_name") or event.get("player") or "\u0646\u0627\u0645\u0634\u062e\u0635"


def load_matches():
    get_matches = scheduler_state["get_matches"]

    if get_matches is None:
        return []

    try:
        return get_matches(status="all")
    except Exception as error:
        print(f"Failed to load matches for scheduler: {error}")
        return []


def load_events(match_id_value):
    get_events = scheduler_state["get_events"]

    if get_events is None:
        return []

    try:
        payload = get_events(match_id_value)
    except Exception as error:
        print(f"Failed to load events for match_id={match_id_value}: {error}")
        return []

    if isinstance(payload, dict):
        provider = payload.get("provider")
        external_match_id = payload.get("external_match_id")
        events = payload.get("events") or []

        for event in events:
            if isinstance(event, dict):
                event.setdefault("provider", provider)
                event.setdefault("external_match_id", external_match_id)

        return events

    return payload if isinstance(payload, list) else []


def to_persian_digits(value):
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def clean_value(value):
    if value is None:
        return ""

    text = str(value).strip()
    return "" if text.lower() in {"none", "null", "undefined", ""} else text


def live_event_type(event):
    return clean_value(event.get("normalized_type") or event.get("event_type") or event.get("type")).lower().replace("-", "_")


def is_scoring_event(event):
    explicit = event.get("is_scoring_event")

    if explicit is True or str(explicit).strip().lower() in {"true", "1", "yes"}:
        return True

    return live_event_type(event) in {"goal", "own_goal", "penalty_goal"}


def is_live_match(match):
    return match.get("is_live") is True or normalized_status(match) in {
        "live",
        "in_progress",
        "ongoing",
        "1h",
        "2h",
        "ht",
        "et",
    }


def match_is_recently_finished(match):
    if not match_is_finished(match):
        return False

    kickoff = parse_kickoff(match)

    if kickoff is None:
        return False

    try:
        lookback_hours = max(1, int(os.getenv("LIVE_FINISHED_LOOKBACK_HOURS", "6")))
    except (TypeError, ValueError):
        lookback_hours = 6

    now = datetime.now(timezone.utc)
    return kickoff <= now <= kickoff + timedelta(hours=lookback_hours)


def compact_score(match):
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = match.get("home_score")
    away_score = match.get("away_score")

    if home_score is None:
        home_score = score.get("home")

    if away_score is None:
        away_score = score.get("away")

    if home_score is None or away_score is None:
        return ""

    return f"{to_persian_digits(home_score)} - {to_persian_digits(away_score)}"


def live_score_line(match):
    home = team_display(match, "home")
    away = team_display(match, "away")
    score = compact_score(match)

    if score:
        return f"{home['name']} {score} {away['name']}"

    return f"{home['name']} - {away['name']}"


def event_minute(event):
    minute = clean_value(event.get("display_minute") or event.get("raw_minute") or event.get("minute") or event.get("time"))
    return to_persian_digits(minute) if minute else ""


def event_player(event):
    return clean_value(
        event.get("player")
        or event.get("player_name")
        or event.get("playerName")
        or event.get("scorer")
        or event.get("goal_scorer")
        or event.get("card_player")
    )


def event_score_token(match):
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = clean_value(match.get("home_score") if match.get("home_score") is not None else score.get("home"))
    away_score = clean_value(match.get("away_score") if match.get("away_score") is not None else score.get("away"))
    return f"{home_score}_{away_score}" if home_score or away_score else "unknown"


def live_event_key(match, event, notification_type):
    provider = normalize_team_key(event.get("provider") or match.get("provider") or "worldcup2026")
    external_match_id = clean_value(
        event.get("external_match_id")
        or match.get("external_match_id")
        or match.get("raw_provider_match_id")
        or match_id(match)
    )
    raw_id = clean_value(event.get("id") or event.get("event_id") or event.get("eventId"))

    if raw_id:
        return f"{provider}:match_{external_match_id}:event_{raw_id}"

    side = scoring_side(event, match) or clean_value(event.get("team_side") or event.get("team") or event.get("side"))
    team = team_display(match, side) if side in {"home", "away"} else {"key": normalize_team_key(side)}
    player = normalize_team_key(event_player(event))
    minute = clean_value(event.get("display_minute") or event.get("raw_minute") or event.get("minute") or event.get("time"))
    event_type = live_event_type(event) or "unknown"

    return (
        f"{provider}:match_{external_match_id}:type_{event_type}:"
        f"min_{normalize_team_key(minute) or 'unknown'}:"
        f"team_{team['key'] or 'unknown'}:"
        f"player_{player or 'unknown'}:"
        f"score_{event_score_token(match)}"
    )


def build_match_started_message(match):
    return "\n".join(
        line
        for line in (
            "\U0001f534 \u0628\u0627\u0632\u06cc \u0634\u0631\u0648\u0639 \u0634\u062f",
            live_score_line(match),
        )
        if clean_value(line)
    )


def build_goal_message(match, event):
    side = scoring_side(event, match)
    scoring_team = team_display(match, side) if side in {"home", "away"} else {"name": clean_value(event.get("team_name"))}
    minute = event_minute(event)
    player = event_player(event)
    event_type = live_event_type(event)
    title = "\u26bd \u06af\u0644!"

    if event_type == "penalty_goal":
        title = "\u26bd \u06af\u0644 \u067e\u0646\u0627\u0644\u062a\u06cc!"
    elif event_type == "own_goal":
        title = "\u26bd \u06af\u0644 \u0628\u0647 \u062e\u0648\u062f\u06cc!"

    lines = [title]

    if scoring_team.get("name") and minute:
        lines.append(f"{scoring_team['name']} \u06af\u0644 \u0632\u062f - \u062f\u0642\u06cc\u0642\u0647 {minute}")
    elif scoring_team.get("name"):
        lines.append(f"{scoring_team['name']} \u06af\u0644 \u0632\u062f")
    elif minute:
        lines.append(f"\u062f\u0642\u06cc\u0642\u0647 {minute}")

    if player:
        lines.append(f"\u06af\u0644\u0632\u0646: {player}")

    score = live_score_line(match)
    if score:
        lines.append(f"\u0646\u062a\u06cc\u062c\u0647: {score}")

    return "\n".join(lines)


def build_red_card_message(match, event):
    side = scoring_side(event, match)
    team = team_display(match, side) if side in {"home", "away"} else {"name": clean_value(event.get("team_name"))}
    minute = event_minute(event)
    player = event_player(event)
    lines = ["\U0001f7e5 \u06a9\u0627\u0631\u062a \u0642\u0631\u0645\u0632"]

    if team.get("name") and minute:
        lines.append(f"\u0628\u0631\u0627\u06cc {team['name']} - \u062f\u0642\u06cc\u0642\u0647 {minute}")
    elif team.get("name"):
        lines.append(f"\u0628\u0631\u0627\u06cc {team['name']}")
    elif minute:
        lines.append(f"\u062f\u0642\u06cc\u0642\u0647 {minute}")

    if player:
        lines.append(f"\u0628\u0627\u0632\u06cc\u06a9\u0646: {player}")

    return "\n".join(lines)


def build_match_ended_message(match):
    return get_final_notification_text(match, "fa")


def localized_team_name(match, side, lang):
    if lang == "en":
        return clean_value(match.get(f"{side}_en") or match.get(f"{side}_team") or match.get(f"{side}_fa"))

    return clean_value(match.get(f"{side}_fa") or match.get(f"{side}_en") or match.get(f"{side}_team"))


def final_score_line(match, lang):
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = match.get("home_score")
    away_score = match.get("away_score")

    if home_score is None:
        home_score = score.get("home")

    if away_score is None:
        away_score = score.get("away")

    if lang == "fa":
        home_score = to_persian_digits(home_score)
        away_score = to_persian_digits(away_score)

    return (
        f"{localized_team_name(match, 'home', lang)} "
        f"{home_score} - {away_score} "
        f"{localized_team_name(match, 'away', lang)}"
    ).strip()


def final_penalty_summary(match, lang):
    provided = match.get("penalty_summary_en" if lang == "en" else "penalty_summary_fa")
    if clean_value(provided):
        return clean_value(provided)

    if match.get("win_method") != "penalty_shootout":
        return ""

    winner_side = clean_value(match.get("penalty_winner_side")).lower()
    winner_name = clean_value(
        match.get("penalty_winner_en" if lang == "en" else "penalty_winner_fa")
    )

    if not winner_name and winner_side in {"home", "away"}:
        winner_name = localized_team_name(match, winner_side, lang)

    if not winner_name:
        return ""

    if lang == "en":
        return f"{winner_name} won on penalties"

    winner_score = match.get("home_penalty_score" if winner_side == "home" else "away_penalty_score")
    loser_score = match.get("away_penalty_score" if winner_side == "home" else "home_penalty_score")
    score_text = ""

    if winner_score is not None and loser_score is not None:
        score_text = f" {to_persian_digits(winner_score)} - {to_persian_digits(loser_score)}"

    return f"{winner_name} در ضربات پنالتی{score_text} پیروز شد"


def get_final_notification_text(match, lang="fa"):
    title = "Full Time" if lang == "en" else "پایان بازی"
    lines = [title, final_score_line(match, lang)]
    penalty_summary = final_penalty_summary(match, lang)

    if penalty_summary:
        lines.append(penalty_summary)

    return "\n".join(line for line in lines if clean_value(line))


def send_live_notification_once(bot_app, telegram_id, match, notification_type, event_key, text):
    match_id_value = match_id(match)

    if match_id_value is None:
        return False

    if has_live_notification_been_sent(telegram_id, match_id_value, notification_type, event_key):
        return False

    event_marker = ":event_"
    if event_marker in event_key:
        raw_event_id = event_key.rsplit(event_marker, 1)[1]
        legacy_event_key = f"{notification_type}:event_{raw_event_id}"

        if has_live_notification_been_sent(
            telegram_id,
            match_id_value,
            notification_type,
            legacy_event_key,
        ):
            mark_live_notification_sent(
                telegram_id,
                match_id_value,
                notification_type,
                event_key,
            )
            return False

    if notification_dry_run():
        print(
            "DRY RUN live notification "
            f"type={notification_type} user={telegram_id} match={match_id_value} key={event_key}\n{text}"
        )
        return False

    try:
        event_loop = scheduler_state.get("event_loop")

        if event_loop is None or event_loop.is_closed():
            raise RuntimeError("Telegram application event loop is not available.")

        future = asyncio.run_coroutine_threadsafe(
            send_telegram_message(bot_app, telegram_id, text),
            event_loop,
        )
        future.result(timeout=30)
        mark_live_notification_sent(telegram_id, match_id_value, notification_type, event_key)
        print(
            "Sent live notification "
            f"type={notification_type} user={telegram_id} match={match_id_value} key={event_key}"
        )
        return True
    except Exception as error:
        print(
            "Failed live notification "
            f"type={notification_type} user={telegram_id} match={match_id_value} key={event_key}: {error}"
        )
        return False


def notify_relevant_users(bot_app, match, notification_type, event_key, text):
    for telegram_id in get_relevant_users_for_match(match):
        send_live_notification_once(bot_app, telegram_id, match, notification_type, event_key, text)


def notify_favorite_users_final(bot_app, match):
    favorites_by_user = get_all_favorite_teams_from_db()
    users_by_id = {user["telegram_id"]: user for user in get_all_users()}
    match_id_value = match_id(match)

    for telegram_id, favorites in favorites_by_user.items():
        if not user_favorite_for_match(favorites, match):
            continue

        language_code = str(users_by_id.get(telegram_id, {}).get("language_code") or "fa").lower()
        lang = "en" if language_code.startswith("en") else "fa"
        notification_key = f"final:{match_id_value}:{telegram_id}"
        send_once(
            bot_app,
            telegram_id,
            get_final_notification_text(match, lang),
            notification_key,
            match_id_value,
            "confirmed match finish notification",
        )


def final_confirmation_score(match):
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    return (
        match.get("home_score") if match.get("home_score") is not None else score.get("home"),
        match.get("away_score") if match.get("away_score") is not None else score.get("away"),
        match.get("home_penalty_score"),
        match.get("away_penalty_score"),
    )


def reset_final_confirmation(match_id_value, reason):
    if pending_final_confirmations.pop(match_id_value, None) is not None:
        print(f"[FINAL_NOTIFY_RESET] match_id={match_id_value} reason={reason}")


def process_final_confirmations(matches, bot_app):
    present_match_ids = set()

    for match in matches:
        match_id_value = match_id(match)

        if match_id_value is None:
            continue

        present_match_ids.add(match_id_value)

        if not is_definitely_finished(match):
            reset_final_confirmation(match_id_value, "active_or_not_final")
            continue

        if not has_final_score(match):
            reset_final_confirmation(match_id_value, "missing_final_score")
            continue

        if not match_is_recently_finished(match):
            reset_final_confirmation(match_id_value, "outside_recent_window")
            continue

        current_score = final_confirmation_score(match)
        confirmation = pending_final_confirmations.get(match_id_value)

        if confirmation is None:
            pending_final_confirmations[match_id_value] = {
                "first_seen_at": datetime.now(timezone.utc),
                "last_score": current_score,
                "count": 1,
                "confirmed": False,
            }
            print(f"[FINAL_NOTIFY_CONFIRM] match_id={match_id_value} count=1")
            continue

        if confirmation["last_score"] != current_score:
            print(f"[FINAL_NOTIFY_RESET] match_id={match_id_value} reason=score_changed")
            confirmation.update({
                "first_seen_at": datetime.now(timezone.utc),
                "last_score": current_score,
                "count": 1,
                "confirmed": False,
            })
            print(f"[FINAL_NOTIFY_CONFIRM] match_id={match_id_value} count=1")
            continue

        if confirmation["confirmed"]:
            continue

        confirmation["count"] += 1

        if confirmation["count"] >= 2:
            confirmation["confirmed"] = True
            print(f"[FINAL_NOTIFY_CONFIRMED] match_id={match_id_value} count={confirmation['count']}")
            notify_favorite_users_final(bot_app, match)

    for pending_match_id in set(pending_final_confirmations).difference(present_match_ids):
        reset_final_confirmation(pending_match_id, "missing_from_wrapper_response")


def check_live_match_notifications():
    try:
        check_live_match_notifications_once()
    except Exception as error:
        print(f"Scheduler check failed in check_live_match_notifications: {error}")


def check_live_match_notifications_once():
    if not live_notifications_enabled():
        return

    bot_app = scheduler_state["bot_app"]

    if bot_app is None:
        return

    matches = load_matches()
    live_matches = [match for match in matches if is_live_match(match)]
    process_final_confirmations(matches, bot_app)

    if not live_matches:
        return

    for match in live_matches:
        match_id_value = match_id(match)

        if match_id_value is None:
            continue

        notify_relevant_users(
            bot_app,
            match,
            "match_started",
            "started",
            build_match_started_message(match),
        )

        events = load_events(match_id_value)

        for event in events:
            event_type = live_event_type(event)

            if is_scoring_event(event):
                notify_relevant_users(
                    bot_app,
                    match,
                    "goal",
                    live_event_key(match, event, "goal"),
                    build_goal_message(match, event),
                )

            if event_type == "red_card":
                notify_relevant_users(
                    bot_app,
                    match,
                    "red_card",
                    live_event_key(match, event, "red_card"),
                    build_red_card_message(match, event),
                )

def seed_existing_match_notification_state():
    if scheduler_state["seeded_existing_live_notifications"]:
        return

    users = get_all_users()
    favorites_by_user = get_all_favorite_teams_from_db()
    seeded_count = 0

    for match in load_matches():
        match_id_value = match_id(match)

        if not match_id_value:
            continue

        is_started = match_has_started(match)
        is_finished = is_definitely_finished(match) and has_final_score(match)

        if not is_started and not is_finished:
            continue

        for user in users:
            telegram_id = user["telegram_id"]
            favorite = user_favorite_for_match(favorites_by_user.get(telegram_id, []), match)

            if is_started:
                suppress_notification_key(
                    user_start_key(match, telegram_id, favorite),
                    telegram_id=telegram_id,
                    match_id_value=match_id_value,
                )
                seeded_count += 1

            if is_finished:
                suppress_notification_key(
                    user_finished_key(match, telegram_id, favorite),
                    telegram_id=telegram_id,
                    match_id_value=match_id_value,
                )
                seeded_count += 1

        if not favorites_by_user or not (is_started or is_finished):
            continue

        events = load_events(match_id_value)
        goal_events = [
            event for event in events
            if (event.get("normalized_type") or event.get("type")) == "goal"
        ]

        for index, event in enumerate(goal_events):
            side = scoring_side(event, match)

            if side not in {"home", "away"}:
                continue

            scoring_team = team_display(match, side)

            for telegram_id, favorites in favorites_by_user.items():
                favorite = user_favorite_for_match(favorites, match)

                if not favorite:
                    continue

                favorite_team, _opponent = favorite_team_context(favorite, match)
                event_key = event_id(event, index)
                direction = "for" if scoring_team["key"] == favorite_team["key"] else "against"
                key = f"favorite_goal_{direction}:{match_id_value}:{event_key}:{favorite_team['key']}:{telegram_id}"
                suppress_notification_key(key, telegram_id=telegram_id, match_id_value=match_id_value)
                seeded_count += 1

    scheduler_state["seeded_existing_live_notifications"] = True
    print(f"Seeded existing match notification state without sending ({seeded_count} keys)")


def check_manual_reminders():
    bot_app = scheduler_state["bot_app"]
    reminders = scheduler_state["reminders"]

    if bot_app is None or reminders is None:
        print("Manual reminders skipped: missing bot or reminders.")
        return

    for telegram_id, user_reminders in list(reminders.items()):
        for match in user_reminders:
            if match.get("notified") or not should_notify(match):
                continue

            notification_key = f"manual:{telegram_id}:{match['id']}"

            if has_sent_notification(notification_key):
                print(f"Skipped duplicate notification: {notification_key}")
                continue

            text = build_match_message(match, "\u06cc\u0627\u062f\u0622\u0648\u0631\u06cc \u0645\u0633\u0627\u0628\u0642\u0647")

            if send_once(bot_app, telegram_id, text, notification_key, match["id"], "manual reminder"):
                mark_reminder_notified(telegram_id, match["id"])
                match["notified"] = True


def check_match_start_notifications():
    bot_app = scheduler_state["bot_app"]

    if bot_app is None:
        return

    users = get_all_users()
    favorites_by_user = get_all_favorite_teams_from_db()

    for match in load_matches():
        match_id_value = match_id(match)

        if not match_id_value or not match_has_started(match):
            continue

        for user in users:
            telegram_id = user["telegram_id"]
            favorite = user_favorite_for_match(favorites_by_user.get(telegram_id, []), match)

            if favorite:
                key = user_start_key(match, telegram_id, favorite)
                if notification_already_handled(f"global_match_start:{match_id_value}:{telegram_id}"):
                    print(f"Skipped duplicate notification: {key}")
                    continue
                text = f"{DEFAULT_STAR} \u0628\u0627\u0632\u06cc \u062a\u06cc\u0645 \u0645\u062d\u0628\u0648\u0628\u062a \u0634\u0631\u0648\u0639 \u0634\u062f\n{fixture_line(match)}"
                send_once(bot_app, telegram_id, text, key, match_id_value, "match start notification")
            else:
                key = f"global_match_start:{match_id_value}:{telegram_id}"
                if has_user_match_specific_notification("favorite_match_start", match, telegram_id):
                    print(f"Skipped duplicate notification: {key}")
                    continue
                text = f"\U0001f514 \u0628\u0627\u0632\u06cc \u0634\u0631\u0648\u0639 \u0634\u062f\n{fixture_line(match)}"
                send_once(bot_app, telegram_id, text, key, match_id_value, "match start notification")


def check_match_finished_notifications():
    bot_app = scheduler_state["bot_app"]

    if bot_app is None:
        return

    process_final_confirmations(load_matches(), bot_app)


def check_favorite_goal_notifications():
    bot_app = scheduler_state["bot_app"]

    if bot_app is None:
        return

    favorites_by_user = get_all_favorite_teams_from_db()

    if not favorites_by_user:
        return

    for match in load_matches():
        match_id_value = match_id(match)

        if not match_id_value or not (match_has_started(match) or match_is_finished(match)):
            continue

        events = load_events(match_id_value)
        goal_events = [
            event for event in events
            if (event.get("normalized_type") or event.get("type")) == "goal"
        ]

        if not goal_events:
            continue

        for index, event in enumerate(goal_events):
            side = scoring_side(event, match)

            if side not in {"home", "away"}:
                continue

            scoring_team = team_display(match, side)

            for telegram_id, favorites in favorites_by_user.items():
                favorite = user_favorite_for_match(favorites, match)

                if not favorite:
                    continue

                favorite_team, _opponent = favorite_team_context(favorite, match)
                event_key = event_id(event, index)

                if scoring_team["key"] == favorite_team["key"]:
                    key = f"favorite_goal_for:{match_id_value}:{event_key}:{favorite_team['key']}:{telegram_id}"
                    text = (
                        f"{DEFAULT_BALL} \u06af\u0644 \u0628\u0631\u0627\u06cc \u062a\u06cc\u0645 \u0645\u062d\u0628\u0648\u0628\u062a!\n"
                        f"{favorite_team['flag']} {favorite_team['name']}\n\n"
                        f"\u06af\u0644\u0632\u0646: {scorer_name(event)}\n\n"
                        f"{score_line(match)}"
                    )
                else:
                    key = f"favorite_goal_against:{match_id_value}:{event_key}:{favorite_team['key']}:{telegram_id}"
                    text = (
                        f"{DEFAULT_BALL} \u06af\u0644 \u0628\u0631\u0627\u06cc {scoring_team['name']} {scoring_team['flag']}\n"
                        f"\u06af\u0644\u0632\u0646: {scorer_name(event)}\n\n"
                        f"{score_line(match)}"
                    )

                send_once(bot_app, telegram_id, text, key, match_id_value, "favorite goal notification")


def check_all_notifications():
    print("Checking notifications...")

    try:
        check_manual_reminders()
    except Exception as error:
        print(f"Scheduler check failed in check_manual_reminders: {error}")


def start_scheduler(bot_app, reminders, favorite_teams, get_matches, get_events=None, event_loop=None):
    scheduler_state["bot_app"] = bot_app
    scheduler_state["reminders"] = reminders
    scheduler_state["favorite_teams"] = favorite_teams
    scheduler_state["get_matches"] = get_matches
    scheduler_state["get_events"] = get_events
    scheduler_state["event_loop"] = event_loop

    if not scheduler.running:
        scheduler.add_job(
            check_all_notifications,
            "interval",
            minutes=1,
            id="matchpulse_notifications",
            replace_existing=True,
        )
        scheduler.add_job(
            check_live_match_notifications,
            "interval",
            seconds=live_notification_interval_seconds(),
            id="matchpulse_live_notifications",
            replace_existing=True,
            max_instances=1,
        )
        scheduler.start()
        print("Scheduler started...")
