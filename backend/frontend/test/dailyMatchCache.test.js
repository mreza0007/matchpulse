import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createDailyMatchCache } from "../src/utils/dailyMatchCache.js";
import { getTehranCalendarDates } from "../src/utils/dates.js";

const TODAY = "2026-09-07";
const TOMORROW = "2026-09-08";
const YESTERDAY = "2026-09-06";
const payload = (date, id = date) => ({
  date, groups: [{ competition: { key: "premier_league" }, matches: [{ id }] }], errors: [],
});
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("first Home load starts today and tomorrow concurrently", async () => {
  const calls = [];
  const gates = new Map([[TODAY, deferred()], [TOMORROW, deferred()]]);
  const cache = createDailyMatchCache({ fetchPayload: (date) => {
    calls.push(date);
    return gates.get(date).promise;
  } });
  assert.equal(cache.getSnapshot(TODAY).loading, true);
  assert.equal(cache.getSnapshot(TODAY).hasPayload, false);
  const today = cache.load(TODAY);
  const tomorrow = cache.load(TOMORROW);
  await Promise.resolve();
  assert.deepEqual(calls, [TODAY, TOMORROW]);
  gates.get(TODAY).resolve(payload(TODAY));
  gates.get(TOMORROW).resolve(payload(TOMORROW));
  await Promise.all([today, tomorrow]);
});

test("Home remount and Live reuse fresh today immediately without skeleton or HTTP", async () => {
  let calls = 0;
  const cache = createDailyMatchCache({ fetchPayload: (date) => { calls++; return payload(date); } });
  const unmount = cache.subscribe(TODAY, () => {});
  await cache.load(TODAY);
  const visible = cache.getSnapshot(TODAY);
  unmount();
  assert.equal(cache.getSnapshot(TODAY), visible);
  assert.equal(visible.loading, false);
  assert.equal(visible.hasPayload, true);
  await cache.load(TODAY);
  await cache.load(TODAY);
  assert.equal(calls, 1);
});

test("same-date in-flight work coalesces and subscribers both update", async () => {
  const gate = deferred();
  let calls = 0, homeUpdates = 0, liveUpdates = 0;
  const cache = createDailyMatchCache({ fetchPayload: () => { calls++; return gate.promise; } });
  const stopHome = cache.subscribe(TODAY, () => homeUpdates++);
  const stopLive = cache.subscribe(TODAY, () => liveUpdates++);
  const home = cache.load(TODAY);
  const live = cache.load(TODAY);
  assert.equal(home, live);
  gate.resolve(payload(TODAY));
  await Promise.all([home, live]);
  assert.equal(calls, 1);
  assert.ok(homeUpdates > 0 && liveUpdates > 0);
  stopHome(); stopLive();
});

test("TTL boundary renders stale immediately and refreshes in background", async () => {
  let clock = 0, calls = 0;
  const gate = deferred();
  const cache = createDailyMatchCache({
    now: () => clock, fetchPayload: (date) => ++calls === 1 ? payload(date, "old") : gate.promise,
  });
  await cache.load(TODAY);
  clock = 9999;
  await cache.load(TODAY);
  assert.equal(calls, 1);
  clock = 10_000;
  const refresh = cache.load(TODAY);
  assert.equal(cache.getSnapshot(TODAY).groups[0].matches[0].id, "old");
  assert.equal(cache.getSnapshot(TODAY).hasPayload, true);
  assert.equal(cache.getSnapshot(TODAY).loading, true);
  gate.resolve(payload(TODAY, "new"));
  await refresh;
  assert.equal(cache.getSnapshot(TODAY).groups[0].matches[0].id, "new");
  assert.equal(calls, 2);
});

