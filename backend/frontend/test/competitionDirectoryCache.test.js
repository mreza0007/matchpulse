import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  COMPETITION_DIRECTORY_TTL_MS,
  createCompetitionDirectoryCache,
} from "../src/utils/competitionDirectoryCache.js";

const payload = {
  competitions: [{ competition_key: "premier_league", season_key: "2026-2027" }],
};

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("first load fetches once and later consumers and remounts reuse the payload", async () => {
  let calls = 0;
  const cache = createCompetitionDirectoryCache({
    fetchPayload: async () => {
      calls += 1;
      return payload;
    },
  });

  const firstConsumer = await cache.load();
  const secondConsumer = await cache.load();
  const remountedConsumer = await cache.load();

  assert.equal(calls, 1);
  assert.equal(firstConsumer, payload);
  assert.equal(secondConsumer, payload);
  assert.equal(remountedConsumer, payload);
});

test("concurrent normal and forced callers share one in-flight request", async () => {
  const gate = deferred();
  let calls = 0;
  const cache = createCompetitionDirectoryCache({
    fetchPayload: () => {
      calls += 1;
      return gate.promise;
    },
  });

  const forced = cache.load({ force: true });
  const normal = cache.load();
  await Promise.resolve();

  assert.equal(calls, 1);
  gate.resolve(payload);
  assert.equal(await forced, payload);
  assert.equal(await normal, payload);
});

test("cache expires at the five-minute boundary", async () => {
  let clock = 0;
  let calls = 0;
  const cache = createCompetitionDirectoryCache({
    now: () => clock,
    fetchPayload: async () => ({
      competitions: [{ competition_key: `scope_${++calls}` }],
    }),
  });

  const first = await cache.load();
  clock = COMPETITION_DIRECTORY_TTL_MS - 1;
  assert.equal(await cache.load(), first);
  assert.equal(calls, 1);

  clock = COMPETITION_DIRECTORY_TTL_MS;
  const refreshed = await cache.load();
  assert.equal(calls, 2);
  assert.notEqual(refreshed, first);
  assert.equal(refreshed.competitions[0].competition_key, "scope_2");
});

test("force refresh bypasses fresh TTL", async () => {
  let calls = 0;
  const cache = createCompetitionDirectoryCache({
    fetchPayload: async () => ({
      competitions: [{ competition_key: `scope_${++calls}` }],
    }),
  });

  const first = await cache.load();
  const refreshed = await cache.load({ force: true });

  assert.equal(calls, 2);
  assert.notEqual(refreshed, first);
  assert.equal(refreshed.competitions[0].competition_key, "scope_2");
});

test("failed refresh rejects and preserves the prior successful payload", async () => {
  let calls = 0;
  const cache = createCompetitionDirectoryCache({
    fetchPayload: async () => {
      calls += 1;
      if (calls === 2) throw new Error("directory unavailable");
      return payload;
    },
  });

  assert.equal(await cache.load(), payload);
  await assert.rejects(cache.load({ force: true }), /directory unavailable/);
  assert.equal(await cache.load(), payload);
  assert.equal(calls, 2);
});

test("first-load failure is visible and a later request can retry", async () => {
  let calls = 0;
  const cache = createCompetitionDirectoryCache({
    fetchPayload: async () => {
      calls += 1;
      if (calls === 1) throw new Error("directory unavailable");
      return payload;
    },
  });

  await assert.rejects(cache.load(), /directory unavailable/);
  assert.equal(await cache.load(), payload);
  assert.equal(calls, 2);
});

test("CompetitionsPage and PredictionsPage use the shared cached loader", () => {
  const api = source("../src/api/competitionDirectory.js");
  const competitionsPage = source("../src/pages/CompetitionsPage.jsx");
  const predictionsPage = source("../src/pages/PredictionsPage.jsx");

  assert.match(api, /createCompetitionDirectoryCache/);
  for (const page of [competitionsPage, predictionsPage]) {
    assert.match(page, /api\/competitionDirectory\.js/);
    assert.match(page, /loadCompetitionDirectory\(/);
    assert.doesNotMatch(page, /fetchCompetitions\(/);
  }
  assert.match(competitionsPage, /force: retryVersion > 0/);
  assert.match(predictionsPage, /force: directoryRetry > 0/);
});
