import { useEffect, useMemo, useState } from "react";
import { fetchMatchesByDate } from "../api/football.js";
import CompetitionMatchGroup from "../components/competitions/CompetitionMatchGroup.jsx";
import HeroMatchCard from "../components/matches/HeroMatchCard.jsx";
import MatchCard from "../components/matches/MatchCard.jsx";
import { formatTehranMatchDateTime, getTehranCalendarDates } from "../utils/dates.js";
import { isLiveMatch } from "../utils/matches.js";

const EMPTY_SET = new Set();
const INITIAL_DATE_STATE = { groups: [], errors: [], failed: false, loading: true };

function normalizeDatePayload(payload) {
  return {
    groups: Array.isArray(payload?.groups) ? payload.groups : [],
    errors: Array.isArray(payload?.errors) ? payload.errors : [],
    failed: false,
    loading: false,
  };
}

function firstMatch(groups) {
  for (const group of groups) {
    if (Array.isArray(group.matches) && group.matches.length > 0) return group.matches[0];
  }
  return null;
}

function displayDate(groups, lang) {
  const match = firstMatch(groups);
  return match ? formatTehranMatchDateTime(match, lang).date : "";
}

function HomeSkeleton({ label }) {
  return (
    <section className="home-date-section" aria-label={label}>
      <div className="home-date-heading"><h2>{label}</h2></div>
      <div className="home-skeleton-list" aria-hidden="true">
        <div className="home-skeleton-card" />
        <div className="home-skeleton-card" />
      </div>
    </section>
  );
}

function DateMatchSection({ label, groups, lang, renderMatch }) {
  if (groups.length === 0) return null;
  const dateLabel = displayDate(groups, lang);

  return (
    <section className="home-date-section">
      <div className="home-date-heading">
        <h2>{label}</h2>
        {dateLabel && <span>{dateLabel}</span>}
      </div>
      <div className="home-competition-list">
        {groups.map((group) => (
          <CompetitionMatchGroup group={group} key={group.competition?.key || group.competition?.season_key}>
            {(group.matches || []).map((match) => renderMatch(match, group.competition))}
          </CompetitionMatchGroup>
        ))}
      </div>
    </section>
  );
}

export default function HomePage({ lang, t }) {
  const [dates] = useState(() => getTehranCalendarDates());
  const [today, setToday] = useState(INITIAL_DATE_STATE);
  const [tomorrow, setTomorrow] = useState(INITIAL_DATE_STATE);

  useEffect(() => {
    const controller = new AbortController();

    const loadDate = (date, setter) => {
      fetchMatchesByDate(date, { signal: controller.signal })
        .then((response) => {
          if (!response.ok) throw new Error(`Aggregate matches request failed: ${response.status}`);
          return response.json();
        })
        .then((payload) => setter(normalizeDatePayload(payload)))
        .catch((error) => {
          if (error.name === "AbortError") return;
          console.error("Failed to load aggregate matches:", error);
          setter({ groups: [], errors: [], failed: true, loading: false });
        });
    };

    loadDate(dates.today, setToday);
    loadDate(dates.tomorrow, setTomorrow);
    return () => controller.abort();
  }, [dates]);

  const todayMatches = useMemo(
    () => today.groups.flatMap((group) => Array.isArray(group.matches) ? group.matches : []),
    [today.groups],
  );
  const liveMatches = todayMatches.filter(isLiveMatch);
  const featuredLiveMatch = liveMatches.length === 1 ? liveMatches[0] : null;
  const hasWarning = today.failed || tomorrow.failed || today.errors.length > 0 || tomorrow.errors.length > 0;
  const isLoading = today.loading || tomorrow.loading;
  const isEmpty = !isLoading && today.groups.length === 0 && tomorrow.groups.length === 0;

  const renderMatch = (match, competition, variant = "standard") => (
    <MatchCard
      awayTeam={match.away_logo ? { logo: match.away_logo } : undefined}
      favoriteTeamIds={EMPTY_SET}
      favoriteTeamKeys={EMPTY_SET}
      homeTeam={match.home_logo ? { logo: match.home_logo } : undefined}
      key={`${competition?.key || "competition"}:${match.id}`}
      lang={lang}
      match={match}
      showEvents={false}
      showFavorites={false}
      showPredictions={false}
      showReminder={false}
      t={t}
      variant={variant}
    />
  );

  return (
    <div className="home-page">
      {featuredLiveMatch && (
        <section className="featured-live-section">
          <HeroMatchCard label={t.featuredLive} lang={lang} match={featuredLiveMatch} mode="live" t={t}>
            {renderMatch(featuredLiveMatch, { key: featuredLiveMatch.competition_key }, "hero")}
          </HeroMatchCard>
        </section>
      )}

      {today.loading ? (
        <HomeSkeleton label={t.today} />
      ) : (
        <DateMatchSection groups={today.groups} label={t.today} lang={lang} renderMatch={renderMatch} />
      )}

      {tomorrow.loading ? (
        <HomeSkeleton label={t.tomorrow} />
      ) : (
        <DateMatchSection groups={tomorrow.groups} label={t.tomorrow} lang={lang} renderMatch={renderMatch} />
      )}

      {hasWarning && <p className="home-inline-warning">{t.homePartialWarning}</p>}
      {isEmpty && <div className="home-empty-state">{t.homeEmpty}</div>}
    </div>
  );
}