test("failed stale refresh retains last good payload with warning and retry recovers", async () => {
  let clock = 0, fail = false;
  const cache = createDailyMatchCache({ now: () => clock, fetchPayload: (date) => {
    if (fail) throw new Error("private internal error");
    return payload(date);
  } });
  await cache.load(TODAY);
  const groups = cache.getSnapshot(TODAY).groups;
  clock = 20_000; fail = true;
  await cache.load(TODAY);
  assert.equal(cache.getSnapshot(TODAY).groups, groups);
  assert.equal(cache.getSnapshot(TODAY).failed, true);
  assert.equal(cache.getSnapshot(TODAY).loading, false);
  assert.doesNotMatch(JSON.stringify(cache.getSnapshot(TODAY)), /private/);
  fail = false;
  await cache.load(TODAY, { force: true });
  assert.equal(cache.getSnapshot(TODAY).failed, false);
});

test("HTTP-200 source errors do not erase cached groups or become fresh successes", async () => {
  let clock = 0, calls = 0;
  const cache = createDailyMatchCache({ now: () => clock, fetchPayload: (date) => {
    calls++;
    return calls === 1 ? payload(date) : { date, groups: [], errors: [{ code: "provider_failure" }] };
  } });
  await cache.load(TODAY);
  const groups = cache.getSnapshot(TODAY).groups;
  clock = 10_000;
  await cache.load(TODAY);
  assert.equal(cache.getSnapshot(TODAY).groups, groups);
  assert.equal(cache.getSnapshot(TODAY).failed, true);
  await cache.load(TODAY);
  assert.equal(calls, 3);
});

test("first partial response remains visible and retryable", async () => {
  const cache = createDailyMatchCache({ fetchPayload: (date) => ({
    ...payload(date), errors: [{ code: "provider_failure" }],
  }) });
  await cache.load(TODAY);
  assert.equal(cache.getSnapshot(TODAY).groups.length, 1);
  assert.equal(cache.getSnapshot(TODAY).failed, true);
  assert.equal(cache.getSnapshot(TODAY).hasPayload, true);
});

test("Live switches among cached date tabs with isolated results and no extra requests", async () => {
  const calls = [];
  const cache = createDailyMatchCache({ fetchPayload: (date) => { calls.push(date); return payload(date); } });
  await Promise.all([cache.load(TODAY), cache.load(TOMORROW)]);
  await cache.load(YESTERDAY);
  for (const date of [TODAY, TOMORROW, YESTERDAY, TODAY]) {
    assert.equal(cache.getSnapshot(date).date, date);
    assert.equal(cache.getSnapshot(date).groups[0].matches[0].id, date);
    await cache.load(date);
  }
  assert.equal(calls.length, 3);
});

test("late response for another date cannot replace the selected date snapshot", async () => {
  const gate = deferred();
  const cache = createDailyMatchCache({ fetchPayload: (date) => date === TODAY ? gate.promise : payload(date) });
  const old = cache.load(TODAY);
  await cache.load(TOMORROW);
  const selected = cache.getSnapshot(TOMORROW);
  gate.resolve(payload(TODAY));
  await old;
  assert.equal(cache.getSnapshot(TOMORROW), selected);
});

test("one aborted consumer and unmount cannot cancel another consumer or its network", async () => {
  const gate = deferred(), controller = new AbortController();
  let calls = 0;
  const cache = createDailyMatchCache({ fetchPayload: (...args) => {
    calls++;
    assert.deepEqual(args, [TODAY]);
    return gate.promise;
  } });
  const stop = cache.subscribe(TODAY, () => {});
  const first = cache.load(TODAY, { signal: controller.signal });
  const second = cache.load(TODAY);
  controller.abort(); stop();
  await assert.rejects(first, { name: "AbortError" });
  gate.resolve(payload(TODAY));
  assert.equal((await second).failed, false);
  assert.equal(calls, 1);
});

test("already aborted consumers start no network request", async () => {
  const controller = new AbortController();
  controller.abort();
  let calls = 0;
  const cache = createDailyMatchCache({ fetchPayload: () => calls++ });
  await assert.rejects(cache.load(TODAY, { signal: controller.signal }), { name: "AbortError" });
  assert.equal(calls, 0);
});

