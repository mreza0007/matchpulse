import { useState } from "react";
import { useDailyMatches, useTehranCalendarDates } from "../hooks/useDailyMatches.js";
import CompetitionMatchGroup from "../components/competitions/CompetitionMatchGroup.jsx";
import MatchCard from "../components/matches/MatchCard.jsx";

const EMPTY_SET = new Set();

function LiveSkeleton() {
  return (
    <div className="home-competition-list" aria-hidden="true">
      {[0, 1].map((index) => (
        <section className="competition-match-group" key={index}>
          <div className="live-skeleton-header" />
          <div className="home-skeleton-card" />
        </section>
      ))}
    </div>
  );
}

export default function LivePage({ lang, t }) {
  const dates = useTehranCalendarDates();
  const [selectedDay, setSelectedDay] = useState("today");
  const result = useDailyMatches(dates[selectedDay]);
  const { retry } = result;

  const dayOptions = [
    { key: "yesterday", label: t.yesterday },
    { key: "today", label: t.today },
    { key: "tomorrow", label: t.tomorrow },
  ];
  const emptyMessage = {
    yesterday: t.liveYesterdayEmpty,
    today: t.liveTodayEmpty,
    tomorrow: t.liveTomorrowEmpty,
  }[selectedDay];
  const hasGroups = result.groups.length > 0;
  const selectDay = (day) => {
    if (day === selectedDay) return;
    setSelectedDay(day);
  };

  return (
    <section className="live-page">
      <div className="live-date-selector" aria-label={t.liveMatches} role="tablist">
        {dayOptions.map((option) => (
          <button
            aria-selected={selectedDay === option.key}
            className={selectedDay === option.key ? "active" : ""}
            key={option.key}
            onClick={() => selectDay(option.key)}
            role="tab"
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>

      {result.loading && !result.hasPayload && <LiveSkeleton />}

      {hasGroups && (
        <div className={`home-competition-list ${result.loading ? "live-groups-loading" : ""}`} aria-busy={result.loading}>
          {result.groups.map((group, groupIndex) => (
            <CompetitionMatchGroup
              group={group}
              key={group.competition?.key || group.competition?.season_key || groupIndex}
            >
              {(group.matches || []).map((match, matchIndex) => (
                <MatchCard
                  awayTeam={match.away_logo ? { logo: match.away_logo } : undefined}
                  favoriteTeamIds={EMPTY_SET}
                  favoriteTeamKeys={EMPTY_SET}
                  homeTeam={match.home_logo ? { logo: match.home_logo } : undefined}
                  key={`${group.competition?.key || groupIndex}:${match.id ?? matchIndex}`}
                  lang={lang}
                  match={match}
                  showEvents={false}
                  showFavorites={false}
                  showPredictions={false}
                  showReminder={false}
                  showStatusSummary
                  t={t}
                />
              ))}
            </CompetitionMatchGroup>
          ))}
        </div>
      )}

      {result.loading && hasGroups && <p className="live-loading-note">{t.loadingMatches}</p>}
      {!result.loading && result.errors.length > 0 && (
        <p className="home-inline-warning">{t.homePartialWarning}</p>
      )}
      {!result.loading && result.failed && (
        <div className="home-empty-state live-error-state">
          <p>{t.liveLoadError}</p>
          <button onClick={retry} type="button">
            {t.retry}
          </button>
        </div>
      )}
      {!result.loading && !result.failed && !hasGroups && (
        <div className="home-empty-state">{emptyMessage}</div>
      )}
    </section>
  );
}
