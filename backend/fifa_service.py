import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FOOTBALL_API_KEY")

HEADERS = {
    "x-apisports-key": API_KEY
}

BASE_URL = "https://v3.football.api-sports.io"


def get_worldcup_teams():
    url = f"{BASE_URL}/teams"

    params = {
        "league": 1,
        "season": 2026
    }

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    return response.json()


def get_worldcup_matches():
    url = f"{BASE_URL}/fixtures"

    params = {
        "league": 1,
        "season": 2026
    }

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    return response.json()