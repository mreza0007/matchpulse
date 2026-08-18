import { useEffect, useRef, useState } from "react";
import { fetchMatchesByDate } from "../api/football.js";
import CompetitionMatchGroup from "../components/competitions/CompetitionMatchGroup.jsx";
import MatchCard from "../components/matches/MatchCard.jsx";
import { getTehranCalendarDates } from "../utils/dates.js";

const EMPTY_SET = new Set();
const INITIAL_STATE = { groups: [], errors: [], failed: false, loading: true };

function normalizePayload(payload) {
  return {
    groups: Array.isArray(payload?.groups) ? payload.groups : [],
    errors: Array.isArray(payload?.errors) ? payload.errors : [],
    failed: false,
    loading: false,
  };
}

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
  const [dates] = useState(() => getTehranCalendarDates());
  const [selectedDay, setSelectedDay] = useState("today");
  const [result, setResult] = useState(INITIAL_STATE);
  const [retryVersion, setRetryVersion] = useState(0);
  const requestVersion = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const currentRequest = requestVersion.current + 1;
    requestVersion.current = currentRequest;

    fetchMatchesByDate(dates[selectedDay], { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Aggregate matches request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (requestVersion.current !== currentRequest || controller.signal.aborted) return;
        setResult(normalizePayload(payload));
      })
      .catch((error) => {
        if (error.name === "AbortError" || requestVersion.current !== currentRequest) return;
        console.error("Failed to load Live match schedule:", error);
        setResult({ groups: [], errors: [], failed: true, loading: false });
      });

    return () => controller.abort();
  }, [dates, retryVersion, selectedDay]);

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
    setResult((current) => ({ ...current, failed: false, loading: true }));
    setSelectedDay(day);
  };
  const retry = () => {
    setResult((current) => ({ ...current, failed: false, loading: true }));
    setRetryVersion((version) => version + 1);
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

      {result.loading && !hasGroups && <LiveSkeleton />}

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
