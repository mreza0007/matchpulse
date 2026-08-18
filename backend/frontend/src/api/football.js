import { request, API_BASE_URL } from "./client.js";
import { COMPETITIONS } from "../config/competitions.js";

export function fetchWorldCupSummary() {
  return request(`${API_BASE_URL}/worldcup/summary`);
}

export function fetchCompetitions(options) {
  return request(`${API_BASE_URL}/competitions`, options);
}

export function fetchCompetitionMatches(competition, options) {
  return request(competition.dataUrls.matches, options);
}

export function fetchCompetitionTeams(competition, options) {
  return request(competition.dataUrls.teams, options);
}

export function fetchCompetitionSeasonMatches(competitionKey, seasonKey, options) {
  const competition = encodeURIComponent(competitionKey);
  const season = encodeURIComponent(seasonKey);
  return request(`${API_BASE_URL}/competitions/${competition}/seasons/${season}/matches?status=all`, options);
}

export function fetchCompetitionSeasonTeams(competitionKey, seasonKey, options) {
  const competition = encodeURIComponent(competitionKey);
  const season = encodeURIComponent(seasonKey);
  return request(`${API_BASE_URL}/competitions/${competition}/seasons/${season}/teams`, options);
}

export function fetchCompetitionStandings(competitionKey, seasonKey, options) {
  const competition = encodeURIComponent(competitionKey);
  const season = encodeURIComponent(seasonKey);
  return request(`${API_BASE_URL}/competitions/${competition}/seasons/${season}/standings`, options);
}

export function fetchCompetitionGroups(competitionKey, seasonKey, options) {
  const competition = encodeURIComponent(competitionKey);
  const season = encodeURIComponent(seasonKey);
  return request(`${API_BASE_URL}/competitions/${competition}/seasons/${season}/groups`, options);
}

export function fetchMatchEvents(competition, matchId, options) {
  const eventsUrl = competition.supportsScopedEvents
    ? competition.dataUrls.events(matchId)
    : COMPETITIONS.worldcup2026.dataUrls.events(matchId);

  return request(eventsUrl, options);
}

export function fetchMatchesByDate(date, options) {
  return request(`${API_BASE_URL}/matches/by-date?date=${encodeURIComponent(date)}`, options);
}
