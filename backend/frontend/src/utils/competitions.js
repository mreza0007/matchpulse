export function getCompetitionName(competition, lang) {
  if (lang === "fa") return competition.name_fa || competition.name_en || competition.competition_key || "";
  return competition.name_en || competition.name_fa || competition.competition_key || "";
}
