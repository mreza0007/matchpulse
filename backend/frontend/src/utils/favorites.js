import { supportsNewCompetitionAction } from "./competitionCapabilities.js";

function displayText(values) {
  return values.find((value) => typeof value === "string" && value.trim()
    && !/^[\d\u06f0-\u06f9\u0660-\u0669]+$/.test(value.trim()))?.trim() || "";
}

export function favoriteDisplayName(team, lang) {
  const fa = [team?.team_name_fa, team?.name_fa];
  const en = [team?.team_name_en, team?.name_en];
  return displayText(lang === "fa" ? [...fa, team?.team_name, ...en] : [...en, team?.team_name, ...fa]);
}

export function favoriteCompetitionName(favorite, lang) {
  const competition = favorite?.competition;
  return displayText(lang === "fa"
    ? [competition?.name_fa, competition?.name_en]
    : [competition?.name_en, competition?.name_fa]);
}

export function favoriteMatchTeam(match, side) {
  const id = match?.[`${side}_team_id`];
  if (typeof id !== "string" || !id.startsWith("mp_team_")) return null;
  return { id, name_fa: match[`${side}_fa`], name_en: match[`${side}_en`],
    logo: match[`${side}_logo`], flag: match[`${side}_flag`] };
}

export function favoriteControl(competition, team, keys, pendingKeys) {
  const key = team ? `${competition?.competition_key}:${team.id}` : "";
  const active = Boolean(key && keys?.has(key));
  return { active, pending: Boolean(key && pendingKeys?.has(key)),
    visible: Boolean(team && (active || supportsNewCompetitionAction(competition, "supports_favorites"))) };
}
