import { supportsNewCompetitionAction } from "./competitionCapabilities.js";

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