test("first failure settles loading and force retry bypasses fresh cache", async () => {
  let calls = 0;
  const cache = createDailyMatchCache({ fetchPayload: (date) => {
    if (++calls === 1) return Promise.reject(new Error("unavailable"));
    return payload(date);
  } });
  await cache.load(TODAY);
  assert.equal(cache.getSnapshot(TODAY).failed, true);
  assert.equal(cache.getSnapshot(TODAY).loading, false);
  await cache.load(TODAY, { force: true });
  await cache.load(TODAY, { force: true });
  assert.equal(calls, 3);
  assert.equal(cache.getSnapshot(TODAY).failed, false);
});

test("wrong-date or malformed response never populates another date", async () => {
  for (const response of [payload(TOMORROW), {}, null, { date: TODAY, groups: {}, errors: [] }]) {
    const cache = createDailyMatchCache({ fetchPayload: () => response });
    await cache.load(TODAY);
    assert.equal(cache.getSnapshot(TODAY).failed, true);
    assert.deepEqual(cache.getSnapshot(TODAY).groups, []);
  }
});

test("valid empty payload is cached and not a skeleton on return", async () => {
  const cache = createDailyMatchCache({ fetchPayload: (date) => ({ date, groups: [], errors: [] }) });
  await cache.load(TODAY);
  assert.equal(cache.getSnapshot(TODAY).hasPayload, true);
  assert.equal(cache.getSnapshot(TODAY).loading, false);
  assert.equal(cache.getSnapshot(TODAY).failed, false);
});

test("bounded cache evicts idle dates without evicting subscribed dates", async () => {
  const cache = createDailyMatchCache({ maxEntries: 2, fetchPayload: payload });
  const stop = cache.subscribe(TODAY, () => {});
  await cache.load(TODAY);
  await cache.load(YESTERDAY);
  await cache.load(TOMORROW);
  assert.equal(cache.getSnapshot(TODAY).hasPayload, true);
  assert.equal(cache.getSnapshot(YESTERDAY).hasPayload, false);
  stop();
});

test("Tehran rollover resolves actual dates rather than reusing a today key", () => {
  const before = getTehranCalendarDates(new Date("2026-09-07T20:29:59Z"));
  const after = getTehranCalendarDates(new Date("2026-09-07T20:30:00Z"));
  assert.equal(before.today, TODAY);
  assert.equal(after.today, TOMORROW);
  assert.equal(after.yesterday, TODAY);
});

test("Home and Live use the single shared hook and never request seasons or reset payloads", () => {
  const home = source("../src/pages/HomePage.jsx");
  const live = source("../src/pages/LivePage.jsx");
  const hook = source("../src/hooks/useDailyMatches.js");
  for (const page of [home, live]) {
    assert.match(page, /useTehranCalendarDates\(\)/);
    assert.doesNotMatch(page, /fetchMatchesByDate|fetchCompetition|fetchWorldCup|setResult|setInterval/);
  }
  assert.match(home, /useDailyMatches\(dates.today\)/);
  assert.match(home, /useDailyMatches\(dates.tomorrow\)/);
  assert.match(home, /today.loading && !today.hasPayload/);
  assert.match(home, /tomorrow.loading && !tomorrow.hasPayload/);
  assert.match(live, /useDailyMatches\(dates\[selectedDay\]\)/);
  assert.match(live, /result.loading && !result.hasPayload/);
  assert.match(live, /onClick=\{retry\}/);
  assert.match(hook, /const dailyMatches = createDailyMatchCache/);
  assert.match(hook, /useSyncExternalStore\(subscribe, getSnapshot\)/);
  assert.match(hook, /fetchMatchesByDate\(date\)/);
  assert.match(hook, /force: true/);
  assert.doesNotMatch(hook, /new AbortController|fetchCompetition|fetchWorldCup|30000/);
});
