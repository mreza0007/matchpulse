import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { articleDate, articleHeadline, createNewsFeed, favoriteNewsRevision, NEWS_PAGE_SIZE, openArticle, safeArticleUrl } from "../src/utils/news.js";
import { fixtureArticle, fixtureArticles, fixtureFavorites } from "./fixtures/newsArticles.js";

const response = (news) => ({ ok: true, json: async () => ({ count: news.length, news }) });
const source = (path) => readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8");

test("headlines localize only existing fields without translation", () => {
  assert.equal(articleHeadline(fixtureArticle, "fa"), fixtureArticle.title_fa);
  assert.equal(articleHeadline(fixtureArticle, "en"), fixtureArticle.title_en);
  assert.equal(articleHeadline({ title_fa: "خبر فارسی" }, "en"), "خبر فارسی");
  assert.equal(articleHeadline({ original_headline: "Original" }, "fa"), "Original");
});

test("safe links require public-shaped credential-free HTTPS URLs", () => {
  assert.equal(safeArticleUrl(fixtureArticle.original_url), fixtureArticle.original_url);
  for (const value of ["javascript:alert(1)", "data:text/html,bad", "//news.test/a", "http://news.test/a",
    "https://user:password@news.test/a", "https://127.0.0.1/a", "https://[::1]/", "https://localhost/a",
    "https://a.local/a", "https://news.test:8443/a", "https://news.test/\npath"]) assert.equal(safeArticleUrl(value), "");
});

test("Telegram opening preserves safe native anchor fallback and modifier behavior", () => {
  let opened = "", prevented = false;
  const event = { button: 0, preventDefault() { prevented = true; } };
  openArticle(event, fixtureArticle.original_url, { openLink(url) { opened = url; } });
  assert.equal(opened, fixtureArticle.original_url);
  assert.equal(prevented, true);
  prevented = false;
  openArticle(event, fixtureArticle.original_url, { openLink() { throw Error("unsupported"); } });
  assert.equal(prevented, false);
  openArticle({ ...event, ctrlKey: true }, fixtureArticle.original_url, { openLink() { assert.fail(); } });
  openArticle(event, "javascript:bad", { openLink() { assert.fail(); } });
});

test("publication dates are localized, stale-marked and never fabricated", () => {
  const now = Date.parse("2026-10-26T00:00:00Z");
  assert.equal(articleDate("2026-10-01T12:00:00Z", "fa", now).stale, true);
  assert.equal(articleDate(fixtureArticle.published_at, "en", now).stale, false);
  for (const value of [null, "bad", "2026-10-25T12:00:00"]) assert.equal(articleDate(value, "fa", now), null);
});

test("favorite invalidation is order-independent but exact competition/team scoped", () => {
  assert.equal(favoriteNewsRevision(fixtureFavorites), favoriteNewsRevision([...fixtureFavorites].reverse()));
  assert.notEqual(favoriteNewsRevision(fixtureFavorites), favoriteNewsRevision([fixtureFavorites[0]]));
  assert.notEqual(favoriteNewsRevision([fixtureFavorites[0]]), favoriteNewsRevision([fixtureFavorites[1]]));
});

test("load more uses bounded offsets and terminates on short page", async () => {
  const calls = [], states = [];
  const feed = createNewsFeed(async (args) => {
    calls.push(args);
    return response(fixtureArticles.slice(args.offset, args.offset + args.limit));
  }, (state) => states.push(state));
  await feed.refresh();
  assert.equal(states.at(-1).items.length, NEWS_PAGE_SIZE);
  assert.equal(states.at(-1).hasMore, true);
  await feed.loadMore();
  assert.equal(states.at(-1).items.length, 24);
  assert.equal(states.at(-1).hasMore, false);
  assert.deepEqual(calls.map(({ limit, offset }) => [limit, offset]), [[20, 0], [20, 20]]);
  feed.dispose();
});

