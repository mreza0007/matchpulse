import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { fixtureArticle, fixtureFavorites } from "./fixtures/newsArticles.js";

test("fixture cards render attribution, links, permissions and both language directions", async (context) => {
  const server = await createServer({ configFile: false, plugins: [react()],
    server: { middlewareMode: true }, appType: "custom", optimizeDeps: { noDiscovery: true } });
  try {
    const { default: Card } = await server.ssrLoadModule("/src/components/news/NewsCard.jsx");
    const { default: Page } = await server.ssrLoadModule("/src/pages/NewsPage.jsx");
    const { translations } = await server.ssrLoadModule("/src/config/translations.js");
    const api = await server.ssrLoadModule("/src/api/news.js");
    const requests = [];
    context.mock.method(globalThis, "fetch", async (url, options) => {
      requests.push({ url: new URL(url, "https://matchpulse.example.invalid"), options });
      return { ok: true, json: async () => ({ count: 1, news: [fixtureArticle] }) };
    });
    const signal = new AbortController().signal;
    await api.fetchNews({ category: "world", competitionKey: "la_liga", teamId: "mp_team_shared", limit: 20, offset: 20, signal });
    assert.deepEqual(Object.fromEntries(requests[0].url.searchParams), {
      category: "world", competition_key: "la_liga", team_id: "mp_team_shared", limit: "20", offset: "20",
    });
    assert.equal(requests[0].options.signal, signal);
    await api.fetchFavoriteNews(10, { limit: 20, offset: 40, signal });
    assert.match(requests[1].url.pathname, /\/news\/favorites\/10$/);
    assert.equal(requests[1].url.searchParams.get("offset"), "40");
    assert.throws(() => api.fetchNews({ teamId: "mp_team_shared" }), /Scoped team required/);
    for (const lang of ["fa", "en"]) {
      const t = translations[lang];
      const render = (item) => renderToStaticMarkup(createElement(Card, { item, lang, t, categoryLabel: "Football" }));
      const html = render(fixtureArticle);
      assert.match(html, new RegExp(`dir="${lang === "fa" ? "rtl" : "ltr"}"`));
      assert.ok(html.includes(fixtureArticle.source));
      assert.ok(html.includes(lang === "fa" ? fixtureArticle.title_fa : fixtureArticle.title_en));
      assert.ok(html.includes(t.newsReadOriginal));
      assert.match(html, /<time dateTime="2026-10-20T09:00:00.000Z"/);
      assert.match(html, /rel="noopener noreferrer"/);
      assert.doesNotMatch(html, /<img/);
      assert.match(render({ ...fixtureArticle, image_permitted: true }), /<img[^>]+loading="lazy"/);
      assert.doesNotMatch(render({ ...fixtureArticle, image_permitted: true, image_url: "javascript:bad" }), /<img/);
      assert.doesNotMatch(render({ ...fixtureArticle, original_url: "http://unsafe.invalid" }), /<a /);
      const notice = render({ id: 1, origin: "static_notice", title_en: "Notice", source: "MatchPulse" });
      assert.ok(notice.includes(t.newsStaticNotice));
      assert.doesNotMatch(notice, /<time|<a /);
      const page = renderToStaticMarkup(createElement(Page, { lang, t, telegramId: 10, favoriteTeams: fixtureFavorites }));
      for (const key of ["newsCategoryAll", "newsCategoryIran", "newsCategoryWorld", "newsCategoryTransfers", "newsCategoryFavorites"])
        assert.ok(page.includes(t[key]));
      assert.ok(page.includes("premier_league"));
      assert.ok(page.includes("la_liga"));
    }
  } finally { await server.close(); }
});
