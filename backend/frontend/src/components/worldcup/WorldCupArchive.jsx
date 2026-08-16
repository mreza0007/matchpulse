import TeamFlag from "../teams/TeamFlag.jsx";
import { getPenaltySummary } from "../../utils/matches.js";

function PenaltySummary({ match, lang }) {
  const summary = getPenaltySummary(match, lang);
  if (!summary) return null;

  return (
    <div className="penalty-summary">
      {summary}
    </div>
  );
}

function SummaryFlag({ team }) {
  const flagUrl = team?.flag_url || (typeof team?.flag === "string" && team.flag.startsWith("http") ? team.flag : "");
  const flagEmoji = flagUrl ? "" : team?.flag;
  const teamName = team?.name_en || team?.team_en || team?.team || "";

  if (flagUrl) {
    return (
      <span className="team-flag" aria-hidden="true">
        <img className="team-flag-img" src={flagUrl} alt="" loading="lazy" />
      </span>
    );
  }

  return <TeamFlag flagEmoji={flagEmoji} teamName={teamName} />;
}

function summaryName(team, lang) {
  if (!team) return "";
  return lang === "fa"
    ? team.name_fa || team.team_fa || team.home_fa || team.away_fa || team.name_en || team.team_en || team.team || ""
    : team.name_en || team.team_en || team.home_en || team.away_en || team.name_fa || team.team_fa || team.team || "";
}

function awardDisplayName(award, lang) {
  if (!award) return "";
  return lang === "fa"
    ? award.name_fa || award.name || award.name_en || ""
    : award.name_en || award.name || award.name_fa || "";
}

function summaryMatchTeams(match) {
  if (!match) return { home: null, away: null };
  return {
    home: {
      name_fa: match.home_fa,
      name_en: match.home_en,
      flag: match.home_flag,
      flag_url: match.home_flag_url,
    },
    away: {
      name_fa: match.away_fa,
      name_en: match.away_en,
      flag: match.away_flag,
      flag_url: match.away_flag_url,
    },
  };
}

function SummaryMatchCard({ title, match, lang, highlight = "" }) {
  if (!match) return null;

  const teams = summaryMatchTeams(match);
  const score = match.score || {};
  const scoreText = `${score.home ?? match.home_score ?? 0} - ${score.away ?? match.away_score ?? 0}`;

  return (
    <article className="archive-match-card">
      <div className="archive-card-kicker">{title}</div>
      <div className="archive-match-line">
        <span>
          <SummaryFlag team={teams.home} />
          {summaryName(teams.home, lang)}
        </span>
        <strong dir="ltr">{scoreText}</strong>
        <span>
          <SummaryFlag team={teams.away} />
          {summaryName(teams.away, lang)}
        </span>
      </div>
      <PenaltySummary match={match} lang={lang} />
      {highlight && <small>{highlight}</small>}
    </article>
  );
}

function PodiumCard({ rank, team, label, lang }) {
  if (!team) return null;

  return (
    <article className={`podium-card rank-${rank}`}>
      <span className="podium-rank">{rank}</span>
      <SummaryFlag team={team} />
      <div>
        <small>{label}</small>
        <strong>{summaryName(team, lang)}</strong>
      </div>
    </article>
  );
}

function AwardCard({ award, lang, t }) {
  if (!award) return null;

  const label = lang === "fa" ? award.award_fa : award.award_en;
  const team = {
    name_fa: award.team_fa,
    name_en: award.team_en,
    flag: award.team_flag,
    flag_url: award.team_flag_url,
  };
  const stat = lang === "fa"
    ? award.goals_label_fa || award.assists_label_fa || ""
    : award.goals
      ? `${award.goals} ${t.goalsLabel}`
      : award.assists
        ? `${award.assists} ${t.assistsLabel}`
        : "";

  return (
    <article className="award-card">
      <div className="archive-card-kicker">{label}</div>
      <strong>{awardDisplayName(award, lang)}</strong>
      <span>
        <SummaryFlag team={team} />
        {summaryName(team, lang)}
      </span>
      {stat && <b>{stat}</b>}
    </article>
  );
}

export default function WorldCupArchive({ summary, isLoading, error, lang, t }) {
  if (isLoading) {
    return <p className="archive-message">{t.worldcupArchiveLoading}</p>;
  }

  if (error || !summary || !summary.podium?.champion) {
    return <p className="archive-message">{t.worldcupArchiveError}</p>;
  }

  const podium = summary.podium || {};
  const awards = summary.awards || {};
  const highlights = summary.highlights || {};
  const champion = podium.champion;

  return (
    <div className="archive-page">
      <article className="archive-hero-card">
        <div className="archive-hero-mark" aria-hidden="true">2026</div>
        <div>
          <p className="eyebrow">{lang === "fa" ? summary.subtitle_fa : summary.subtitle_en}</p>
          <h2>{summaryName(champion, lang)}</h2>
          <span>{t.championTitle}</span>
        </div>
        <SummaryFlag team={champion} />
        <SummaryMatchCard title={t.finalMatchLabel} match={summary.final_match} lang={lang} t={t} />
      </article>

      <section className="archive-grid podium-grid">
        <PodiumCard rank="2" team={podium.runner_up} label={t.runnerUp} lang={lang} />
        <PodiumCard rank="3" team={podium.third_place} label={t.thirdPlaceHonor} lang={lang} />
        <PodiumCard rank="4" team={podium.fourth_place} label={t.fourthPlaceHonor} lang={lang} />
      </section>

      <section className="archive-block">
        <div className="section-header">
          <h2>{t.awardsTitle}</h2>
        </div>
        <div className="archive-grid awards-grid">
          <AwardCard award={awards.best_player} lang={lang} t={t} />
          <AwardCard award={awards.top_scorer} lang={lang} t={t} />
          <AwardCard award={awards.top_assister} lang={lang} t={t} />
          <AwardCard award={awards.best_goalkeeper} lang={lang} t={t} />
          <AwardCard award={awards.best_young_player} lang={lang} t={t} />
        </div>
      </section>

      <section className="archive-block">
        <div className="section-header">
          <h2>{t.finalMatchesTitle}</h2>
        </div>
        <div className="archive-grid">
          <SummaryMatchCard title={t.finalMatchLabel} match={summary.final_match} lang={lang} t={t} />
          <SummaryMatchCard title={t.thirdPlaceMatchLabel} match={summary.third_place_match} lang={lang} t={t} />
        </div>
      </section>

      <section className="archive-block">
        <div className="section-header">
          <h2>{t.highlightsTitle}</h2>
        </div>
        <div className="archive-grid">
          <SummaryMatchCard
            title={t.bestWin}
            match={highlights.best_win || highlights.biggest_wins?.[0]}
            lang={lang}
            t={t}
          />
        </div>
      </section>
    </div>
  );
}
