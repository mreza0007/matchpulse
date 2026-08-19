ALLOWED_RESULTS = frozenset({"home", "draw", "away"})
CORRECT_PREDICTION_POINTS = 3


def prediction_identity(prediction):
    return (
        prediction["competition_key"],
        prediction["season_key"],
        prediction["match_id"],
    )


def canonical_prediction_result(match):
    if not isinstance(match, dict):
        return None

    status = str(match.get("status") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if match.get("is_finished") is not True and status not in {
        "finished", "finish", "ft", "full_time", "fulltime", "completed", "complete", "final",
    }:
        return None

    result = str(match.get("result") or "").strip().lower()
    if result in ALLOWED_RESULTS:
        return result

    penalty_winner = str(match.get("penalty_winner_side") or "").strip().lower()
    if penalty_winner in {"home", "away"}:
        return penalty_winner

    score_source = str(match.get("score_source") or "").strip().lower()
    trusted_score_sources = {
        "raw_final", "raw_score", "events", "scorers", "worldcup_wrapper", "varzesh3", "score_override",
    }
    if score_source not in trusted_score_sources:
        return None

    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    if home_score is None:
        home_score = score.get("home")
    if away_score is None:
        away_score = score.get("away")

    try:
        home_score = int(home_score)
        away_score = int(away_score)
    except (TypeError, ValueError):
        return None

    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def evaluate_prediction(prediction, match):
    result = canonical_prediction_result(match)
    if result is None:
        return {"status": "pending", "points": 0}
    if prediction.get("predicted_result") == result:
        return {"status": "correct", "points": CORRECT_PREDICTION_POINTS}
    return {"status": "wrong", "points": 0}


def evaluate_predictions(predictions, matches_by_identity):
    evaluations = []
    stats = {"points": 0, "correct": 0, "wrong": 0, "pending": 0, "total": len(predictions)}

    for prediction in predictions:
        evaluation = evaluate_prediction(
            prediction, matches_by_identity.get(prediction_identity(prediction))
        )
        evaluations.append(evaluation)
        stats[evaluation["status"]] += 1
        stats["points"] += evaluation["points"]

    return evaluations, stats


def calculate_prediction_stats(predictions, matches_by_identity):
    return evaluate_predictions(predictions, matches_by_identity)[1]


def resolve_prediction_matches(
    predictions, resolver, provider_error_type, should_resolve=None
):
    matches_by_identity = {}
    evaluation_errors = 0

    for prediction in predictions:
        identity = prediction_identity(prediction)
        if identity in matches_by_identity:
            continue
        if should_resolve is not None and not should_resolve(prediction):
            matches_by_identity[identity] = None
            continue
        try:
            matches_by_identity[identity] = resolver(*identity)
        except provider_error_type:
            matches_by_identity[identity] = None
            evaluation_errors += 1

    return matches_by_identity, evaluation_errors


def public_display_name(user):
    username = str((user or {}).get("username") or "").strip().lstrip("@")
    if username:
        return f"@{username}"

    first_name = str((user or {}).get("first_name") or "").strip()
    last_name = str((user or {}).get("last_name") or "").strip()
    if first_name:
        return f"{first_name} {last_name[0]}." if last_name else first_name
    return "Anonymous"
