import { useEffect, useRef, useState } from "react";
import { fetchFavoriteNews, fetchNews } from "../api/news.js";
import NewsCard from "../components/news/NewsCard.jsx";
import { COMPETITIONS } from "../config/competitions.js";

const CATEGORIES = [
  { key: "all", value: null, labelKey: "newsCategoryAll" },
  { key: "favorites", value: null, labelKey: "newsCategoryFavorites" },
  { key: "iran", value: "iran", labelKey: "newsCategoryIran" },
  { key: "world", value: "world", labelKey: "newsCategoryWorld" },
  { key: "national", value: "national", labelKey: "newsCategoryNational" },
  { key: "transfers", value: "transfers", labelKey: "newsCategoryTransfers" },
];

function NewsSkeleton() {
  return (
    <div className="structured-news-list" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <div className="structured-news-skeleton" key={index}>
          <span />
          <span />
        </div>
      ))}
    </div>
  );
}

function trustedCompetitionLabels(item, lang) {
  if (!Array.isArray(item?.related_competition_keys)) return [];

  return item.related_competition_keys.flatMap((key) => {
    const competition = COMPETITIONS[key];
    if (!competition) return [];
    return [competition.labels[lang] || competition.labels.en];
  });
}

export default function NewsPage({ lang, t, telegramId }) {
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [result, setResult] = useState({ items: [], loading: true, error: null });
  const [retryVersion, setRetryVersion] = useState(0);
  const cache = useRef(new Map());
  const requestVersion = useRef(0);
  const selectedOption = CATEGORIES.find((category) => category.key === selectedCategory);
  const isFavoritesFeed = selectedCategory === "favorites";
  const hasUsableTelegramId = (
    (Number.isSafeInteger(telegramId) && telegramId > 0)
    || (typeof telegramId === "string" && /^[1-9]\d*$/.test(telegramId))
  );
  const cacheKey = isFavoritesFeed
    ? `favorites:${String(telegramId)}`
    : `normal:${selectedCategory}`;

  useEffect(() => {
    if (isFavoritesFeed && !hasUsableTelegramId) return undefined;

    if (cache.current.has(cacheKey)) {
      setResult({ items: cache.current.get(cacheKey), loading: false, error: null });
      return undefined;
    }

    const controller = new AbortController();
    const currentRequest = requestVersion.current + 1;
    requestVersion.current = currentRequest;
    setResult({ items: [], loading: true, error: null });

    const request = isFavoritesFeed
      ? fetchFavoriteNews(telegramId, { signal: controller.signal })
      : fetchNews({ category: selectedOption?.value, signal: controller.signal });

    request
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          const error = new Error(`News request failed: ${response.status}`);
          error.status = response.status;
          throw error;
        }
        return payload;
      })
      .then((payload) => {
        if (controller.signal.aborted || requestVersion.current !== currentRequest) return;
        const items = Array.isArray(payload?.news) ? payload.news : [];
        cache.current.set(cacheKey, items);
        setResult({ items, loading: false, error: null });
      })
      .catch((error) => {
        if (error.name === "AbortError" || requestVersion.current !== currentRequest) return;
        console.error("Failed to load News:", error);
        setResult({
          items: [],
          loading: false,
          error: isFavoritesFeed && error.status === 503 ? "favorites-update" : "generic",
        });
      });

    return () => controller.abort();
  }, [
    cacheKey,
    hasUsableTelegramId,
    isFavoritesFeed,
    retryVersion,
    selectedOption?.value,
    telegramId,
  ]);

  const selectCategory = (categoryKey) => {
    if (categoryKey === selectedCategory) return;
    setSelectedCategory(categoryKey);
  };
  const retry = () => {
    cache.current.delete(cacheKey);
    setRetryVersion((version) => version + 1);
  };
  const identityRequired = isFavoritesFeed && !hasUsableTelegramId;

  return (
    <section className="structured-news-page">
      <h1>{t.newsPage}</h1>

      <div className="structured-news-categories" aria-label={t.newsCategories} role="tablist">
        {CATEGORIES.map((category) => (
          <button
            aria-selected={selectedCategory === category.key}
            className={selectedCategory === category.key ? "active" : ""}
            key={category.key}
            onClick={() => selectCategory(category.key)}
            role="tab"
            type="button"
          >
            {t[category.labelKey]}
          </button>
        ))}
      </div>

      {!identityRequired && result.loading && <NewsSkeleton />}

      {identityRequired && (
        <div className="home-empty-state">{t.favoriteNewsIdentityRequired}</div>
      )}

      {!identityRequired && !result.loading && result.error && (
        <div className="home-empty-state structured-news-error">
          <p>
            {result.error === "favorites-update"
              ? t.favoriteNewsUpdateRequired
              : (isFavoritesFeed ? t.favoriteNewsLoadError : t.newsLoadError)}
          </p>
          <button onClick={retry} type="button">{t.retry}</button>
        </div>
      )}

      {!identityRequired && !result.loading && !result.error && result.items.length === 0 && (
        <div className="home-empty-state">
          {isFavoritesFeed ? t.favoriteNewsEmpty : t.newsCategoryEmpty}
        </div>
      )}

      {!identityRequired && !result.loading && !result.error && result.items.length > 0 && (
        <div className="structured-news-list">
          {result.items.map((item) => (
            <NewsCard
              categoryLabel={t[`newsCategory${item.category?.charAt(0).toUpperCase()}${item.category?.slice(1)}`] || ""}
              competitionLabels={trustedCompetitionLabels(item, lang)}
              item={item}
              key={item.id}
              lang={lang}
            />
          ))}
        </div>
      )}
    </section>
  );
}
