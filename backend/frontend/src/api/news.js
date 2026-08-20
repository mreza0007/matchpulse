import { API_BASE_URL, request } from "./client.js";

function buildNewsQuery({ category, competitionKey, teamId } = {}) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (competitionKey) params.set("competition_key", competitionKey);
  if (teamId !== undefined && teamId !== null) params.set("team_id", String(teamId));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function fetchNews({ category, competitionKey, teamId, signal } = {}) {
  const query = buildNewsQuery({ category, competitionKey, teamId });

  return request(`${API_BASE_URL}/news${query}`, { signal });
}

export function fetchFavoriteNews(telegramId, { category, signal } = {}) {
  const query = buildNewsQuery({ category });

  return request(
    `${API_BASE_URL}/news/favorites/${encodeURIComponent(telegramId)}${query}`,
    { signal },
  );
}
