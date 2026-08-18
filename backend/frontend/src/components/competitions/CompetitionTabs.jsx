const TAB_LABEL_KEYS = {
  overview: "competitionTabOverview",
  matches: "competitionTabMatches",
  standings: "competitionTabStandings",
  groups: "competitionTabGroups",
  knockout: "competitionTabKnockout",
  stats: "competitionTabStats",
  teams: "competitionTabTeams",
};

export default function CompetitionTabs({ activeTab, onChange, tabs, t }) {
  return (
    <div className="competition-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          aria-selected={activeTab === tab}
          className={activeTab === tab ? "active" : ""}
          key={tab}
          onClick={() => onChange(tab)}
          role="tab"
          type="button"
        >
          {t[TAB_LABEL_KEYS[tab]]}
        </button>
      ))}
    </div>
  );
}
