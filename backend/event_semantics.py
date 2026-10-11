"""Conservative decision evidence shared by adapters and notifications."""
import re


def confirmed_disallowed_goal(event):
    if not isinstance(event, dict):
        return False
    event_type = str(event.get("normalized_type") or event.get("type") or "").lower()
    if event_type in {"disallowed_goal", "var_disallowed_goal", "goal_disallowed"}:
        return True
    for field in ("description", "raw_type_label", "typeTitle", "eventTitle", "decisionTitle", "decision", "outcome"):
        text = str(event.get(field) or "").strip().lower()
        if re.fullmatch(r"(?:goal disallowed|disallowed goal|goal overturned|overturned goal)(?: after var review)?[.!]?", text):
            return True
        if re.fullmatch(r"گل\s+(?:مردود(?:\s+شده)?|رد\s+شده)[.!]?", text):
            return True
    return False
