import { API_BASE_URL } from "../api/client.js";

export const COMPETITIONS = {
  worldcup2026: {
    competitionKey: "worldcup2026",
    seasonKey: "2026",
    labels: {
      fa: "\u062c\u0627\u0645 \u062c\u0647\u0627\u0646\u06cc \u06f2\u06f0\u06f2\u06f6",
      en: "World Cup 2026",
    },
    dataUrls: {
      matches: `${API_BASE_URL}/matches`,
      teams: `${API_BASE_URL}/teams`,
      events: (matchId) => `${API_BASE_URL}/match/${matchId}/events`,
    },
    logoSrc: "/world-cup-2026-logo.webp",
    logoFallback: "WC 2026",
    fixedStats: { teams: 48, matches: 104, cities: 16 },
    supportsFavorites: true,
    supportsReminders: true,
    supportsPredictions: true,
    supportsScopedEvents: false,
  },
  premier_league: {
    competitionKey: "premier_league",
    seasonKey: "2026-2027",
    labels: {
      fa: "\u0644\u06cc\u06af \u0628\u0631\u062a\u0631 \u0627\u0646\u06af\u0644\u06cc\u0633",
      en: "Premier League",
    },
    subtitles: {
      fa: "\u0628\u0631\u0646\u0627\u0645\u0647 \u0628\u0627\u0632\u06cc\u200c\u0647\u0627\u060c \u0646\u062a\u0627\u06cc\u062c \u0648 \u0648\u0636\u0639\u06cc\u062a \u0632\u0646\u062f\u0647 \u0644\u06cc\u06af \u0628\u0631\u062a\u0631 \u0627\u0646\u06af\u0644\u06cc\u0633",
      en: "Fixtures, results and live match status for the Premier League",
    },
    dataUrls: {
      matches: `${API_BASE_URL}/competitions/premier_league/seasons/2026-2027/matches?status=all`,
      teams: `${API_BASE_URL}/competitions/premier_league/seasons/2026-2027/teams`,
      events: (matchId) => `${API_BASE_URL}/competitions/premier_league/seasons/2026-2027/matches/${encodeURIComponent(matchId)}/events`,
    },
    logoSrc: "",
    logoFallback: "PL",
    fixedStats: null,
    supportsFavorites: false,
    supportsReminders: false,
    supportsPredictions: false,
    supportsScopedEvents: true,
  },
};
