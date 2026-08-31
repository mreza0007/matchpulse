import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  buildReminderIdentitySet,
  finishReminderMutation,
  isReminderEligibleMatch,
  reminderErrorTranslationKey,
  reminderIdentity,
  reminderIdentityFromMatch,
  reminderIdentityKey,
  reminderIdentityKeyFromRecord,
  reminderRequestBody,
  tryBeginReminderMutation,
} from "../src/utils/reminders.js";
import { supportsNewCompetitionAction } from "../src/utils/competitionCapabilities.js";

const testDirectory = fileURLToPath(new URL(".", import.meta.url));
const source = (relativePath) => readFileSync(
  new URL(relativePath, `file:///${testDirectory.replaceAll("\\", "/")}`),
  "utf8",
);

const futureMatch = {
  id: "shared-match",
  status: "upcoming",
  is_live: false,
  is_finished: false,
  kickoff_utc: "2099-09-01T12:00:00Z",
};

test("scoped reminder identity isolates competitions and seasons", () => {
  const premier = reminderIdentity("premier_league", "2026-2027", "shared-match");
  const laLiga = reminderIdentity("la_liga", "2026-2027", "shared-match");
  const nextSeason = reminderIdentity("premier_league", "2027-2028", "shared-match");

  assert.notEqual(reminderIdentityKey(premier), reminderIdentityKey(laLiga));
  assert.notEqual(reminderIdentityKey(premier), reminderIdentityKey(nextSeason));
  assert.deepEqual(
    reminderIdentityFromMatch(
      { competition_key: "PREMIER_LEAGUE", season_key: "2026-2027" },
      futureMatch,
    ),
    premier,
  );
});

test("reminder request body contains only the scoped trusted identity", () => {
  const body = reminderRequestBody(
    42,
    reminderIdentity("premier_league", "2026-2027", "shared-match"),
  );

  assert.deepEqual(body, {
    telegram_id: 42,
    competition_key: "premier_league",
    season_key: "2026-2027",
    match_id: "shared-match",
  });
  assert.deepEqual(Object.keys(body), [
    "telegram_id",
    "competition_key",
    "season_key",
    "match_id",
  ]);

  const api = source("../src/api/user.js");
  assert.match(api, /JSON\.stringify\(reminderRequestBody\(telegramId, identity\)\)/);
  assert.doesNotMatch(api, /home_(?:team|name)|away_(?:team|name)|kickoff_utc|provider/);
});

test("reminder loading deduplicates exact scopes and ignores malformed rows", () => {
  const records = [
    {
      competition_key: "worldcup2026",
      season_key: "2026",
      match_id: "17",
    },
    {
      competition_key: "premier_league",
      season_key: "2026-2027",
      match_id: "17",
    },
    {
      competition_key: "premier_league",
      season_key: "2026-2027",
      match_id: "17",
    },
    { competition_key: "premier_league", match_id: "incomplete" },
    {
      competition_key: "premier_league",
      season_key: "2026-2027",
      id: "must-not-be-used-as-match-id",
    },
    null,
  ];
  const active = buildReminderIdentitySet(records);

  assert.equal(active.size, 2);
  assert.equal(active.has(reminderIdentityKeyFromRecord(records[0])), true);
  assert.equal(active.has(reminderIdentityKeyFromRecord(records[1])), true);
  assert.equal(reminderIdentityKeyFromRecord(records[4]), "");
});

test("UI eligibility allows any future upcoming match without prediction scope coupling", () => {
  assert.equal(isReminderEligibleMatch(futureMatch, Date.parse("2099-08-01T00:00:00Z")), true);
  assert.equal(
    isReminderEligibleMatch(
      { ...futureMatch, round: "Week 99", prediction_scope: "not-selected" },
      Date.parse("2099-08-01T00:00:00Z"),
    ),
    true,
  );
});

test("UI eligibility rejects live, finished, invalid kickoff, and started matches", () => {
  const now = Date.parse("2099-08-01T00:00:00Z");
  const cases = [
    { ...futureMatch, status: "live" },
    { ...futureMatch, is_live: true },
    { ...futureMatch, status: "finished", is_finished: true },
    { ...futureMatch, kickoff_utc: null },
    { ...futureMatch, kickoff_utc: "not-a-date" },
    { ...futureMatch, kickoff_utc: "2099-09-01T12:00:00" },
    { ...futureMatch, kickoff_utc: "2099-07-01T12:00:00Z" },
  ];

  for (const match of cases) {
    assert.equal(isReminderEligibleMatch(match, now), false);
  }
});

