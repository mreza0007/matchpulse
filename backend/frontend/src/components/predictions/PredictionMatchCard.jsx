import { useState } from "react";
import TeamFlag from "../teams/TeamFlag.jsx";
import { formatTehranMatchDateTime } from "../../utils/dates.js";

const LEGACY_RESULT_LABELS = {
  home: "predictionLegacyHome",
  draw: "predictionLegacyDraw",
  away: "predictionLegacyAway",
};

function teamName(match, side, lang) {
  if (lang === "fa") {
    return match?.[`${side}_fa`] || match?.[`${side}_team_name_fa`] || match?.[`${side}_en`] || "";
  }
  return match?.[`${side}_en`] || match?.[`${side}_team_name_en`] || match?.[`${side}_fa`] || "";
}

function initialScore(prediction, side) {
  if (prediction?.prediction_type !== "exact_score") return "";
  const value = prediction?.[`${side}_score`];
  return Number.isInteger(value) && value >= 0 ? String(value) : "";
}

export default function PredictionMatchCard({
  competition,
  errorMessage,
  isLocked,
  isSaving,
  lang,
  match,
  onSave,
  prediction,
  saveWasSuccessful,
  t,
}) {
  const [homeScore, setHomeScore] = useState(() => initialScore(prediction, "home"));
  const [awayScore, setAwayScore] = useState(() => initialScore(prediction, "away"));
  const [isEditingLegacy, setIsEditingLegacy] = useState(false);
  const kickoff = formatTehranMatchDateTime(match, lang).compact || t.dateUnavailable;
  const home = teamName(match, "home", lang);
  const away = teamName(match, "away", lang);
  const isLegacyResult = prediction?.prediction_type === "result";
  const legacyLabelKey = LEGACY_RESULT_LABELS[prediction?.prediction];
  const canSubmit = /^\d+$/.test(homeScore) && /^\d+$/.test(awayScore) && !isSaving && !isLocked;
  const updateScore = (setter) => (event) => {
    const value = event.target.value;
    if (/^\d{0,2}$/.test(value)) setter(value);
  };

  const submit = (event) => {
    event.preventDefault();
    if (!canSubmit) return;
    onSave(match.id, Number(homeScore), Number(awayScore));
  };

  return (
    <article className={`prediction-match-card ${isLocked ? "locked" : ""}`}>
      <div className="prediction-match-context">
        <span>{competition.name}</span>
        <time>{kickoff}</time>
      </div>

      <div className="prediction-teams">
        <div>
          <TeamFlag
            flagEmoji={match.home_flag}
            logoUrl={match.home_logo}
            teamName={match.home_en || home}
          />
          <strong>{home}</strong>
        </div>
        <span>{t.vs}</span>
        <div>
          <TeamFlag
            flagEmoji={match.away_flag}
            logoUrl={match.away_logo}
            teamName={match.away_en || away}
          />
          <strong>{away}</strong>
        </div>
      </div>

      {isLegacyResult && !isEditingLegacy ? (
        <div className="prediction-legacy-state">
          <span>{t.predictionLegacyLabel}: <strong>{t[legacyLabelKey] || t.unavailable}</strong></span>
          {!isLocked && (
            <button onClick={() => setIsEditingLegacy(true)} type="button">
              {t.predictionEditExactScore}
            </button>
          )}
        </div>
      ) : (
        <form className="prediction-score-form" onSubmit={submit}>
          <label>
            <span>{t.predictionHomeScore}</span>
            <input
              aria-label={`${t.predictionHomeScore} ${home}`}
              disabled={isLocked || isSaving}
              inputMode="numeric"
              onChange={updateScore(setHomeScore)}
              pattern="[0-9]*"
              value={homeScore}
            />
          </label>
          <span aria-hidden="true">–</span>
          <label>
            <span>{t.predictionAwayScore}</span>
            <input
              aria-label={`${t.predictionAwayScore} ${away}`}
              disabled={isLocked || isSaving}
              inputMode="numeric"
              onChange={updateScore(setAwayScore)}
              pattern="[0-9]*"
              value={awayScore}
            />
          </label>
          <button disabled={!canSubmit} type="submit">
            {isSaving ? t.predictionSaving : prediction ? t.predictionUpdate : t.predictionSubmit}
          </button>
        </form>
      )}

      <div className="prediction-card-status" aria-live="polite">
        {isLocked && <span className="error">{errorMessage || t.predictionDeadlinePassed}</span>}
        {!isLocked && errorMessage && <span className="error">{errorMessage}</span>}
        {!isLocked && !errorMessage && saveWasSuccessful && (
          <span className="success">{t.predictionSaved}</span>
        )}
        {!isLocked && !errorMessage && prediction?.points_awarded != null && (
          <span>{t.predictionEarnedPoints}: {prediction.points_awarded}</span>
        )}
        {!isLocked && !errorMessage && prediction && prediction?.points_awarded == null && (
          <span>{t.predictionPending}</span>
        )}
      </div>
    </article>
  );
}
