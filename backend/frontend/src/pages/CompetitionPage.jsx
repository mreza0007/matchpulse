import { useEffect, useMemo, useState } from "react";
import {
  fetchCompetitionSeasonMatches,
  fetchCompetitionSeasonTeams,
} from "../api/football.js";
import CompetitionLogo from "../components/competitions/CompetitionLogo.jsx";
import CompetitionTabs from "../components/competitions/CompetitionTabs.jsx";
import MatchCard from "../components/matches/MatchCard.jsx";
import TeamFlag from "../components/teams/TeamFlag.jsx";
import { getKickoffTime, groupMatchesByDate } from "../utils/dates.js";
import {
  isFutureMatchStatus,
  isLiveMatch,
  isResultTabMatch,
  normalizeMatchPayload,
} from "../utils/matches.js";
import { getCompetitionName } from "../utils/competitions.js";

const EMPTY_SET = new Set();
const FORMAT_TABS = {
  league: ["overview", "matches", "standings", "stats", "teams"],
  group_knockout: ["overview", "matches", "groups", "knockout", "stats", "teams"],
  knockout_only: ["overview", "matches", "knockout", "stats", "teams"],
};
const INITIAL_MATCHES = { items: [], loading: true, loaded: false, failed: false };
const INITIAL_TEAMS = { items: [], loading: false, loaded: false, failed: false };

function TabSkeleton() {
  return (
    <div className="competition-tab-skeleton" aria-hidden="true">
      <div className="home-skeleton-card" />
      <div className="home-skeleton-card" />
    </div>
  );
}

function RetryState({ message, onRetry, t }) {
  return (
    <div className="home-empty-state competitions-error-state">
      <p>{message}</p>
      <button onClick={onRetry} type="button">{t.retry}</button>
    </div>
  );
}

function DisplayMatchCard({ lang, match, t }) {
  return (
    <MatchCard
      awayTeam={match.away_logo ? { logo: match.away_logo } : undefined}
      favoriteTeamIds={EMPTY_SET}
      favoriteTeamKeys={EMPTY_SET}
      homeTeam={match.home_logo ? { logo: match.home_logo } : undefined}
      lang={lang}
      match={match}
      showEvents={false}
      showFavorites={false}
      showPredictions={false}
      showReminder={false}
      showStatusSummary
      t={t}
    />
  );
}

function overviewMatch(matches) {
  const liveMatch = matches.find(isLiveMatch);
  if (liveMatch) return liveMatch;

  return matches
    .map((match, index) => ({ index, kickoff: getKickoffTime(match), match }))
    .filter(({ kickoff, match }) => (
      Number.isFinite(kickoff) && kickoff > Date.now() && isFutureMatchStatus(match)
    ))
    .sort((first, second) => first.kickoff - second.kickoff || first.index - second.index)[0]?.match || null;
}

function teamName(team, lang) {
  if (lang === "fa") return team.name_fa || team.team_name || team.name_en || "";
  return team.name_en || team.team_name || team.name_fa || "";
}

