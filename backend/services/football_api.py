import os
import requests
from datetime import datetime, timedelta

BASE_URL = "https://api.football-data.org/v4"


def is_configured():
    return bool(os.getenv("FOOTBALL_API_TOKEN"))


def get_headers():
    token = os.getenv("FOOTBALL_API_TOKEN")

    if not token:
        return None

    return {
        "X-Auth-Token": token,
    }


# 🔥 گرفتن همه بازی‌ها در بازه زمانی کوتاه
def get_matches(date_from=None, date_to=None):
    if not date_from:
        date_from = datetime.utcnow().date().isoformat()
    if not date_to:
        date_to = (datetime.utcnow().date() + timedelta(days=1)).isoformat()

    url = f"{BASE_URL}/matches"

    params = {
        "dateFrom": date_from,
        "dateTo": date_to
    }

    headers = get_headers()

    if headers is None:
        print("[FOOTBALL_API_WARNING] FOOTBALL_API_TOKEN is not configured.")
        return {
            "ok": False,
            "message": "FOOTBALL_API_TOKEN is not configured",
            "matches": [],
        }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        data["ok"] = True
        return data
    except Exception as e:
        print("[FOOTBALL_API_ERROR]", str(e))
        return {
            "ok": False,
            "message": "football-data.org request failed",
            "matches": [],
        }


# 🔥 فقط live + finished
def get_live_and_finished():
    headers = get_headers()

    if headers is None:
        print("[FOOTBALL_API_WARNING] FOOTBALL_API_TOKEN is not configured.")
        return {
            "ok": False,
            "message": "FOOTBALL_API_TOKEN is not configured",
            "matches": [],
        }

    try:
        res = requests.get(
            f"{BASE_URL}/matches?status=LIVE,FINISHED",
            headers=headers,
            timeout=10
        )
        res.raise_for_status()
        data = res.json()
        data["ok"] = True
        return data
    except Exception as e:
        print("[FOOTBALL_API_ERROR]", str(e))
        return {
            "ok": False,
            "message": "football-data.org request failed",
            "matches": [],
        }