test("reminder error statuses map to stable friendly messages", () => {
  assert.equal(reminderErrorTranslationKey(409), "reminderIneligible");
  assert.equal(reminderErrorTranslationKey(404), "reminderStale");
  assert.equal(reminderErrorTranslationKey(501), "reminderDisabled");
  assert.equal(reminderErrorTranslationKey(502), "reminderProviderError");
  assert.equal(reminderErrorTranslationKey(503), "reminderStorageError");
  assert.equal(reminderErrorTranslationKey(500), "reminderError");
});

test("CompetitionPage uses backend capability metadata and one MatchCard control", () => {
  const competitionPage = source("../src/pages/CompetitionPage.jsx");
  const matchCard = source("../src/components/matches/MatchCard.jsx");
  const activeCompetition = {
    competition_key: "premier_league",
    is_active: true,
    status: "active",
    supports_reminders: true,
  };
  const archivedWorldCup = {
    competition_key: "worldcup2026",
    is_active: false,
    status: "archived",
    supports_reminders: false,
  };

  assert.equal(supportsNewCompetitionAction(activeCompetition, "supports_reminders"), true);
  assert.equal(supportsNewCompetitionAction(archivedWorldCup, "supports_reminders"), false);
  assert.equal(isReminderEligibleMatch(futureMatch), true);


  assert.match(
    competitionPage,
    /supportsNewCompetitionAction\(\s*competition, "supports_reminders",?\s*\)/,
  );
  assert.match(competitionPage, /isReminderEligibleMatch\(match\)/);
  assert.match(competitionPage, /onReminderToggle\(competition, selectedMatch\)/);
  assert.doesNotMatch(competitionPage, /prediction_scope|predictable/);
  assert.equal((matchCard.match(/className=\{`remind-btn/g) || []).length, 1);
  assert.match(matchCard, /disabled=\{isReminderPending\}/);
});

test("World Cup archive cannot render a new reminder action", () => {
  const competitionPage = source("../src/pages/CompetitionPage.jsx");
  const archivePage = source("../src/pages/ArchivedCompetitionPage.jsx");

  assert.match(competitionPage, /competitionExperience\(props\.competition\) === "archive"/);
  assert.match(competitionPage, /return <ArchivedCompetitionPage/);
  assert.doesNotMatch(archivePage, /MatchCard|onReminderToggle|supports_reminders/);
});

test("Profile retains context and deletes the exact stored reminder", () => {
  const profilePage = source("../src/pages/ProfilePage.jsx");

  assert.match(profilePage, /reminders\.map\(\(match, index\) =>/);
  assert.match(profilePage, /reminderIdentityKeyFromRecord\(match\)/);
  assert.match(profilePage, /match\?\.competition_key/);
  assert.match(profilePage, /match\?\.season_key/);
  assert.match(profilePage, /malformed-reminder:\$\{index\}/);
  assert.match(profilePage, /disabled=\{!identityKey \|\| isReminderPending\}/);
  assert.match(profilePage, /onRemoveReminder\(match\)/);
  assert.doesNotMatch(profilePage, /filter.*reminder|supports_reminders/);
});

test("exact-key mutation lock blocks double clicks and allows parallel scopes", () => {
  const pending = new Set();
  const first = reminderIdentityKey(
    reminderIdentity("premier_league", "2026-2027", "shared-match"),
  );
  const second = reminderIdentityKey(
    reminderIdentity("la_liga", "2026-2027", "shared-match"),
  );

  assert.equal(tryBeginReminderMutation(pending, first), true);
  assert.equal(tryBeginReminderMutation(pending, first), false);
  assert.equal(tryBeginReminderMutation(pending, second), true);
  finishReminderMutation(pending, first);
  assert.equal(tryBeginReminderMutation(pending, first), true);
  assert.equal(pending.has(second), true);
});

test("mutation failures preserve scoped state until a successful response", () => {
  const app = source("../src/App.jsx");
  const addCatch = app.slice(
    app.indexOf(".catch((error) => {", app.indexOf("const addReminder")),
    app.indexOf(".finally(", app.indexOf("const addReminder")),
  );
  const removeCatch = app.slice(
    app.indexOf(".catch((error) => {", app.indexOf("const removeReminder")),
    app.indexOf(".finally(", app.indexOf("const removeReminder")),
  );

  assert.doesNotMatch(addCatch, /setReminders/);
  assert.doesNotMatch(removeCatch, /setReminders/);
  assert.match(app, /reminderFailureMessage\(error\.status\)/);
});
