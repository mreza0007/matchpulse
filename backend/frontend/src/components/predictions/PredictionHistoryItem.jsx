const LEGACY_RESULT_LABELS = {
  home: "predictionLegacyHome",
  draw: "predictionLegacyDraw",
  away: "predictionLegacyAway",
};

const EVALUATION_LABELS = {
  pending: "predictionEvaluationPending",
  correct: "predictionCorrect",
  wrong: "predictionWrong",
};

export default function PredictionHistoryItem({ item, t }) {
  const isExactScore = item?.prediction_type === "exact_score";
  const hasExactScore = Number.isInteger(item?.home_score) && Number.isInteger(item?.away_score);
  const resultLabel = t[LEGACY_RESULT_LABELS[item?.predicted_result]] || t.unavailable;
  const predictionLabel = isExactScore
    ? (hasExactScore ? `${item.home_score} - ${item.away_score}` : t.unavailable)
    : resultLabel;
  const evaluation = item?.evaluation || {};
  const evaluationLabel = t[EVALUATION_LABELS[evaluation.status]] || t.predictionEvaluationPending;

  return (
    <article className="prediction-history-item">
      <div>
        <span>{isExactScore ? t.predictionExactScore : t.predictionLegacyLabel}</span>
        <strong>{predictionLabel}</strong>
      </div>
      <div className={`prediction-history-evaluation ${evaluation.status || "pending"}`}>
        <strong>{evaluationLabel}</strong>
        {evaluation.points != null && (
          <span>{t.predictionHistoryPoints}: {evaluation.points}</span>
        )}
      </div>
    </article>
  );
}
