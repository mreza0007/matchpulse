// Development-only UI harness; never imported into the production entrypoint.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import NewsPage from "../../src/pages/NewsPage.jsx";
import { translations } from "../../src/config/translations.js";
import { fixtureArticles, fixtureFavorites } from "./newsArticles.js";
import { runNewsBrowserChecks } from "./newsBrowserChecks.js";
import "../../src/App.css";

let currentFavorites = fixtureFavorites, fail = false;
window.fetch = async (input, { signal } = {}) => {
  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
  const url = new URL(String(input), window.location.origin);
  if (!/\/news(?:\/favorites\/10)?$/.test(url.pathname)) throw Error("Only fixture news requests allowed");
  if (fail) return { ok: false, status: 502, json: async () => ({ detail: "fixture failure" }) };
  let items = fixtureArticles;
  const params = url.searchParams;
  if (url.pathname.includes("/favorites/")) items = items.filter((item) => item.related_teams.some((team) =>
    currentFavorites.some((favorite) => favorite.competition_key === team.competition_key && favorite.team_id === team.team_id)));
  if (params.has("category")) items = items.filter((item) => item.category === params.get("category"));
  if (params.has("team_id")) items = items.filter((item) => item.related_teams.some((team) =>
    team.competition_key === params.get("competition_key") && team.team_id === params.get("team_id")));
  const offset = Number(params.get("offset") || 0), limit = Number(params.get("limit") || 20);
  items = items.slice(offset, offset + limit);
  return { ok: true, json: async () => ({ count: items.length, news: items }) };
};

export default function Preview() {
  const [lang, setLang] = useState(new URLSearchParams(window.location.search).get("lang") === "fa" ? "fa" : "en");
  const [favorites, setFavorites] = useState(fixtureFavorites);
  return <main style={{ maxWidth: 640, margin: "0 auto", padding: 12, boxSizing: "border-box" }}>
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
      <button onClick={() => setLang(lang === "fa" ? "en" : "fa")}>Switch language</button>
      <button onClick={() => { fail = !fail; }}>Toggle API failure</button>
      <button onClick={() => { currentFavorites = favorites.length === 2 ? [fixtureFavorites[0]] : fixtureFavorites;
        setFavorites(currentFavorites); }}>Toggle favorite membership</button>
    </div>
    <NewsPage lang={lang} t={translations[lang]} telegramId={10} favoriteTeams={favorites} />
  </main>;
}

createRoot(document.getElementById("root")).render(<Preview />);
if (new URLSearchParams(window.location.search).get("verify") === "1") {
  const lang = new URLSearchParams(window.location.search).get("lang") === "fa" ? "fa" : "en";
  runNewsBrowserChecks(translations[lang]);
}
