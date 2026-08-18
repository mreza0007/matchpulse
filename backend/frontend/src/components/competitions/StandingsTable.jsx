import TeamFlag from "../teams/TeamFlag.jsx";

function teamName(row, lang) {
  if (lang === "fa") return row.team_fa || row.team_en || "";
  return row.team_en || row.team_fa || "";
}

function valueOrDash(value) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

export default function StandingsTable({ lang, preview = false, rows, t }) {
  return (
    <div className={`standings-table-scroll ${preview ? "preview" : ""}`}>
      <table className="standings-table">
        <thead>
          <tr>
            <th scope="col">{t.standingsRank}</th>
            <th scope="col">{t.standingsTeam}</th>
            <th scope="col">{t.standingsPlayed}</th>
            <th scope="col">{t.standingsGoalDifference}</th>
            <th scope="col">{t.standingsPoints}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.team_id || row.external_team_id || index}>
              <td className="standings-rank">{valueOrDash(row.rank)}</td>
              <td>
                <span className="standings-team">
                  <TeamFlag logoUrl={row.logo || ""} teamName={row.team_en || ""} />
                  <strong>{teamName(row, lang)}</strong>
                  {row.has_live_match === true && (
                    <span className="standings-live-dot" aria-label={t.statusLive} title={t.statusLive} />
                  )}
                </span>
              </td>
              <td>{valueOrDash(row.played)}</td>
              <td>{valueOrDash(row.goal_difference)}</td>
              <td className="standings-points">{valueOrDash(row.points)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
