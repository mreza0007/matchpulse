import { getLocalizedTeamName } from "./teams.js";
import {
  isFinishedMatch,
  isLiveMatch,
  isPastPendingResult,
} from "./matches.js";

const EVENT_LABELS = {
  fa: {
    goal: "\u06af\u0644",
    penalty_goal: "\u06af\u0644 \u067e\u0646\u0627\u0644\u062a\u06cc",
    penalty_event: "\u0631\u0648\u06cc\u062f\u0627\u062f \u067e\u0646\u0627\u0644\u062a\u06cc",
    own_goal: "\u06af\u0644 \u0628\u0647 \u062e\u0648\u062f\u06cc",
    var_disallowed_goal: "\u06af\u0644 \u0645\u0631\u062f\u0648\u062f \u0628\u0627 VAR",
    disallowed_goal: "\u06af\u0644 \u0645\u0631\u062f\u0648\u062f \u0628\u0627 VAR",
    penalty_missed: "\u067e\u0646\u0627\u0644\u062a\u06cc \u062e\u0631\u0627\u0628\u200c\u0634\u062f\u0647",
    missed_penalty: "\u067e\u0646\u0627\u0644\u062a\u06cc \u062e\u0631\u0627\u0628\u200c\u0634\u062f\u0647",
    assist: "\u067e\u0627\u0633 \u06af\u0644",
    yellow_card: "\u06a9\u0627\u0631\u062a \u0632\u0631\u062f",
    second_yellow_red: "\u06a9\u0627\u0631\u062a \u0632\u0631\u062f \u062f\u0648\u0645",
    red_card: "\u06a9\u0627\u0631\u062a \u0642\u0631\u0645\u0632",
    substitution: "\u062a\u0639\u0648\u06cc\u0636",
    var: "VAR",
    halftime: "\u067e\u0627\u06cc\u0627\u0646 \u0646\u06cc\u0645\u0647 \u0627\u0648\u0644",
    fulltime: "\u067e\u0627\u06cc\u0627\u0646 \u0628\u0627\u0632\u06cc",
    kickoff: "\u0634\u0631\u0648\u0639 \u0628\u0627\u0632\u06cc",
    other: "\u0631\u0648\u06cc\u062f\u0627\u062f",
    unknown: "\u0631\u0648\u06cc\u062f\u0627\u062f",
  },
  en: {
    goal: "Goal",
    penalty_goal: "Penalty goal",
    penalty_event: "Penalty event",
    own_goal: "Own goal",
    var_disallowed_goal: "VAR-disallowed goal",
    disallowed_goal: "VAR-disallowed goal",
    penalty_missed: "Missed penalty",
    missed_penalty: "Missed penalty",
    assist: "Assist",
    yellow_card: "Yellow card",
    second_yellow_red: "Second yellow/red card",
    red_card: "Red card",
    substitution: "Substitution",
    var: "VAR",
    halftime: "Half-time",
    fulltime: "Full-time",
    kickoff: "Kick-off",
    other: "Event",
    unknown: "Event",
  },
};

export function getEventTypeLabel(type, lang) {
  return EVENT_LABELS[lang]?.[type] || EVENT_LABELS[lang]?.unknown || "Event";
}

export function getEventIcon(type) {
  if (type === "goal") return "⚽";
  if (type === "yellow_card") return "🟨";
  if (type === "red_card") return "🟥";
  if (type === "substitution") return "🔁";
  return "•";
}

export function getLegacyEventIcon(type) {
  if (type === "goal") return "⚽";
  if (type === "yellow_card") return "🟨";
  if (type === "red_card") return "🟥";
  if (type === "substitution") return "🔁";
  return "•";
}

void getEventIcon;
void getLegacyEventIcon;

export function getFirstEventValue(event, keys) {
  for (const key of keys) {
    const value = event?.[key];

    if (value !== undefined && value !== null && value !== "") return value;
  }

  return "";
}

export function normalizeEventSide(event) {
  const side = String(
    getFirstEventValue(event, ["team_side", "side", "home_or_away", "team"]) || "",
  )
    .toLowerCase()
    .replace(/[-\s]/g, "_");

  if (["home", "host", "home_team"].includes(side)) return "home";
  if (["away", "guest", "away_team"].includes(side)) return "away";
  return "";
}

export function resolveEventTeam(event, match, lang) {
  const side = normalizeEventSide(event);

  if (side === "home") {
    return {
      flag: match.home_flag,
      logo: match.home_logo,
      name: getLocalizedTeamName(match, "home", lang),
      englishName: match.home_en,
    };
  }

  if (side === "away") {
    return {
      flag: match.away_flag,
      logo: match.away_logo,
      name: getLocalizedTeamName(match, "away", lang),
      englishName: match.away_en,
    };
  }

  const teamName = getFirstEventValue(event, ["team_name", "teamName"]);
  const blockedNames = new Set(["home", "away", "host", "guest", "میزبان", "مهمان"]);

  return {
    flag: "",
    logo: "",
    name: blockedNames.has(String(teamName).toLowerCase()) ? "" : teamName,
    englishName: teamName,
  };
}

export function getEventPlayer(event) {
  return getFirstEventValue(event, [
    "player",
    "player_name",
    "playerName",
    "scorer",
    "goal_scorer",
  ]);
}

export function getNormalizedEventType(event) {
  return String(event?.normalized_type || event?.event_type || event?.type || "unknown").toLowerCase();
}

export function getRenderedEventIcon(type) {
  return {
    goal: "\u26bd",
    penalty_goal: "\u26bd",
    own_goal: "\u26bd\u21a9\ufe0f",
    var_disallowed_goal: "\ud83d\udcf9",
    disallowed_goal: "\ud83d\udcf9",
    penalty_event: "\u26aa",
    penalty_missed: "\u274c",
    missed_penalty: "\u274c",
    yellow_card: "\ud83d\udfe8",
    second_yellow_red: "\ud83d\udfe8\ud83d\udfe5",
    red_card: "\ud83d\udfe5",
    substitution: "\ud83d\udd01",
    var: "\ud83c\udfa5",
  }[type] || "\u2022";
}

function eventIdentityPart(value) {
  return String(value ?? "").trim().toLowerCase();
}

export function competitionEventIdentity(competition, match) {
  const competitionKey = eventIdentityPart(competition?.competition_key);
  const seasonKey = eventIdentityPart(competition?.season_key);
  const matchId = String(match?.id ?? "").trim();
  if (!competitionKey || !seasonKey || !matchId.startsWith("mp_match_")) return null;
  return {
    competition_key: competitionKey,
    season_key: seasonKey,
    match_id: matchId,
  };
}

export function competitionEventIdentityKey(identity) {
  if (!identity) return "";
  return [
    eventIdentityPart(identity.competition_key),
    eventIdentityPart(identity.season_key),
    String(identity.match_id ?? "").trim(),
  ].join(":");
}

export function canShowCompetitionEvents(competition, match) {
  return Boolean(
    competition?.supports_events === true
    && match?.id
    && (isFinishedMatch(match) || isLiveMatch(match) || isPastPendingResult(match)),
  );
}

export function eventRequestFailureKind(status) {
  if (status === 404 || status === 501) return "unavailable";
  return "failed";
}

export function isCurrentEventRequest(activeRequest, identityKey, version) {
  return Boolean(
    activeRequest
    && activeRequest.identityKey === identityKey
    && activeRequest.version === version
    && activeRequest.controller?.signal?.aborted !== true
  );
}
