import { useEffect, useState } from "react";
import { fetchWorldCupSummary } from "../api/football.js";
import CompetitionLogo from "../components/competitions/CompetitionLogo.jsx";
import WorldCupArchive from "../components/worldcup/WorldCupArchive.jsx";
import { getCompetitionName } from "../utils/competitions.js";

export default function ArchivedCompetitionPage({ competition, lang, onBack, t }) {
  const [summary, setSummary] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    fetchWorldCupSummary({ signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`World Cup summary request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (controller.signal.aborted) return;
        setSummary(payload);
        setIsLoading(false);
      })
      .catch((requestError) => {
        if (requestError.name === "AbortError") return;
        console.error("Failed to load World Cup summary:", requestError);
        setError(t.worldcupArchiveLoadError);
        setIsLoading(false);
      });

    return () => controller.abort();
  }, [t.worldcupArchiveLoadError]);

  return (
    <section className="competition-detail-shell archive-section">
      <button className="competition-back-button" onClick={onBack} type="button">
        <span aria-hidden="true">{lang === "fa" ? "\u2192" : "\u2190"}</span>
        {t.backToCompetitions}
      </button>

      <div className="competition-detail-identity">
        <CompetitionLogo competition={competition} />
        <div>
          <p className="eyebrow">{t.worldcupArchiveSubtitle}</p>
          <h1>{getCompetitionName(competition, lang)}</h1>
          {competition.season_key && <p>{t.season}: {competition.season_key}</p>}
        </div>
      </div>

      <WorldCupArchive
        error={error}
        isLoading={isLoading}
        lang={lang}
        summary={summary}
        t={t}
      />
    </section>
  );
}
