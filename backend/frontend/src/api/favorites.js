import { API_BASE_URL, request } from "./client.js";

const jsonHeaders = { "Content-Type": "application/json" };

export function fetchFavoriteTeams(telegramId, { signal } = {}) {
  return request(`${API_BASE_URL}/favorite-teams/${telegramId}`, { signal });
}

export function addFavoriteTeam(payload, { signal } = {}) {
  return request(`${API_BASE_URL}/favorite-team`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
    signal,
  });
}

export function deleteFavoriteTeam(payload, { signal } = {}) {
  return request(`${API_BASE_URL}/favorite-team`, {
    method: "DELETE",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
    signal,
  });
}
