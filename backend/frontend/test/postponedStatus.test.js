import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { translations } from "../src/config/translations.js";
import {
  canShowEvents,
  getHeroMatch,
  getHeroMode,
  getHeroStatusLine,
  getMatchStatus,
  isFinishedMatch,
  isFutureMatchStatus,
  isLiveMatch,
  isPostponedMatch,
  isPredictionLocked,
  normalizeMatchStatus,
} from "../src/utils/matches.js";
import { isReminderEligibleMatch } from "../src/utils/reminders.js";

const testDirectory = fileURLToPath(new URL(".", import.meta.url));
const source = (relativePath) => readFileSync(
  new URL(relativePath, `file:///${testDirectory.replaceAll("\\", "/")}`),
  "utf8",
);
const postponed = {
  id: "mp_match_postponed",
  status: "postponed",
  is_live: false,
  is_finished: false,
  is_upcoming: false,
  kickoff_utc: "2099-09-12T12:00:00Z",
};

test("postponed is a first-class non-playing status", () => {
  assert.equal(normalizeMatchStatus(postponed), "postponed");
  assert.equal(normalizeMatchStatus({ status: "unknown", status_title: "تعویق" }), "postponed");
  assert.equal(normalizeMatchStatus({ status: "unknown", statusTitle: " Postponed " }), "postponed");
  assert.equal(normalizeMatchStatus({ ...postponed, is_live: true }), "postponed");
  assert.equal(isPostponedMatch(postponed), true);
  assert.equal(isLiveMatch(postponed), false);
  assert.equal(isFinishedMatch(postponed), false);
  assert.equal(isFutureMatchStatus(postponed), false);
  assert.equal(canShowEvents(postponed), false);
});

test("future kickoff does not unlock prediction or future eligibility", () => {
  assert.equal(isFutureMatchStatus({ ...postponed, is_upcoming: true }), false);
  assert.equal(isPredictionLocked(postponed), true);
  assert.equal(isReminderEligibleMatch(postponed), false);
});

test("postponed translations and status labels are explicit", () => {
  assert.equal(translations.fa.statusPostponed, "به تعویق افتاده");
  assert.equal(translations.en.statusPostponed, "Postponed");
  assert.deepEqual(
    getMatchStatus(postponed, "fa", translations.fa),
    { key: "postponed", label: "به تعویق افتاده" },
  );
  assert.deepEqual(
    getMatchStatus(postponed, "en", translations.en),
    { key: "postponed", label: "Postponed" },
  );
});

test("existing live, upcoming, finished, pending-result and live-phase status behavior remains", () => {
  assert.equal(normalizeMatchStatus({ status: "live" }), "live");
  assert.equal(normalizeMatchStatus({ status: "unknown", status_title: "half time" }), "live");
  assert.equal(normalizeMatchStatus({ status: "unknown", status_title: "ضربات پنالتی" }), "live");
  assert.equal(normalizeMatchStatus({ status: "finished" }), "finished");
  assert.equal(normalizeMatchStatus({ status: "pending_result" }), "pending_result");
  assert.equal(normalizeMatchStatus({ status: "upcoming" }), "upcoming");
});

test("postponed cannot become a live, upcoming, or result hero", () => {
  const live = { id: "live", status: "live" };
  const upcoming = { id: "upcoming", status: "upcoming" };
  const finished = { id: "finished", status: "finished" };
  assert.equal(getHeroMatch([postponed, live], [postponed, upcoming], [postponed, finished]), live);
  assert.equal(getHeroMatch([postponed], [postponed], [postponed]), null);
  assert.equal(getHeroMode(postponed), "postponed");
  assert.deepEqual(
    getHeroStatusLine(postponed, getHeroMode(postponed), "en", translations.en, Date.now()),
    { label: "", value: "Postponed", isCountdown: false },
  );
});

test("MatchCard renders a neutral label without live, score, time, or reminder behavior", () => {
  const card = source("../src/components/matches/MatchCard.jsx");
  const css = source("../src/App.css");
  assert.match(card, /matchStatus\.key === "postponed"/);
  assert.match(card, /className="match-status postponed"/);
  assert.match(card, /showReminder && !isPostponed/);
  assert.match(card, /!isPostponed && <span>🕒/);
  assert.match(card, /\["upcoming", "pending_result", "postponed"\]\.includes/);
  assert.doesNotMatch(card, /match-status postponed live-pulse/);
  assert.match(css, /\.match-status\.postponed/);
});

test("Home and Live retain postponed rows in normal date groups without hero promotion", () => {
  const home = source("../src/pages/HomePage.jsx");
  const live = source("../src/pages/LivePage.jsx");
  assert.match(home, /todayMatches\.filter\(isLiveMatch\)/);
  assert.match(home, /\(group\.matches \|\| \[\]\)\.map\(\(match\) => renderMatch/);
  assert.match(live, /\(group\.matches \|\| \[\]\)\.map\(\(match, matchIndex\) =>/);
  assert.doesNotMatch(home, /filter\([^)]*postponed/);
  assert.doesNotMatch(live, /filter\([^)]*postponed/);
});
