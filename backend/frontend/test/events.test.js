import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  canShowCompetitionEvents,
  competitionEventIdentity,
  competitionEventIdentityKey,
  eventRequestFailureKind,
  getEventPlayer,
  getEventTypeLabel,
  getFirstEventValue,
  getRenderedEventIcon,
  isCurrentEventRequest,
  resolveEventTeam,
} from "../src/utils/events.js";

const testDirectory = fileURLToPath(new URL(".", import.meta.url));
const source = (relativePath) => readFileSync(
  new URL(relativePath, `file:///${testDirectory.replaceAll("\\", "/")}`),
  "utf8",
);

const supportedCompetition = {
  competition_key: "premier_league",
  season_key: "2026-2027",
  supports_events: true,
};
const sharedMatch = {
  id: "mp_match_shared",
  kickoff_utc: "2026-09-01T12:00:00Z",
  status: "finished",
};

test("generic event identity isolates competition and season scopes", () => {
  const premier = competitionEventIdentity(supportedCompetition, sharedMatch);
  const laLiga = competitionEventIdentity(
    { ...supportedCompetition, competition_key: "la_liga" },
    sharedMatch,
  );
  const nextSeason = competitionEventIdentity(
    { ...supportedCompetition, season_key: "2027-2028" },
    sharedMatch,
  );

  assert.notEqual(competitionEventIdentityKey(premier), competitionEventIdentityKey(laLiga));
  assert.notEqual(competitionEventIdentityKey(premier), competitionEventIdentityKey(nextSeason));
  assert.equal(
    competitionEventIdentityKey(premier),
    "premier_league:2026-2027:mp_match_shared",
  );
  assert.equal(
    competitionEventIdentity(supportedCompetition, { id: "480301" }),
    null,
  );
});

test("authoritative capability and match status control event visibility", () => {
  assert.equal(
    canShowCompetitionEvents(supportedCompetition, { ...sharedMatch, status: "live" }),
    true,
  );
  assert.equal(canShowCompetitionEvents(supportedCompetition, sharedMatch), true);
  assert.equal(
    canShowCompetitionEvents(
      supportedCompetition,
      { ...sharedMatch, kickoff_utc: "2099-09-01T12:00:00Z", status: "upcoming" },
    ),
    false,
  );
  assert.equal(
    canShowCompetitionEvents(
      supportedCompetition,
      {
        ...sharedMatch,
        can_show_event_button: true,
        kickoff_utc: "2099-09-01T12:00:00Z",
        status: "upcoming",
      },
    ),
    false,
  );
  assert.equal(
    canShowCompetitionEvents({ ...supportedCompetition, supports_events: false }, sharedMatch),
    false,
  );
  assert.equal(
    canShowCompetitionEvents(
      {
        competition_key: "worldcup2026",
        season_key: "2026",
        supports_events: false,
      },
      sharedMatch,
    ),
    false,
  );
});

test("event failures map to safe UI states", () => {
  assert.equal(eventRequestFailureKind(404), "unavailable");
  assert.equal(eventRequestFailureKind(501), "unavailable");
  assert.equal(eventRequestFailureKind(502), "failed");
  assert.equal(eventRequestFailureKind(500), "failed");
});

test("request currency rejects aborted and cross-scope responses", () => {
  const currentController = new AbortController();
  const oldController = new AbortController();
  const active = {
    controller: currentController,
    identityKey: "premier_league:2026-2027:mp_match_shared",
    version: 3,
  };

  assert.equal(isCurrentEventRequest(active, active.identityKey, 3), true);
  assert.equal(isCurrentEventRequest(active, "la_liga:2026-2027:mp_match_shared", 3), false);
  assert.equal(isCurrentEventRequest(active, active.identityKey, 2), false);
  oldController.abort();
  assert.equal(
    isCurrentEventRequest({ ...active, controller: oldController }, active.identityKey, 3),
    false,
  );
});

test("scoped API helper uses only canonical competition season match route", () => {
  const api = source("../src/api/football.js");
  const helperStart = api.indexOf("export function fetchCompetitionMatchEvents");
  const helperEnd = api.indexOf("export function fetchMatchEvents", helperStart);
  const helper = api.slice(helperStart, helperEnd);

  assert.match(helper, /canonicalMatchId\.startsWith\("mp_match_"\)/);
  assert.match(
    helper,
    /competitions\/\$\{competition\}\/seasons\/\$\{season\}\/matches\/\$\{match\}\/events/,
  );
  assert.match(helper, /options,/);
  assert.doesNotMatch(helper, /COMPETITIONS|worldcup2026|provider|external/);
});

