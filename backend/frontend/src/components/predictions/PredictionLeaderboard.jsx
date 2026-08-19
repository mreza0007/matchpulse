export default function PredictionLeaderboard({ entries, t }) {
  return (
    <div className="prediction-leaderboard-table-wrap">
      <table className="prediction-leaderboard-table">
        <thead>
          <tr>
            <th>{t.predictionLeaderboardRank}</th>
            <th>{t.predictionLeaderboardUser}</th>
            <th>{t.predictionLeaderboardPoints}</th>
            <th>{t.predictionLeaderboardCorrect}</th>
            <th>{t.predictionLeaderboardTotal}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry, index) => (
            <tr key={`${entry.rank}:${entry.display_name}:${index}`}>
              <td>{entry.rank}</td>
              <td>{entry.display_name}</td>
              <td>{entry.points}</td>
              <td>{entry.correct}</td>
              <td>{entry.total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