export default function CompetitionPage({ competition, lang, onBack, t }) {
  const tabs = FORMAT_TABS[competition.format] || [];
  const [activeTab, setActiveTab] = useState("overview");
  const [matches, setMatches] = useState(INITIAL_MATCHES);
  const [teams, setTeams] = useState(INITIAL_TEAMS);
  const [matchesRetryVersion, setMatchesRetryVersion] = useState(0);
  const [teamsRetryVersion, setTeamsRetryVersion] = useState(0);
  const [teamsRequested, setTeamsRequested] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    fetchCompetitionSeasonMatches(
      competition.competition_key,
      competition.season_key,
      { signal: controller.signal },
    )
      .then((response) => {
        if (!response.ok) throw new Error(`Competition matches request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (controller.signal.aborted) return;
        const items = Array.isArray(payload?.matches)
          ? payload.matches.map(normalizeMatchPayload)
          : [];
        setMatches({ items, loading: false, loaded: true, failed: false });
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        console.error("Failed to load competition matches:", error);
        setMatches({ items: [], loading: false, loaded: false, failed: true });
      });

    return () => controller.abort();
  }, [competition.competition_key, competition.season_key, matchesRetryVersion]);

  useEffect(() => {
    if (!teamsRequested) return undefined;
    const controller = new AbortController();

    fetchCompetitionSeasonTeams(
      competition.competition_key,
      competition.season_key,
      { signal: controller.signal },
    )
      .then((response) => {
        if (!response.ok) throw new Error(`Competition teams request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (controller.signal.aborted) return;
        setTeams({
          items: Array.isArray(payload?.teams) ? payload.teams : [],
          loading: false,
          loaded: true,
          failed: false,
        });
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        console.error("Failed to load competition teams:", error);
        setTeams({ items: [], loading: false, loaded: false, failed: true });
      });

    return () => controller.abort();
  }, [competition.competition_key, competition.season_key, teamsRequested, teamsRetryVersion]);

  const matchGroups = useMemo(
    () => groupMatchesByDate(matches.items, lang),
    [lang, matches.items],
  );
  const primaryMatch = useMemo(() => overviewMatch(matches.items), [matches.items]);
  const previewMatches = useMemo(
    () => matches.items
      .filter((match) => match !== primaryMatch)
      .filter((match) => isLiveMatch(match) || isFutureMatchStatus(match) || isResultTabMatch(match))
      .slice(0, 3),
    [matches.items, primaryMatch],
  );

  const selectTab = (tab) => {
    setActiveTab(tab);
    if (tab === "teams" && !teamsRequested) {
      setTeams((current) => ({ ...current, loading: true }));
      setTeamsRequested(true);
    }
  };
  const retryMatches = () => {
    setMatches((current) => ({ ...current, loading: true, failed: false }));
    setMatchesRetryVersion((version) => version + 1);
  };
  const retryTeams = () => {
    setTeams((current) => ({ ...current, loading: true, failed: false }));
    setTeamsRetryVersion((version) => version + 1);
  };

  const renderOverview = () => {
    if (matches.loading) return <TabSkeleton />;
    if (matches.failed) return <RetryState message={t.competitionMatchesLoadError} onRetry={retryMatches} t={t} />;
    if (matches.items.length === 0) return <div className="home-empty-state">{t.competitionMatchesEmpty}</div>;

    return (
      <div className="competition-overview-content">
        {primaryMatch && (
          <section className="competition-preview-section">
            <h2>{isLiveMatch(primaryMatch) ? t.liveMatches : t.nextMatch}</h2>
            <DisplayMatchCard lang={lang} match={primaryMatch} t={t} />
          </section>
        )}
        {previewMatches.length > 0 && (
          <section className="competition-preview-section">
            <h2>{t.recentUpcomingMatches}</h2>
            <div className="competition-preview-matches">
              {previewMatches.map((match, index) => (
                <DisplayMatchCard
                  key={`${competition.competition_key}:${match.id ?? index}`}
                  lang={lang}
                  match={match}
                  t={t}
                />
              ))}
            </div>
          </section>
        )}
      </div>
    );
  };

  const renderMatches = () => {
    if (matches.loading) return <TabSkeleton />;
    if (matches.failed) return <RetryState message={t.competitionMatchesLoadError} onRetry={retryMatches} t={t} />;
    if (matches.items.length === 0) return <div className="home-empty-state">{t.competitionMatchesEmpty}</div>;

    return (
      <div className="competition-match-groups">
        {matchGroups.map((group) => (
          <section className="match-day-group" key={group.dateKey}>
            <h2 className="match-day-header">{group.label || t.dateUnavailable}</h2>
            <div className="match-day-list">
              {group.matches.map((match, index) => (
                <DisplayMatchCard
                  key={`${competition.competition_key}:${match.id ?? index}`}
                  lang={lang}
                  match={match}
                  t={t}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    );
  };

  const renderTeams = () => {
    if (teams.loading) return <TabSkeleton />;
    if (teams.failed) return <RetryState message={t.competitionTeamsLoadError} onRetry={retryTeams} t={t} />;
    if (teams.loaded && teams.items.length === 0) return <div className="home-empty-state">{t.competitionTeamsEmpty}</div>;

    return (
      <div className="competition-team-grid">
        {teams.items.map((team, index) => (
          <div className="competition-team-row" key={team.id || team.team_key || index}>
            <TeamFlag
              flagEmoji={team.emoji || team.flag}
              logoUrl={team.logo || team.logo_url || ""}
              teamName={team.name_en || team.team_name || ""}
            />
            <strong>{teamName(team, lang)}</strong>
          </div>
        ))}
      </div>
    );
  };

  const renderActiveTab = () => {
    if (activeTab === "overview") return renderOverview();
    if (activeTab === "matches") return renderMatches();
    if (activeTab === "teams") return renderTeams();
    return <div className="home-empty-state">{t.competitionDataUnavailable}</div>;
  };

  return (
    <section className="competition-detail-shell">
      <button className="competition-back-button" onClick={onBack} type="button">
        <span aria-hidden="true">{lang === "fa" ? "→" : "←"}</span>
        {t.backToCompetitions}
      </button>

      <div className="competition-detail-identity">
        <CompetitionLogo competition={competition} />
        <div>
          <h1>{getCompetitionName(competition, lang)}</h1>
          {competition.season_key && <p>{t.season}: {competition.season_key}</p>}
        </div>
      </div>

      {tabs.length > 0 ? (
        <>
          <CompetitionTabs activeTab={activeTab} onChange={selectTab} tabs={tabs} t={t} />
          <div className="competition-tab-content" role="tabpanel">{renderActiveTab()}</div>
        </>
      ) : (
        <div className="home-empty-state">{t.competitionDataUnavailable}</div>
      )}
    </section>
  );
}
