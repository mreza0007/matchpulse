"""Telegram push policy only. Never remove events from Mini App timelines.

Use canonical types or explicit, finite decision phrases. Numeric provider codes,
keyword co-occurrence and scoring booleans alone are not evidence of a key moment.
"""
import re

from event_semantics import confirmed_disallowed_goal

GOALS = frozenset({"goal", "own_goal", "penalty_goal"})
LABELS = {
    "penalty_awarded": ("پنالتی اعلام شد", "Penalty awarded"),
    "penalty_missed": ("پنالتی ناموفق", "Penalty unsuccessful"),
    "var_review_goal": ("بررسی گل با VAR", "VAR goal review"),
    "var_review_penalty": ("بررسی پنالتی با VAR", "VAR penalty review"),
    "var_review_red_card": ("بررسی کارت قرمز با VAR", "VAR red-card review"),
    "goal_disallowed": ("گل مردود شد", "Goal disallowed"),
    "goal_confirmed": ("گل تأیید شد", "Goal confirmed"),
    "penalty_overturned": ("تصمیم پنالتی لغو شد", "Penalty overturned"),
    "red_card_upheld": ("کارت قرمز تأیید شد", "Red card upheld"),
    "red_card_cancelled": ("کارت قرمز لغو شد", "Red card cancelled"),
}
PHRASES = {
    "penalty_awarded": ("penalty awarded", "penalty given", "پنالتی اعلام شد", "اعلام پنالتی"),
    "penalty_missed": ("penalty missed", "missed penalty", "penalty saved", "saved penalty", "penalty unsuccessful", "پنالتی از دست رفت", "پنالتی مهار شد", "پنالتی ناموفق"),
    "goal_disallowed": ("goal disallowed", "disallowed goal", "goal overturned", "گل مردود", "گل مردود شده", "گل مردود شد", "گل رد شده"),
    "goal_confirmed": ("goal confirmed", "goal stands", "goal upheld", "گل تایید شد", "تایید گل"),
    "penalty_overturned": ("penalty overturned", "penalty cancelled", "penalty canceled", "no penalty", "پنالتی لغو شد", "لغو پنالتی"),
    "red_card_upheld": ("red card upheld", "red card confirmed", "کارت قرمز تایید شد", "تایید کارت قرمز"),
    "red_card_cancelled": ("red card overturned", "red card cancelled", "red card canceled", "کارت قرمز لغو شد", "لغو کارت قرمز"),
    "var_review_goal": ("var goal review", "var review for goal", "goal under var review", "بررسی گل با var", "بازبینی ویدئویی گل"),
    "var_review_penalty": ("var penalty review", "var review for penalty", "penalty under var review", "بررسی پنالتی با var", "بازبینی ویدئویی پنالتی"),
    "var_review_red_card": ("var red card review", "var review for red card", "red card under var review", "بررسی کارت قرمز با var", "بازبینی ویدئویی کارت قرمز"),
}


def evidence_texts(event):
    seen = set()
    for _ in range(4):
        if not isinstance(event, dict) or id(event) in seen:
            break
        seen.add(id(event))
        for field in ("description", "description_fa", "raw_type_label", "typeTitle", "eventTitle", "decisionTitle", "decision", "outcome"):
            value = event.get(field)
            if isinstance(value, str) and value.strip():
                text = " ".join(value.lower().replace("تأیید", "تایید").split())
                text = re.sub(r"^var\s*[:–-]\s*", "", text)
                text = re.sub(r" after var review[.!]?$", "", text)
                if not text.startswith(("بررسی", "بازبینی")):
                    text = re.sub(r" با var[.!]?$", "", text)
                yield text.rstrip(".!")
        event = event.get("raw_event")


def classify_key_moment(event):
    if not isinstance(event, dict):
        return None
    event_type = str(event.get("normalized_type") or event.get("event_type") or event.get("type") or "").lower().replace("-", "_")
    # Ordinary timeline events stay silent even if a stray scoring flag is true.
    if event_type in {"yellow_card", "substitution", "corner", "offside", "foul"}:
        return None
    texts = set(evidence_texts(event))
    decisions = {kind for kind, phrases in PHRASES.items() if texts.intersection(phrases)}
    if confirmed_disallowed_goal(event):
        decisions.add("goal_disallowed")
    outcomes = {kind for kind in decisions if not kind.startswith("var_review_")}
    reviews = decisions - outcomes
    if outcomes:
        if len(outcomes) != 1:
            return None  # Conflicting verdicts are not a referee decision.
        outcome = outcomes.pop()
        subject = "red_card" if outcome.startswith("red_card_") else outcome.split("_")[0]
        if any(review != "var_review_" + subject for review in reviews):
            return None
        # A retained review label is not a conflict with its definitive outcome.
        return outcome
    if reviews:
        return reviews.pop() if len(reviews) == 1 else None
    if event_type == "var":
        subjects = {kind for text, kind in {"goal": "var_review_goal", "گل": "var_review_goal",
            "penalty": "var_review_penalty", "پنالتی": "var_review_penalty",
            "red card": "var_review_red_card", "کارت قرمز": "var_review_red_card"}.items() if text in texts}
        return subjects.pop() if len(subjects) == 1 else None
    if event_type in {"var", "other", "penalty_event"}:
        return None
    if any(re.search(r"\?|\b(?:possible|pending|checking|review)\b", text) for text in texts):
        return None
    if event_type in GOALS:
        return "goal" if event.get("is_scoring_event") is not False else None
    if event_type in {"red_card", "second_yellow_red"}:
        return "red_card"
    if event_type in {"missed_penalty", "penalty_missed", "penalty_saved"}:
        return "penalty_missed"
    if event_type == "penalty_awarded":
        return "penalty_awarded"
    if event_type == "halftime":
        return "halftime"
    return None
