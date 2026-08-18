import EventRow from "./EventRow.jsx";
import TeamFlag from "../teams/TeamFlag.jsx";
import { formatTehranMatchDateTime } from "../../utils/dates.js";
import {
  canShowEvents,
  getMatchScore,
  getMatchStatus,
  getPenaltySummary,
  getPredictionLabel,
  isFutureMatchStatus,
  isLiveMatch,
  isPredictionLocked,
} from "../../utils/matches.js";
import { getLocalizedTeamName, normalizeTeamKey } from "../../utils/teams.js";

function PenaltySummary({ match, lang }) {
  const summary = getPenaltySummary(match, lang);
  if (!summary) return null;

  return (
    <div className="penalty-summary">
      {summary}
    </div>
  );
}

export default function MatchCard({
  match,
  t,
  showReminder = true,
  onReminderToggle,
  isReminderActive = false,
  homeTeam,
  awayTeam,
  favoriteTeamIds,
  favoriteTeamKeys,
  onFavoriteToggle,
  lang,
  onDetailsClick,
  isExpanded = false,
  events = [],
  isLoadingEvents = false,
  eventsUnavailable = false,
  eventsFailed = false,
  isScoreChanged = false,
  variant = "standard",
  prediction = "",
  onPredictionSelect,
  isPredictionSaving = false,
  predictionWasSaved = false,
  predictionSaveFailed = false,
  predictionForceLocked = false,
  showFavorites = true,
  showPredictions = true,
  showEvents = true,
}) {
  const matchStatus = getMatchStatus(match, lang, t);
  const isLive = isLiveMatch(match);
  const matchScoreValue = getMatchScore(match);
  const matchScore =
    matchStatus.key === "upcoming" || matchStatus.key === "pending_result"
      ? ""
      : matchScoreValue || (matchStatus.key === "live" ? "0 - 0" : "");
  const homeName = getLocalizedTeamName(match, "home", lang);
  const awayName = getLocalizedTeamName(match, "away", lang);
  const shouldShowScoreFallback = !matchScore && ["finished", "pending_result"].includes(matchStatus.key);
  const matchDateTime = formatTehranMatchDateTime(match, lang);
  const canViewEvents = showEvents && canShowEvents(match);
  const predictionLocked = predictionForceLocked || isPredictionLocked(match);
  const showPrediction = isFutureMatchStatus(match) || Boolean(prediction);
  const stopCardClick = (event) => event.stopPropagation();
  const renderTeamName = (name, flag, englishName, team) => {
    const isFavorite = team
      ? favoriteTeamIds.has(String(team.id)) ||
        favoriteTeamKeys.has(normalizeTeamKey(team.team_key || team.name_en || team.name_fa || team.team_name || team.id))
      : false;

    return (
      <strong className="team-name">
        <TeamFlag
          flagEmoji={flag}
          logoUrl={team?.logo || team?.logo_url || ""}
          teamName={englishName}
        />
        {name}
        {showFavorites && team && (
          <button
            className={`favorite-star ${isFavorite ? "active" : ""}`}
            aria-label={isFavorite ? t.removeFavorite : t.addFavorite}
            onClick={(event) => {
              event.stopPropagation();
              onFavoriteToggle(team);
            }}
          >
            {isFavorite ? "\u2605" : "\u2606"}
          </button>
        )}
      </strong>
    );
  };

  return (
    <article
      className={`match-card ${variant === "hero" ? "hero-match-card" : ""} ${isLive ? "live-match" : ""} ${isExpanded ? "selected" : ""}`}
    >
      <div className="match-top">
        <div className="match-top-main">
          <span className="match-date">{matchDateTime.date}</span>
          <span className="match-stage">{match.stage_label || match.stage}</span>
        </div>
        {isLive && variant !== "hero" && <span className="match-status live live-pulse">{matchStatus.label}</span>}
      </div>

      <div className="match-score-block">
        <div className="teams">
          {renderTeamName(homeName, match.home_flag, match.home_en, homeTeam)}
          <span
            className={
              matchScore
                ? `match-score ${isScoreChanged ? "score-changed" : ""}`
                : shouldShowScoreFallback
                  ? "match-score-pending"
                  : "match-vs"
            }
          >
            {matchScore || (shouldShowScoreFallback ? t.scorePending : t.vs)}
          </span>
          {renderTeamName(awayName, match.away_flag, match.away_en, awayTeam)}
        </div>
        <PenaltySummary match={match} lang={lang} />
      </div>

      <div className="match-meta-grid">
        <span>🕒 {matchDateTime.time}</span>
        {match.group && (
          <span>
            🏆 {t.group} {match.group}
          </span>
        )}
        <span>🏟 {match.stadium}</span>
        <span>📍 {match.city}</span>
      </div>

      {match.result && match.score_source !== "football-data.org" && (
        <div className="match-info">
          <span>📊 {match.result}</span>
        </div>
      )}

      {showPredictions && showPrediction && (
        <div className={`prediction-panel ${predictionLocked ? "locked" : ""}`}>
          <div className="prediction-heading">
            <strong>{t.prediction}</strong>
            {predictionLocked && <span>{t.predictionLocked}</span>}
            {!predictionLocked && predictionWasSaved && <span>{t.predictionSaved}</span>}
          </div>
          <div className="prediction-options">
            {["home", "draw", "away"].map((value) => (
              <button
                className={prediction === value ? "selected" : ""}
                disabled={predictionLocked || isPredictionSaving}
                key={value}
                onClick={() => onPredictionSelect?.(match.id, value)}
                type="button"
              >
                {getPredictionLabel(match, value, lang, t)}
              </button>
            ))}
          </div>
          {prediction && (
            <p className="prediction-selection">
              {t.yourPrediction}: <strong>{getPredictionLabel(match, prediction, lang, t)}</strong>
            </p>
          )}
          {predictionSaveFailed && <p className="prediction-error">{t.predictionSaveFailed}</p>}
        </div>
      )}

      {showReminder && (
        <button
          className={`remind-btn ${isReminderActive ? "active" : ""}`}
          onClick={(event) => {
            event.stopPropagation();
            onReminderToggle(match.id);
          }}
        >
          {isReminderActive ? `🔕 ${t.cancelReminder}` : `🔔 ${t.remind}`}
        </button>
      )}

      {canViewEvents && (
        <button className="details-btn" onClick={() => onDetailsClick?.(match)}>
          {t.viewEvents}
        </button>
      )}

      {isExpanded && (
        <div className="match-events" onClick={stopCardClick}>
          <h3>{t.matchEvents}</h3>
          {isLoadingEvents ? (
            <p>{t.loadingEvents}</p>
          ) : eventsFailed ? (
            <p>{t.eventRequestFailed}</p>
          ) : eventsUnavailable ? (
            <p>{t.eventSourceUnavailable}</p>
          ) : events.length > 0 ? (
            <ol className="event-timeline">
              {events.map((event, index) => (
                <EventRow
                  event={event}
                  index={index}
                  key={`${event.display_minute || event.raw_minute || event.minute}-${event.type}-${event.player}-${event.team}-${index}`}
                  lang={lang}
                  match={match}
                  t={t}
                />
              ))}
            </ol>
          ) : (
            <p>{t.noEvents}</p>
          )}
        </div>
      )}
    </article>
  );
}
