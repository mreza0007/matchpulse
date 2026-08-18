import TeamFlag from "../teams/TeamFlag.jsx";

function teamName(row, lang) {
  if (lang === "fa") return row.team_fa || row.team_en || "";
  return row.team_en || row.team_fa || "";
}

function valueOrDash(value) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

export default function GroupTable({ group, lang, preview = false, t }) {
  const standings = Array.isArray(group.standings) ? group.standings : [];
  const rows = preview ? standings.slice(0, 4) : standings;

  return (
    <section className="competition-group-card">
      <h3>{t.group} {group.group_key}</h3>
      <div className="standings-table-scroll group-table-scroll">
        <table className="standings-table group-table">
          <thead>
            <tr>
              <th scope="col">{t.standingsTeam}</th>
              <th scope="col">{t.standingsPlayed}</th>
              <th scope="col">{t.standingsGoalDifference}</th>
              <th scope="col">{t.standingsPoints}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.team_id || index}>
                <td>
                  <span className="standings-team">
                    <TeamFlag logoUrl={row.logo || ""} teamName={row.team_en || row.team_fa || ""} />
                    <strong>{teamName(row, lang)}</strong>
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
    </section>
  );
}
