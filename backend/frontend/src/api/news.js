import { API_BASE_URL, request } from "./client.js";

function buildNewsQuery({ category, competitionKey, teamId, limit, offset } = {}) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (competitionKey) params.set("competition_key", competitionKey);
  if (teamId !== undefined && teamId !== null) params.set("team_id", String(teamId));
  if (teamId !== undefined && teamId !== null && !competitionKey) throw new Error("Scoped team required");
  if (limit !== undefined) params.set("limit", String(limit));
  if (offset !== undefined) params.set("offset", String(offset));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function fetchNews({ category, competitionKey, teamId, limit, offset, signal } = {}) {
  const query = buildNewsQuery({ category, competitionKey, teamId, limit, offset });

  return request(`${API_BASE_URL}/news${query}`, { signal });
}

export function fetchFavoriteNews(telegramId, { category, limit, offset, signal } = {}) {
  const query = buildNewsQuery({ category, limit, offset });

  return request(
    `${API_BASE_URL}/news/favorites/${encodeURIComponent(telegramId)}${query}`,
    { signal },
  );
}
