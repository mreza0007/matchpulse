// Temporary product metadata: the backend's broad `type` field cannot distinguish
// domestic leagues from club tournaments. Keep this explicit and key-based until
// the competition registry exposes a dedicated directory category.
export const COMPETITION_CATEGORY_ORDER = ["leagues", "clubCompetitions", "nationalCompetitions"];

export const COMPETITION_CATEGORY_BY_KEY = {
  premier_league: "leagues",
  persian_gulf_pro_league: "leagues",
  la_liga: "leagues",
  serie_a: "leagues",
  bundesliga: "leagues",
  ligue_1: "leagues",
  champions_league: "clubCompetitions",
  europa_league: "clubCompetitions",
  worldcup2026: "nationalCompetitions",
};
