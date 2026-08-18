import CompetitionLogo from "../components/competitions/CompetitionLogo.jsx";
import { getCompetitionName } from "../utils/competitions.js";

export default function CompetitionPage({ competition, lang, onBack, t }) {
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

      <div className="home-empty-state">{t.competitionDetailComingSoon}</div>
    </section>
  );
}
