import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  INITIAL_VISIBLE_MATCH_GROUPS,
  MATCH_GROUP_CHUNK_SIZE,
  initialVisibleGroupCount,
  nextVisibleGroupCount,
  visibleGroupSlice,
} from "../src/utils/progressiveGroups.js";

const testDirectory = fileURLToPath(new URL(".", import.meta.url));
const source = (relativePath) => readFileSync(
  new URL(relativePath, `file:///${testDirectory.replaceAll("\\", "/")}`),
  "utf8",
);

test("full schedules initially expose ten date groups", () => {
  const groups = Array.from({ length: 24 }, (_, index) => ({ dateKey: String(index) }));
  assert.equal(INITIAL_VISIBLE_MATCH_GROUPS, 10);
  assert.equal(initialVisibleGroupCount(groups.length), 10);
  assert.deepEqual(visibleGroupSlice(groups, 10), groups.slice(0, 10));
});

test("date groups progress in bounded chunks until all are visible", () => {
  assert.equal(MATCH_GROUP_CHUNK_SIZE, 8);
  assert.equal(nextVisibleGroupCount(10, 24), 18);
  assert.equal(nextVisibleGroupCount(18, 24), 24);
  assert.equal(nextVisibleGroupCount(24, 24), 24);
  assert.equal(initialVisibleGroupCount(4), 4);
});

test("CompetitionPage resets only when a successful full payload is installed", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  const directory = source("../src/pages/CompetitionsPage.jsx");
  const successStart = page.indexOf("const groups = groupMatchesByDate(items, \"en\")");
  const eventStart = page.indexOf("const toggleMatchEvents");
  const eventEnd = page.indexOf("const renderDisplayMatchCard", eventStart);
  const reminderStart = page.indexOf("function DisplayMatchCard");
  const reminderEnd = page.indexOf("function teamName", reminderStart);

  assert.notEqual(successStart, -1);
  assert.match(page.slice(successStart, successStart + 260), /setVisibleMatchGroupCount\(initialVisibleGroupCount\(groups\.length\)\)/);
  assert.doesNotMatch(page.slice(eventStart, eventEnd), /setVisibleMatchGroupCount/);
  assert.doesNotMatch(page.slice(reminderStart, reminderEnd), /setVisibleMatchGroupCount/);
  assert.match(directory, /key=\{`\$\{selectedCompetition\.competition_key\}:\$\{selectedCompetition\.season_key \|\| ""\}`\}/);
});

test("CompetitionPage supports observer loading and an explicit fallback control", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  assert.match(page, /new IntersectionObserver/);
  assert.match(page, /visibleMatchGroups\.map/);
  assert.match(page, /ref=\{matchGroupSentinelRef\}/);
  assert.match(page, /onClick=\{loadMoreMatchGroups\}/);
  assert.match(page, /t\.loadMoreMatches/);
});

test("MatchCard memoization keeps volatile UI props authoritative and logo props stable", () => {
  const card = source("../src/components/matches/MatchCard.jsx");
  const competitionPage = source("../src/pages/CompetitionPage.jsx");
  const homePage = source("../src/pages/HomePage.jsx");

  assert.match(card, /export default memo\(MatchCard\)/);
  assert.match(card, /const predictionLocked = showPredictions &&/);
  assert.match(card, /const showPrediction = showPredictions &&/);
  assert.match(competitionPage, /homeLogo=\{match\.home_logo \|\| ""\}/);
  assert.match(homePage, /awayLogo=\{match\.away_logo \|\| ""\}/);
  assert.match(card, /isExpanded= false|isExpanded = false/);
  assert.match(card, /isReminderActive/);
});
