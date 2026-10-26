import { useEffect, useRef, useState } from "react";
import { fetchFavoriteNews, fetchNews } from "../api/news.js";
import NewsCard from "../components/news/NewsCard.jsx";
import { COMPETITIONS } from "../config/competitions.js";
import { favoriteDisplayName, favoriteCompetitionName } from "../utils/favorites.js";
import { createNewsFeed, favoriteNewsRevision } from "../utils/news.js";
import "./NewsPage.css";

const CATEGORIES = ["all", "iran", "world", "transfers", "favorites", "national"];
const labelKey = (key) => `newsCategory${key.charAt(0).toUpperCase()}${key.slice(1)}`;

function NewsFeed({ category, competitionKey, teamId, telegramId, lang, t }) {
  const [result, setResult] = useState({ items: [], loading: true, error: false, hasMore: false });
  const feed = useRef(null);
  useEffect(() => {
    const common = { category: ["all", "favorites"].includes(category) ? undefined : category };
    const instance = createNewsFeed((pagination) => category === "favorites" && !teamId
      ? fetchFavoriteNews(telegramId, { ...common, ...pagination })
      : fetchNews({ ...common, competitionKey, teamId, ...pagination }), setResult);
    feed.current = instance;
    instance.refresh();
    return () => instance.dispose();
  }, [category, competitionKey, teamId, telegramId]);

  return <div className="news-feed" aria-busy={result.loading}>
    <div className="news-feed-toolbar">
      <button type="button" disabled={result.loading} onClick={() => feed.current?.refresh()}>{t.newsRefresh}</button>
    </div>
    {result.error && <div className="home-empty-state structured-news-error" role="status">
      <p>{result.items.length ? t.newsRefreshError : category === "favorites" ? t.favoriteNewsLoadError : t.newsLoadError}</p>
      <button type="button" disabled={result.loading} onClick={() => feed.current?.retry()}>{t.retry}</button>
    </div>}
    {result.loading && !result.items.length && <div className="structured-news-list" aria-label={t.loading}>
      {[0, 1, 2].map((index) => <div className="structured-news-skeleton" key={index} aria-hidden="true"><span /><span /></div>)}
    </div>}
    {!result.loading && !result.error && !result.items.length && <div className="home-empty-state">
      {category === "favorites" ? t.favoriteNewsEmpty : t.newsCategoryEmpty}
    </div>}
    <div className="structured-news-list">
      {result.items.map((item) => <NewsCard key={item.id} item={item} lang={lang} t={t}
        categoryLabel={t[labelKey(item.category || "")] || ""}
        competitionLabels={(item.related_competition_keys || []).flatMap((key) => {
          const labels = COMPETITIONS[key]?.labels;
          return labels ? [labels[lang] || labels.en] : [];
        })} />)}
    </div>
    {result.hasMore && <button className="news-load-more" type="button" disabled={result.loading}
      onClick={() => feed.current?.loadMore()}>{result.loading ? t.loading : t.newsLoadMore}</button>}
  </div>;
}

export default function NewsPage({ lang, t, telegramId, favoriteTeams = [] }) {
  const [category, setCategory] = useState("all");
  const [selectedTeam, setSelectedTeam] = useState("");
  const favoritesRevision = favoriteNewsRevision(favoriteTeams);
  const options = [...new Map(favoriteTeams.filter((team) => team.competition_key && team.team_id != null)
    .map((team) => [JSON.stringify([team.competition_key, String(team.team_id)]), team])).entries()]
    .filter(([, team]) => favoriteDisplayName(team, lang));
  const activeTeam = options.some(([key]) => key === selectedTeam) ? selectedTeam : "";
  const [competitionKey, teamId] = activeTeam ? JSON.parse(activeTeam) : [];
  const identityRequired = category === "favorites" && !/^[1-9]\d*$/.test(String(telegramId || ""));
  // Favorite identity changes invalidate personal feeds, including same-ID teams in other competitions.
  const scope = JSON.stringify([category, competitionKey, teamId, telegramId,
    category === "favorites" || activeTeam ? favoritesRevision : ""]);
  return <section className="structured-news-page" dir={lang === "fa" ? "rtl" : "ltr"}>
    <h1>{t.newsPage}</h1>
    <div className="structured-news-categories" aria-label={t.newsCategories}>
      {CATEGORIES.map((key) => <button key={key} type="button" aria-pressed={category === key}
        className={category === key ? "active" : ""} onClick={() => setCategory(key)}>{t[labelKey(key)]}</button>)}
    </div>
    {options.length > 0 && <label className="news-team-filter">{t.newsTeamFilter}
      <select value={activeTeam} onChange={(event) => setSelectedTeam(event.target.value)}>
        <option value="">{t.newsAllTeams}</option>
        {options.map(([key, team]) => <option value={key} key={key}>
          {favoriteDisplayName(team, lang)}{favoriteCompetitionName(team, lang) ? ` — ${favoriteCompetitionName(team, lang)}` : ""}
        </option>)}
      </select>
    </label>}
    {identityRequired ? <div className="home-empty-state">{t.favoriteNewsIdentityRequired}</div>
      : <NewsFeed key={scope} category={category} competitionKey={competitionKey} teamId={teamId}
        telegramId={telegramId} lang={lang} t={t} />}
  </section>;
}
