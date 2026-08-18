import { useEffect, useMemo, useState } from "react";
import { fetchCompetitions } from "../api/football.js";
import {
  COMPETITION_CATEGORY_BY_KEY,
  COMPETITION_CATEGORY_ORDER,
} from "../config/competitionCategories.js";
import CompetitionLogo from "../components/competitions/CompetitionLogo.jsx";
import { getCompetitionName } from "../utils/competitions.js";
import CompetitionPage from "./CompetitionPage.jsx";

function CompetitionListSkeleton() {
  return (
    <div className="competitions-skeleton" aria-hidden="true">
      <div className="competitions-skeleton-heading" />
      <div className="competitions-skeleton-row" />
      <div className="competitions-skeleton-row" />
    </div>
  );
}

export default function CompetitionsPage({ lang, t }) {
  const [competitions, setCompetitions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [retryVersion, setRetryVersion] = useState(0);
  const [selectedCompetition, setSelectedCompetition] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchCompetitions({ signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Competitions request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (controller.signal.aborted) return;
        setCompetitions(Array.isArray(payload?.competitions) ? payload.competitions : []);
        setHasError(false);
        setIsLoading(false);
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        console.error("Failed to load competitions directory:", error);
        setCompetitions([]);
        setHasError(true);
        setIsLoading(false);
      });

    return () => controller.abort();
  }, [retryVersion]);

  const categories = useMemo(() => {
    const grouped = Object.fromEntries(COMPETITION_CATEGORY_ORDER.map((key) => [key, []]));

    competitions.forEach((competition) => {
      const category = COMPETITION_CATEGORY_BY_KEY[competition?.competition_key];
      if (category && grouped[category]) grouped[category].push(competition);
    });

    return COMPETITION_CATEGORY_ORDER
      .map((key) => ({ key, competitions: grouped[key] }))
      .filter((category) => category.competitions.length > 0);
  }, [competitions]);

  const retry = () => {
    setHasError(false);
    setIsLoading(true);
    setRetryVersion((version) => version + 1);
  };

  if (selectedCompetition) {
    return (
      <CompetitionPage
        competition={selectedCompetition}
        lang={lang}
        onBack={() => setSelectedCompetition(null)}
        t={t}
      />
    );
  }

  return (
    <section className="competitions-page">
      <h1>{t.competitionsPage}</h1>

      {isLoading && <CompetitionListSkeleton />}

      {!isLoading && hasError && (
        <div className="home-empty-state competitions-error-state">
          <p>{t.competitionsLoadError}</p>
          <button onClick={retry} type="button">{t.retry}</button>
        </div>
      )}

      {!isLoading && !hasError && categories.length === 0 && (
        <div className="home-empty-state">{t.competitionsEmpty}</div>
      )}

      {!isLoading && !hasError && categories.map((category) => (
        <section className="competition-directory-section" key={category.key}>
          <h2>{t[category.key]}</h2>
          <div className="competition-directory-list">
            {category.competitions.map((competition) => (
              <button
                className="competition-directory-row"
                key={competition.competition_key}
                onClick={() => setSelectedCompetition(competition)}
                type="button"
              >
                <CompetitionLogo competition={competition} />
                <span className="competition-directory-copy">
                  <strong>{getCompetitionName(competition, lang)}</strong>
                  {competition.season_key && <small>{t.season}: {competition.season_key}</small>}
                </span>
                <span className="competition-directory-chevron" aria-hidden="true">‹</span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </section>
  );
}