test("CompetitionPage fetches events only from the click handler with scoped race guards", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  const handlerStart = page.indexOf("const toggleMatchEvents");
  const handlerEnd = page.indexOf("const renderDisplayMatchCard", handlerStart);
  const handler = page.slice(handlerStart, handlerEnd);
  const firstEffect = page.indexOf("useEffect(");

  assert.ok(handlerStart > firstEffect);
  assert.match(handler, /fetchCompetitionMatchEvents\(/);
  assert.match(handler, /eventRequestRef\.current/);
  assert.match(handler, /controller\.abort\(\)/);
  assert.match(handler, /isCurrentEventRequest\(/);
  assert.match(handler, /eventRequestFailureKind\(error\.status\)/);
  assert.doesNotMatch(page.slice(0, handlerStart), /fetchCompetitionMatchEvents\(/);
  assert.doesNotMatch(handler, /setInterval|setTimeout/);
});

test("league overview matches and knockout matches share the same MatchCard event path", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  const knockout = source("../src/components/competitions/KnockoutRound.jsx");

  assert.match(page, /const renderDisplayMatchCard/);
  assert.match(page, /renderMatch=\{\(match, matchIndex\) => renderDisplayMatchCard\(/);
  assert.match(page, /showEvents=\{Boolean\(eventIdentityKey && canShowCompetitionEvents/);
  assert.match(knockout, /if \(renderMatch\) return renderMatch\(match, index\)/);
});

test("existing MatchCard states and EventRow render normalized and legacy fields", () => {
  const card = source("../src/components/matches/MatchCard.jsx");
  const row = source("../src/components/matches/EventRow.jsx");
  const genericEvent = {
    player_name: "Scorer",
    assist_name: "Assistant",
    player_in_name: "Incoming",
    player_out_name: "Outgoing",
  };

  assert.equal(getEventPlayer(genericEvent), "Scorer");
  assert.equal(getFirstEventValue(genericEvent, ["assist", "assist_name"]), "Assistant");
  assert.equal(getFirstEventValue(genericEvent, ["player_in_name", "player_in"]), "Incoming");
  assert.equal(getEventTypeLabel("second_yellow_red", "en"), "Second yellow/red card");
  assert.notEqual(getRenderedEventIcon("var"), "•");
  assert.match(card, /isLoadingEvents \?/);
  assert.match(card, /eventsFailed \?/);
  assert.match(card, /eventsUnavailable \?/);
  assert.match(card, /events\.length > 0 \?/);
  assert.match(card, /t\.noEvents/);
  assert.match(row, /player_in_name/);
  assert.match(row, /player_out_name/);
  assert.match(row, /event\.home_score/);
  assert.match(row, /event\.away_score/);
  assert.match(row, /getFirstEventValue\(event, \["description"\]\)/);
  assert.match(row, /\["goal", "penalty_goal", "own_goal"\]/);
});

test("event teams preserve national flags and resolve home and away club logos", () => {
  const match = {
    home_flag: "🇪🇸",
    home_logo: "https://images.example/home.png",
    home_fa: "میزبان",
    home_en: "Home",
    away_flag: "",
    away_logo: "https://images.example/away.png",
    away_fa: "مهمان",
    away_en: "Away",
  };

  assert.deepEqual(resolveEventTeam({ team_side: "home" }, match, "en"), {
    flag: "🇪🇸",
    logo: "https://images.example/home.png",
    name: "Home",
    englishName: "Home",
  });
  assert.deepEqual(resolveEventTeam({ team_side: "away" }, match, "en"), {
    flag: "",
    logo: "https://images.example/away.png",
    name: "Away",
    englishName: "Away",
  });
  assert.deepEqual(resolveEventTeam({ team_name: "Unknown club" }, match, "en"), {
    flag: "",
    logo: "",
    name: "Unknown club",
    englishName: "Unknown club",
  });
});

test("EventRow passes flag and logo through TeamFlag's existing fallback order", () => {
  const row = source("../src/components/matches/EventRow.jsx");
  const teamFlag = source("../src/components/teams/TeamFlag.jsx");

  assert.match(row, /flagEmoji=\{team\.flag\}/);
  assert.match(row, /logoUrl=\{team\.logo\}/);
  assert.match(row, /teamName=\{team\.englishName\}/);
  assert.match(row, /team\.name \|\| team\.flag \|\| team\.logo/);
  assert.match(teamFlag, /const imageUrl = flagImageUrl \|\| backendLogoUrl/);
  assert.match(teamFlag, /flagEmoji \|\| "⚽"/);
  assert.match(row, /type === "substitution"/);
  assert.match(row, /getEventPlayer\(event\)/);
  assert.match(row, /providedLabel \|\| getEventTypeLabel\(type, lang\)/);
});

test("World Cup archive remains separate from generic event controls", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  const archive = source("../src/pages/ArchivedCompetitionPage.jsx");

  assert.match(page, /competitionExperience\(props\.competition\) === "archive"/);
  assert.match(page, /return <ArchivedCompetitionPage/);
  assert.doesNotMatch(archive, /fetchCompetitionMatchEvents|MatchCard|supports_events/);
});
