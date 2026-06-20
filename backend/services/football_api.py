import os
import requests
from datetime import datetime, timedelta

BASE_URL = "https://api.football-data.org/v4"

TOKEN = os.getenv("FOOTBALL_API_TOKEN")


headers = {
    "X-Auth-Token": TOKEN
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

    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print("[FOOTBALL_API_ERROR]", str(e))
        return {"matches": []}


# 🔥 فقط live + finished
def get_live_and_finished():
    try:
        res = requests.get(
            f"{BASE_URL}/matches?status=LIVE,FINISHED",
            headers=headers,
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print("[FOOTBALL_API_ERROR]", str(e))
        return {"matches": []}