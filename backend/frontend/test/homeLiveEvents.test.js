import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  createScopedMatchEventController,
  matchEventIdentity,
} from "../src/utils/scopedMatchEvents.js";

const testDirectory = fileURLToPath(new URL(".", import.meta.url));
const source = (relativePath) => readFileSync(
  new URL(relativePath, `file:///${testDirectory.replaceAll("\\", "/")}`),
  "utf8",
);
const match = (overrides = {}) => ({
  id: "mp_match_331c27325ef7c347a72beb3d",
  competition_key: "la_liga",
  season_key: "2026-2027",
  status: "finished",
  ...overrides,
});
const response = (events, status = 200, extra = {}) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => ({ events, ...extra }),
});
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

test("Home/Live identity comes only from each match scope", () => {
  assert.deepEqual(matchEventIdentity(match()), {
    competition_key: "la_liga",
    season_key: "2026-2027",
    match_id: "mp_match_331c27325ef7c347a72beb3d",
  });
  assert.equal(matchEventIdentity(match({ id: "486074" })), null);
  assert.equal(matchEventIdentity(match({ season_key: "" })), null);
});

test("first open calls the scoped API and stores a 14-event timeline", async () => {
  const events = Array.from({ length: 14 }, (_, index) => ({ id: `event-${index}` }));
  const calls = [];
  const controller = createScopedMatchEventController((...args) => {
    calls.push(args);
    return response(events);
  });
  const selected = match();

  const request = controller.toggle(selected);
  assert.equal(controller.eventProps(selected).isExpanded, true);
  assert.equal(controller.eventProps(selected).isLoadingEvents, true);
  await request;

  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].slice(0, 3), [
    "la_liga",
    "2026-2027",
    "mp_match_331c27325ef7c347a72beb3d",
  ]);
  assert.ok(calls[0][3].signal instanceof AbortSignal);
  assert.equal(controller.eventProps(selected).events.length, 14);
  assert.equal(controller.eventProps(selected).isLoadingEvents, false);
});

test("collapse and cached reopen do not refetch", async () => {
  let calls = 0;
  const controller = createScopedMatchEventController(() => {
    calls += 1;
    return response([{ id: "cached-event" }]);
  });
  const selected = match();

  await controller.toggle(selected);
  await controller.toggle(selected);
  assert.equal(controller.eventProps(selected).isExpanded, false);
  await controller.toggle(selected);
  assert.equal(controller.eventProps(selected).isExpanded, true);
  assert.deepEqual(controller.eventProps(selected).events, [{ id: "cached-event" }]);
  assert.equal(calls, 1);
});

test("opening another competition aborts and ignores the old response", async () => {
  const oldRequest = deferred();
  const newRequest = deferred();
  const signals = [];
  const controller = createScopedMatchEventController((competitionKey, seasonKey, matchId, options) => {
    signals.push(options.signal);
    return competitionKey === "la_liga" ? oldRequest.promise : newRequest.promise;
  });
  const oldMatch = match();
  const newMatch = match({
    id: "mp_match_premier",
    competition_key: "premier_league",
  });

  const oldPromise = controller.toggle(oldMatch);
  await Promise.resolve();
  const newPromise = controller.toggle(newMatch);
  await Promise.resolve();
  assert.equal(signals[0].aborted, true);
  assert.equal(controller.eventProps(oldMatch).isExpanded, false);
  assert.equal(controller.eventProps(newMatch).isExpanded, true);
  oldRequest.resolve(response([{ id: "must-not-leak" }]));
  newRequest.resolve(response([{ id: "premier-event" }]));
  await Promise.all([oldPromise, newPromise]);

  assert.deepEqual(controller.eventProps(oldMatch).events, []);
  assert.deepEqual(controller.eventProps(newMatch).events, [{ id: "premier-event" }]);
});

test("day switch reset aborts selection while preserving completed caches", async () => {
  const controller = createScopedMatchEventController(() => response([{ id: "cached" }]));
  const selected = match();
  await controller.toggle(selected);
  controller.resetSelection();
  assert.equal(controller.eventProps(selected).isExpanded, false);
  assert.deepEqual(controller.eventProps(selected).events, [{ id: "cached" }]);
});

