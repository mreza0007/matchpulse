import MatchCard from "../matches/MatchCard.jsx";

const EMPTY_SET = new Set();
const ROUND_LABEL_KEYS = {
  r32: "knockoutRoundR32",
  r16: "knockoutRoundR16",
  qf: "knockoutRoundQf",
  sf: "knockoutRoundSf",
  third: "knockoutRoundThird",
  final: "knockoutRoundFinal",
};

function roundLabel(roundKey, t) {
  const translationKey = ROUND_LABEL_KEYS[roundKey];
  return (translationKey && t[translationKey]) || roundKey;
}

export default function KnockoutRound({ competitionKey, lang, round, t }) {
  const matches = Array.isArray(round.matches) ? round.matches : [];

  return (
    <section className="competition-knockout-round">
      <h2>{roundLabel(round.round_key, t)}</h2>
      <div className="competition-knockout-matches">
        {matches.map((match, index) => (
          <MatchCard
            awayTeam={match.away_logo ? { logo: match.away_logo } : undefined}
            favoriteTeamIds={EMPTY_SET}
            favoriteTeamKeys={EMPTY_SET}
            homeTeam={match.home_logo ? { logo: match.home_logo } : undefined}
            key={`${competitionKey}:${round.round_key}:${match.id ?? index}`}
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
      </div>
    </section>
  );
}
