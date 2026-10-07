export const NATIONS_LEAGUE_KEY = "uefa_nations_league";
export const NATIONS_LEAGUE_DIVISIONS = ["a", "b", "c", "d"];

export function nationsLeagueDivision(key) {
  return NATIONS_LEAGUE_DIVISIONS.find((division) => key === `${NATIONS_LEAGUE_KEY}_${division}`) || "";
}

export function isNationsLeague(key) {
  return key === NATIONS_LEAGUE_KEY || Boolean(nationsLeagueDivision(key));
}

export function competitionNavigationKey(location) {
  if (!location) return "";
  const query = new URLSearchParams(location.search || "");
  const hash = String(location.hash || "").replace(/^#\/?/, "");
  const key = query.get("competition") || query.get("competition_key")
    || hash.replace(/^competitions\//, "").split(/[/?]/)[0];
  return /^[a-z][a-z0-9_]*$/.test(key || "") ? key : "";
}

export function nationsLeaguePresentation() {
  return {
    competition_key: NATIONS_LEAGUE_KEY,
    name_fa: "لیگ ملت‌های اروپا",
    name_en: "UEFA Nations League",
    logo_src: "/competition-logos/uefa-nations-league.png",
  };
}

// This groups presentation only; capabilities and API identities stay on each division.
export function groupCompetitionDirectory(competitions) {
  const divisions = NATIONS_LEAGUE_DIVISIONS.flatMap((division) => (
    competitions.filter((item) => item.competition_key === `${NATIONS_LEAGUE_KEY}_${division}`)
  ));
  let inserted = false;
  return competitions.flatMap((competition) => {
    if (!nationsLeagueDivision(competition.competition_key)) return [competition];
    if (inserted) return [];
    inserted = true;
    return [{ ...nationsLeaguePresentation(), season_key: divisions[0]?.season_key, divisions }];
  });
}

export function resolveNationsLeagueDivision(divisions, key) {
  return divisions.find((item) => item.competition_key === key)
    || divisions.find((item) => item.competition_key === `${NATIONS_LEAGUE_KEY}_a`)
    || divisions[0]
    || null;
}

export function formatSeasonLabel(season) {
  const value = String(season || "");
  const digits = value.replace(/[۰-۹٠-٩]/g, (digit) => (
    String("۰۱۲۳۴۵۶۷۸۹".includes(digit)
      ? "۰۱۲۳۴۵۶۷۸۹".indexOf(digit)
      : "٠١٢٣٤٥٦٧٨٩".indexOf(digit))
  ));
  const years = digits.match(/^(\d{4})\s*[-–/]\s*(\d{4})$/);
  if (!years) return value;
  return [years[1], years[2]].sort((left, right) => Number(left) - Number(right)).join("-");
}

export function competitionTabs(competition) {
  const tabs = ["overview"];
  if (competition.supports_matches === true) tabs.push("matches");
  if (competition.supports_standings === true) tabs.push("standings");
  if (competition.supports_groups === true) tabs.push("groups");
  if (competition.supports_knockout === true) tabs.push("knockout");
  // No statistics endpoint/capability currently exists; do not expose a dead tab.
  // Teams use the existing universal scoped teams endpoint, without a capability flag.
  tabs.push("teams");
  return tabs;
}