test("refresh failure preserves articles, retry resets offset and never exposes raw errors", async () => {
  const states = [], calls = [];
  let fail = false;
  const feed = createNewsFeed(async (args) => {
    calls.push(args.offset);
    if (fail) return { ok: false, json: () => { throw Error("PRIVATE"); } };
    return response([fixtureArticle]);
  }, (state) => states.push(state));
  await feed.refresh();
  fail = true;
  await feed.refresh();
  assert.equal(states.at(-1).items[0].id, fixtureArticle.id);
  assert.equal(states.at(-1).error, true);
  assert.doesNotMatch(JSON.stringify(states), /PRIVATE/);
  fail = false;
  await feed.retry();
  assert.equal(states.at(-1).error, false);
  assert.deepEqual(calls, [0, 0, 0]);
  feed.dispose();
});

test("pagination retry repeats failed offset and deduplicates overlapping article IDs", async () => {
  const states = [], calls = [];
  let fail = false;
  const feed = createNewsFeed(async ({ offset }) => {
    calls.push(offset);
    if (fail) throw Error("network");
    return response(offset ? [fixtureArticles[19], fixtureArticles[20]] : fixtureArticles.slice(0, 20));
  }, (state) => states.push(state));
  await feed.refresh(); fail = true;
  await feed.loadMore(); fail = false;
  await feed.retry();
  assert.deepEqual(calls, [0, 20, 20]);
  assert.equal(states.at(-1).items.length, 21);
  feed.dispose();
});

test("unmounted and superseded requests cannot update a different feed", async () => {
  const pending = [], states = [];
  const feed = createNewsFeed(() => new Promise((resolve) => pending.push(resolve)), (state) => states.push(state));
  const first = feed.refresh(), second = feed.refresh();
  pending[1](response([fixtureArticles[1]])); await second;
  pending[0](response([fixtureArticles[0]])); await first;
  assert.equal(states.at(-1).items[0].id, fixtureArticles[1].id);
  const third = feed.refresh(), length = states.length;
  feed.dispose(); pending[2](response([])); await third;
  assert.equal(states.length, length);
});

test("empty and malformed feed responses are distinct", async () => {
  const states = [];
  let invalid = false;
  const feed = createNewsFeed(async () => invalid ? { ok: true, json: async () => ({}) } : response([]), (s) => states.push(s));
  await feed.refresh();
  assert.equal(states.at(-1).error, false);
  assert.equal(states.at(-1).hasMore, false);
  invalid = true; await feed.refresh();
  assert.equal(states.at(-1).error, true);
  feed.dispose();
});

test("scoped API and favorites changes are wired to the page", () => {
  const api = source("api/news.js"), page = source("pages/NewsPage.jsx"), app = source("App.jsx");
  for (const field of ["competition_key", "team_id", "limit", "offset"]) assert.ok(api.includes(`params.set("${field}"`));
  assert.match(page, /favoriteNewsRevision\(favoriteTeams\)/);
  assert.match(page, /<NewsFeed key=\{scope\}/);
  assert.match(page, /fetchFavoriteNews\(telegramId/);
  assert.match(page, /fetchNews\(\{ \.\.\.common, competitionKey, teamId/);
  assert.match(app, /<NewsPage[^>]*favoriteTeams=\{favoriteTeams\}/);
});

test("mobile card bounds, logical alignment, touch targets and safe image fallback", () => {
  const css = source("pages/NewsPage.css"), card = source("components/news/NewsCard.jsx");
  assert.match(css, /grid-template-columns: minmax\(0, 1fr\)/);
  assert.match(css, /overflow-wrap: anywhere; text-align: start/);
  assert.match(css, /min-height: 44px/);
  assert.match(card, /item.image_permitted === true/);
  assert.match(card, /onError=\{\(\) => setFailedImage\(image\)\}/);
  assert.match(card, /rel="noopener noreferrer"/);
  assert.doesNotMatch(card, /dangerouslySetInnerHTML/);
});
