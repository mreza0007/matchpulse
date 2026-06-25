from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from services.worldcup_adapter import (
    can_show_event_button,
    can_show_in_results,
    event_button_visibility,
    get_match_events_from_worldcup_wrapper,
    get_matches_from_worldcup_wrapper,
    normalize_match,
    parse_match_datetime,
    source_timezone_for_match,
    TEHRAN_TZ,
)
from real_data_service import get_real_matches


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


REGRESSION_MATCH_IDS = [1, 2, 19, 29, 35, 37, 38, 40, 44, 49, 51]


def score_text(match):
    home_score = match.get("home_score")
    away_score = match.get("away_score")

    if home_score is None or away_score is None:
        return ""

    return f"{home_score}-{away_score}"


def print_match_audit(matches, event_counts=None):
    event_counts = event_counts or {}
    print("full matchpulse integration audit")
    print(
        "\t".join(
            [
                "internal_id",
                "date",
                "home",
                "away",
                "status",
                "normalized_status",
                "score",
                "score_source",
                "provider",
                "external_match_id",
                "can_show_in_results",
                "can_show_event_button",
                "event_id_resolve_method",
                "event_count",
            ]
        )
    )
    for match in matches:
        event_button, event_reason = event_button_visibility(match)
        event_count = event_counts.get(match.get("id"), len(match.get("events") or []))
        row = [
            match.get("id"),
            match.get("kickoff_iso") or match.get("date_iran") or match.get("local_date"),
            match.get("home_en"),
            match.get("away_en"),
            match.get("status"),
            normalize_match(match).get("status") if match else "",
            score_text(match),
            match.get("score_source"),
            match.get("provider"),
            match.get("external_match_id") or match.get("raw_provider_match_id") or "",
            can_show_in_results(match),
            event_button,
            match.get("event_id_resolution_method") or ("existing" if match.get("external_match_id") else "failed"),
            event_count,
        ]
        print("\t".join(str(value) for value in row))
        print(
            "[RESULTS_AUDIT] "
            f"id={match.get('id')} teams={match.get('home_en')} vs {match.get('away_en')} "
            f"status={match.get('status')} score_source={match.get('score_source')} "
            f"visible={can_show_in_results(match)} event_button={event_button} "
            f"external={match.get('external_match_id') or match.get('raw_provider_match_id') or ''}"
        )
        print(
            "[EVENT_BUTTON_AUDIT] "
            f"id={match.get('id')} teams={match.get('home_en')} vs {match.get('away_en')} "
            f"can_show={event_button} reason={event_reason}"
        )


def assert_regression_checks(matches):
    by_id = {match.get("id"): match for match in matches}
    required_old_ids = [1, 19, 35]
    finished_count = sum(1 for match in matches if match.get("is_finished") is True)

    for match_id in required_old_ids:
        match = by_id.get(match_id)
        assert match is not None, f"id={match_id} missing"
        assert can_show_in_results(match), f"id={match_id} should appear in Results"
        assert can_show_event_button(match), f"id={match_id} should show event button"

    upcoming_with_event_button = [
        match.get("id")
        for match in matches
        if match.get("is_upcoming") is True and can_show_event_button(match)
    ]
    assert not upcoming_with_event_button, f"upcoming matches have event buttons: {upcoming_with_event_button}"

    for match_id in [40, 49]:
        match = by_id.get(match_id)
        assert match is not None, f"id={match_id} missing"
        assert can_show_event_button(match), f"id={match_id} should still show event button"

    print(
        "regression checks",
        json.dumps(
            {
                "finished_count": finished_count,
                "required_old_ids": required_old_ids,
                "upcoming_with_event_button": upcoming_with_event_button,
                "mapped_boundary_ids": [40, 49],
            },
            ensure_ascii=True,
        ),
    )


def collect_event_counts(matches):
    event_counts = {}
    by_id = {match.get("id"): match for match in matches}

    for match_id in REGRESSION_MATCH_IDS:
        match = by_id.get(match_id)

        if not match or not can_show_event_button(match):
            event_counts[match_id] = 0
            continue

        payload = get_match_events_from_worldcup_wrapper(match_id)
        event_counts[match_id] = len(payload.get("events") or [])
        print(
            "[EVENT_RESOLVE_AUDIT] "
            f"id={match_id} teams={match.get('home_en')} vs {match.get('away_en')} "
            f"external={payload.get('external_match_id') or ''} "
            f"method={match.get('event_id_resolution_method') or 'request'} "
            f"event_count={event_counts[match_id]}"
        )

    return event_counts


def print_audit_summary(matches, event_counts):
    missing_external_before_uruguay = [
        match.get("id")
        for match in matches
        if (match.get("id") or 0) < 40
        and not (match.get("external_match_id") or match.get("raw_provider_match_id"))
    ]
    old_matches_without_event_button = [
        match.get("id")
        for match in matches
        if (match.get("id") or 0) < 40 and can_show_in_results(match) and not can_show_event_button(match)
    ]
    summary = {
        "total": len(matches),
        "results_visible": sum(1 for match in matches if can_show_in_results(match)),
        "finished": sum(1 for match in matches if match.get("is_finished") is True),
        "pending_result": sum(1 for match in matches if match.get("status") == "pending_result"),
        "upcoming": sum(1 for match in matches if match.get("is_upcoming") is True),
        "missing_external_before_uruguay": len(missing_external_before_uruguay),
        "missing_external_before_uruguay_ids": missing_external_before_uruguay,
        "event_button_visible_count": sum(1 for match in matches if can_show_event_button(match)),
        "old_matches_without_event_button": len(old_matches_without_event_button),
        "old_matches_without_event_button_ids": old_matches_without_event_button,
        "regression_event_counts": event_counts,
    }
    print("audit summary", json.dumps(summary, ensure_ascii=True))


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
    service_matches = get_real_matches(status="all")
    finished_matches = [match for match in matches if match.get("is_finished") is True]
    upcoming_matches = [match for match in matches if match.get("is_upcoming") is True]
    pending_matches = [match for match in service_matches if match.get("status") == "pending_result"]
    print(
        "match status counts",
        json.dumps(
            {
                "total": len(matches),
                "finished": len(finished_matches),
                "upcoming": len(upcoming_matches),
                "service_total": len(service_matches),
                "service_finished": sum(1 for match in service_matches if match.get("is_finished") is True),
                "service_live": sum(1 for match in service_matches if match.get("is_live") is True),
                "service_upcoming": sum(1 for match in service_matches if match.get("is_upcoming") is True),
                "service_pending": len(pending_matches),
            },
            ensure_ascii=True,
        ),
    )
    event_counts = collect_event_counts(service_matches)
    assert_regression_checks(service_matches)
    print_match_audit(service_matches, event_counts)
    print_audit_summary(service_matches, event_counts)
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
