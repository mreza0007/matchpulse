import { API_BASE_URL, request } from "./client.js";

const jsonHeaders = { "Content-Type": "application/json" };

export function saveTelegramUser(telegramId, telegramUser) {
  return request(`${API_BASE_URL}/user`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      telegram_id: telegramId,
      first_name: telegramUser?.first_name || "",
      last_name: telegramUser?.last_name || "",
      username: telegramUser?.username || "",
      language_code: telegramUser?.language_code || "",
    }),
  });
}

export function fetchFavoriteTeams(telegramId) {
  return request(`${API_BASE_URL}/favorite-teams/${telegramId}`);
}

export function fetchReminders(telegramId) {
  return request(`${API_BASE_URL}/reminders/${telegramId}`);
}

export function fetchPredictions(telegramId) {
  return request(`${API_BASE_URL}/predictions/${telegramId}`);
}

export function fetchPredictionStats(telegramId) {
  return request(`${API_BASE_URL}/prediction-stats/${telegramId}`);
}

export function createFavoriteTeam(telegramId, team) {
  return request(`${API_BASE_URL}/favorite-team`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ telegram_id: telegramId, ...team }),
  });
}

export function deleteFavoriteTeam(telegramId, teamId, teamKey) {
  return request(`${API_BASE_URL}/favorite-team`, {
    method: "DELETE",
    headers: jsonHeaders,
    body: JSON.stringify({
      telegram_id: telegramId,
      team_id: teamId,
      team_key: teamKey,
    }),
  });
}

export function createReminder(telegramId, matchId) {
  return request(`${API_BASE_URL}/reminder`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ telegram_id: telegramId, match_id: matchId }),
  });
}

export function deleteReminder(telegramId, matchId) {
  return request(`${API_BASE_URL}/reminder`, {
    method: "DELETE",
    headers: jsonHeaders,
    body: JSON.stringify({ telegram_id: telegramId, match_id: matchId }),
  });
}

export function savePrediction(telegramId, matchId, prediction) {
  return request(`${API_BASE_URL}/prediction`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ telegram_id: telegramId, match_id: matchId, prediction }),
  });
}
