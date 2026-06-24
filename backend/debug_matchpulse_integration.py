from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from services.worldcup_adapter import (
    get_match_events_from_worldcup_wrapper,
    get_matches_from_worldcup_wrapper,
    normalize_match,
    parse_match_datetime,
    source_timezone_for_match,
    TEHRAN_TZ,
)


def print_match_time(label, match):
    normalized = normalize_match(match)
    payload = {
            "kickoff_iso": normalized.get("kickoff_iso"),
            "kickoff_utc": normalized.get("kickoff_utc"),
            "kickoff_ts": normalized.get("kickoff_ts"),
            "date_key": normalized.get("date_key"),
            "weekday_fa": normalized.get("weekday_fa"),
            "date_label_fa": normalized.get("date_label_fa"),
            "time_iran": normalized.get("time_iran"),
            "stadium_id": normalized.get("stadium_id"),
            "source_timezone": normalized.get("source_timezone"),
            "source_local_date": normalized.get("local_date"),
            "tehran_datetime": (
                parse_match_datetime(match).astimezone(TEHRAN_TZ).isoformat()
                if parse_match_datetime(match)
                else None
            ),
    }
    print(label, json.dumps(payload, ensure_ascii=True))


def main():
    print_match_time(
        "06/23/2026 20:00 default source local_date",
        {
            "id": 1,
            "status": "upcoming",
            "local_date": "06/23/2026 20:00",
        },
    )
    print_match_time(
        "06/23/2026 20:00 stadium 1 venue local_date",
        {
            "id": 1,
            "status": "upcoming",
            "local_date": "06/23/2026 20:00",
            "stadium_id": "1",
        },
    )

    matches = get_matches_from_worldcup_wrapper()
    finished_matches = [match for match in matches if match.get("is_finished") is True]
    upcoming_matches = [match for match in matches if match.get("is_upcoming") is True]
    print(
        "match status counts",
        json.dumps(
            {
                "total": len(matches),
                "finished": len(finished_matches),
                "upcoming": len(upcoming_matches),
            },
            ensure_ascii=True,
        ),
    )
    print(
        "first 5 finished",
        json.dumps(
            [
                {
                    "id": match.get("id"),
                    "teams": f"{match.get('home_en')} vs {match.get('away_en')}",
                    "status": match.get("status"),
                    "is_finished": match.get("is_finished"),
                    "is_upcoming": match.get("is_upcoming"),
                    "kickoff_ts": match.get("kickoff_ts"),
                }
                for match in finished_matches[:5]
            ],
            ensure_ascii=True,
        ),
    )
    print(
        "status checks",
        json.dumps(
            [
                {
                    "id": match.get("id"),
                    "teams": f"{match.get('home_en')} vs {match.get('away_en')}",
                    "status": match.get("status"),
                    "is_finished": match.get("is_finished"),
                    "is_upcoming": match.get("is_upcoming"),
                    "kickoff_ts": match.get("kickoff_ts"),
                }
                for match in matches
                if (
                    f"{match.get('home_en')} vs {match.get('away_en')}" in {
                        "New Zealand vs Egypt",
                        "Scotland vs Brazil",
                    }
                    or (
                        "Colombia" in f"{match.get('home_en')} vs {match.get('away_en')}"
                        and "Congo" in f"{match.get('home_en')} vs {match.get('away_en')}"
                    )
                )
            ],
            ensure_ascii=True,
        ),
    )

    for match in matches:
        teams = f"{match.get('home_en')} vs {match.get('away_en')}"
        if (
            "Colombia" in teams
            or "Congo" in teams
            or "Brazil" in teams
            or "Scotland" in teams
            or "Switzerland" in teams
            or "Canada" in teams
        ):
            print_match_time(teams, match)

    event_match = next((match for match in matches if match.get("is_finished")), None)
    if event_match is None:
        event_match = next(
            (
                match
                for match in matches
                if match.get("external_match_id") or match.get("raw_provider_match_id")
            ),
            None,
        )

    if event_match:
        events_payload = get_match_events_from_worldcup_wrapper(event_match.get("id"))
        print(
            "match events",
            json.dumps({
                "internal_match_id": event_match.get("id"),
                "external_match_id": events_payload.get("external_match_id"),
                "provider": events_payload.get("provider"),
                "event_count": len(events_payload.get("events") or []),
                "source_timezone": source_timezone_for_match(event_match).key,
            }, ensure_ascii=True),
        )
    else:
        print("match events", json.dumps({"event_count": 0, "warning": "no provider-backed match found"}, ensure_ascii=True))


if __name__ == "__main__":
    main()
