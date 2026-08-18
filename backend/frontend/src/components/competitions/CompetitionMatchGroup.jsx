export default function CompetitionMatchGroup({ group, children }) {
  const competition = group.competition || {};
  const competitionName = competition.name_fa || competition.name || competition.key || "";

  return (
    <section className="competition-match-group">
      <button
        aria-disabled="true"
        className="competition-group-header"
        data-competition-key={competition.key || ""}
        type="button"
      >
        <span>{competitionName}</span>
        <span aria-hidden="true">‹</span>
      </button>
      <div className="competition-group-matches">{children}</div>
    </section>
  );
}
