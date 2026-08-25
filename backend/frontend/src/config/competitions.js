import { API_BASE_URL } from "../api/client.js";

function genericCompetitionConfig(competitionKey, seasonKey, labels, logoFallback) {
  const competition = encodeURIComponent(competitionKey);
  const season = encodeURIComponent(seasonKey);
  return {
    competitionKey,
    seasonKey,
    labels,
    subtitles: {
      fa: `برنامه بازی‌ها، نتایج و وضعیت زنده ${labels.fa}`,
      en: `Fixtures, results and live match status for ${labels.en}`,
    },
    dataUrls: {
      matches: `${API_BASE_URL}/competitions/${competition}/seasons/${season}/matches?status=all`,
      teams: `${API_BASE_URL}/competitions/${competition}/seasons/${season}/teams`,
      events: (matchId) => (
        `${API_BASE_URL}/competitions/${competition}/seasons/${season}/matches/${encodeURIComponent(matchId)}/events`
      ),
    },
    logoSrc: "",
    logoFallback,
    fixedStats: null,
    supportsScopedEvents: true,
  };
}

export const COMPETITIONS = {
  worldcup2026: {
    competitionKey: "worldcup2026",
    seasonKey: "2026",
    status: "archived",
    isActive: false,
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
    supportsScopedEvents: true,
  },
  persian_gulf_pro_league: genericCompetitionConfig(
    "persian_gulf_pro_league", "1405-1406",
    { fa: "لیگ برتر خلیج فارس", en: "Persian Gulf Pro League" }, "PGPL",
  ),
  la_liga: genericCompetitionConfig(
    "la_liga", "2026-2027", { fa: "لالیگا", en: "La Liga" }, "LL",
  ),
  serie_a: genericCompetitionConfig(
    "serie_a", "2026-2027", { fa: "سری آ", en: "Serie A" }, "SA",
  ),
  bundesliga: genericCompetitionConfig(
    "bundesliga", "2026-2027", { fa: "بوندس‌لیگا", en: "Bundesliga" }, "BL",
  ),
  ligue_1: genericCompetitionConfig(
    "ligue_1", "2026-2027", { fa: "لیگ ۱ فرانسه", en: "Ligue 1" }, "L1",
  ),
  champions_league: genericCompetitionConfig(
    "champions_league", "2026-2027",
    { fa: "لیگ قهرمانان اروپا", en: "UEFA Champions League" }, "UCL",
  ),
  europa_league: genericCompetitionConfig(
    "europa_league", "2026-2027",
    { fa: "لیگ اروپا", en: "UEFA Europa League" }, "UEL",
  ),
};
