import { API_BASE_URL, request } from "./client.js";

const jsonHeaders = { "Content-Type": "application/json" };

function scopedQuery(competitionKey, seasonKey) {
  const query = new URLSearchParams();
  if (competitionKey) query.set("competition_key", competitionKey);
  if (seasonKey) query.set("season_key", seasonKey);
  const value = query.toString();
  return value ? `?${value}` : "";
}

export function fetchPredictableMatches(competitionKey, seasonKey, { signal } = {}) {
  const competition = encodeURIComponent(competitionKey);
  const season = encodeURIComponent(seasonKey);
  return request(
    `${API_BASE_URL}/competitions/${competition}/seasons/${season}/predictable-matches`,
    { signal },
  );
}

export function fetchUserPredictions(
  telegramId,
  { competitionKey, seasonKey, signal } = {},
) {
  const query = scopedQuery(competitionKey, seasonKey);
  return request(`${API_BASE_URL}/predictions/${encodeURIComponent(telegramId)}${query}`, { signal });
}

export function fetchPredictionStats(
  telegramId,
  { competitionKey, seasonKey, signal } = {},
) {
  const query = scopedQuery(competitionKey, seasonKey);
  return request(
    `${API_BASE_URL}/prediction-stats/${encodeURIComponent(telegramId)}${query}`,
    { signal },
  );
}

export function fetchPredictionHistory(
  telegramId,
  { competitionKey, seasonKey, signal } = {},
) {
  const query = scopedQuery(competitionKey, seasonKey);
  return request(
    `${API_BASE_URL}/prediction-history/${encodeURIComponent(telegramId)}${query}`,
    { signal },
  );
}

export function fetchPredictionLeaderboard(
  { competitionKey, seasonKey, signal } = {},
) {
  const query = scopedQuery(competitionKey, seasonKey);
  return request(`${API_BASE_URL}/prediction-leaderboard${query}`, { signal });
}

export function savePrediction(payload, { signal } = {}) {
  return request(`${API_BASE_URL}/prediction`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
    signal,
  });
}
