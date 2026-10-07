import { API_BASE_URL } from "../api/client.js";

function genericCompetitionConfig(competitionKey, seasonKey, labels, logoFallback, logoSrc) {
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
    logoSrc,
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
    logoSrc: "/competition-logos/premier-league.svg",
    logoFallback: "PL",
    fixedStats: null,
    supportsScopedEvents: true,
  },
  persian_gulf_pro_league: genericCompetitionConfig(
    "persian_gulf_pro_league", "1405-1406",
    { fa: "لیگ برتر خلیج فارس", en: "Persian Gulf Pro League" }, "PGPL",
    "/competition-logos/persian-gulf-pro-league.png",
  ),
  la_liga: genericCompetitionConfig(
    "la_liga", "2026-2027", { fa: "لالیگا", en: "La Liga" }, "LL",
    "/competition-logos/la-liga.svg",
  ),
  serie_a: genericCompetitionConfig(
    "serie_a", "2026-2027", { fa: "سری آ", en: "Serie A" }, "SA",
    "/competition-logos/serie-a.svg",
  ),
  bundesliga: genericCompetitionConfig(
    "bundesliga", "2026-2027", { fa: "بوندس‌لیگا", en: "Bundesliga" }, "BL",
    "/competition-logos/bundesliga.svg",
  ),
  ligue_1: genericCompetitionConfig(
    "ligue_1", "2026-2027", { fa: "لیگ ۱ فرانسه", en: "Ligue 1" }, "L1",
    "/competition-logos/ligue-1.svg",
  ),
  champions_league: genericCompetitionConfig(
    "champions_league", "2026-2027",
    { fa: "لیگ قهرمانان اروپا", en: "UEFA Champions League" }, "UCL",
    "/competition-logos/champions-league.svg",
  ),
  europa_league: genericCompetitionConfig(
    "europa_league", "2026-2027",
    { fa: "لیگ اروپا", en: "UEFA Europa League" }, "UEL",
    "/competition-logos/europa-league.svg",
  ),
  uefa_nations_league_a: genericCompetitionConfig(
    "uefa_nations_league_a", "2026-2027",
    { fa: "لیگ ملت‌های اروپا (A)", en: "UEFA Nations League A" }, "UNL A",
    "/competition-logos/uefa-nations-league.png",
  ),
  uefa_nations_league_b: genericCompetitionConfig(
    "uefa_nations_league_b", "2026-2027",
    { fa: "لیگ ملت‌های اروپا (B)", en: "UEFA Nations League B" }, "UNL B",
    "/competition-logos/uefa-nations-league.png",
  ),
  uefa_nations_league_c: genericCompetitionConfig(
    "uefa_nations_league_c", "2026-2027",
    { fa: "لیگ ملت‌های اروپا (C)", en: "UEFA Nations League C" }, "UNL C",
    "/competition-logos/uefa-nations-league.png",
  ),
  uefa_nations_league_d: genericCompetitionConfig(
    "uefa_nations_league_d", "2026-2027",
    { fa: "لیگ ملت‌های اروپا (D)", en: "UEFA Nations League D" }, "UNL D",
    "/competition-logos/uefa-nations-league.png",
  ),
};