test("failure kinds use existing unavailable and failed MatchCard states", async () => {
  for (const [status, expected] of [[404, "eventsUnavailable"], [501, "eventsUnavailable"], [502, "eventsFailed"]]) {
    const controller = createScopedMatchEventController(() => response([], status));
    const selected = match({ id: `mp_match_${status}` });
    await controller.toggle(selected);
    assert.equal(controller.eventProps(selected)[expected], true);
    assert.equal(controller.eventProps(selected).isLoadingEvents, false);
  }
});

test("HTTP 200 empty events with source warnings are unavailable and not cached as loaded", async () => {
  const controller = createScopedMatchEventController(() => (
    response([], 200, { warnings: ["provider unavailable"] })
  ));
  const selected = match({ id: "mp_match_warned_empty" });
  await controller.toggle(selected);

  const state = Object.values(controller.getSnapshot().statesByIdentity)[0];
  assert.deepEqual(state.events, []);
  assert.equal(state.failed, false);
  assert.equal(state.loaded, false);
  assert.equal(state.loading, false);
  assert.equal(state.unavailable, true);
  assert.equal(controller.eventProps(selected).eventsUnavailable, true);
});

test("HTTP 200 genuine empty events are a normal loaded empty timeline", async () => {
  const controller = createScopedMatchEventController(() => (
    response([], 200, { warnings: [] })
  ));
  const selected = match({ id: "mp_match_genuine_empty" });
  await controller.toggle(selected);

  const state = Object.values(controller.getSnapshot().statesByIdentity)[0];
  assert.deepEqual(state.events, []);
  assert.equal(state.failed, false);
  assert.equal(state.loaded, true);
  assert.equal(state.loading, false);
  assert.equal(state.unavailable, false);
});

test("HTTP 200 non-empty events remain normally loaded despite warning metadata", async () => {
  const events = [{ id: "event-1" }];
  const controller = createScopedMatchEventController(() => (
    response(events, 200, { warning: "partial provider metadata" })
  ));
  const selected = match({ id: "mp_match_non_empty" });
  await controller.toggle(selected);

  const state = Object.values(controller.getSnapshot().statesByIdentity)[0];
  assert.deepEqual(state.events, events);
  assert.equal(state.loaded, true);
  assert.equal(state.unavailable, false);
});

test("eligibility shows live/finished/override and excludes upcoming/postponed", () => {
  const controller = createScopedMatchEventController(() => response([]));
  assert.equal(controller.eventProps(match({ status: "live" })).showEvents, true);
  assert.equal(controller.eventProps(match()).showEvents, true);
  assert.equal(controller.eventProps(match({ status: "pending_result", kickoff_utc: "2000-01-01T00:00:00Z" })).showEvents, true);
  assert.equal(controller.eventProps(match({ status: "upcoming" })).showEvents, false);
  assert.equal(controller.eventProps(match({ status: "postponed" })).showEvents, false);
  assert.equal(controller.eventProps(match({ status: "postponed", can_show_event_button: true })).showEvents, true);
});

test("Home and Live use one scoped controller without selectedCompetition or season fetching", () => {
  const home = source("../src/pages/HomePage.jsx");
  const live = source("../src/pages/LivePage.jsx");
  const hook = source("../src/hooks/useScopedMatchEvents.js");
  const api = source("../src/api/football.js");

  for (const page of [home, live]) {
    assert.match(page, /useScopedMatchEvents\(\)/);
    assert.match(page, /\.\.\.matchEvents\.eventProps\(match\)/);
    assert.doesNotMatch(page, /showEvents=\{false\}|selectedCompetition|fetchMatchEvents|fetchCompetitionSeason/);
  }
  assert.match(live, /matchEvents\.resetSelection\(\)/);
  assert.match(hook, /createScopedMatchEventController\(fetchCompetitionMatchEvents\)/);
  assert.match(
    api,
    /competitions\/\$\{competition\}\/seasons\/\$\{season\}\/matches\/\$\{match\}\/events/,
  );
});

test("CompetitionPage retains its existing scoped event implementation", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  assert.match(page, /fetchCompetitionMatchEvents\(/);
  assert.match(page, /competitionEventIdentity\(competition, match\)/);
  assert.match(page, /canShowCompetitionEvents\(competition, match\)/);
  assert.doesNotMatch(page, /useScopedMatchEvents/);
});
