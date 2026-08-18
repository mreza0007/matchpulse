import { useEffect, useRef, useState } from "react";
import { fetchNews } from "../api/news.js";
import NewsCard from "../components/news/NewsCard.jsx";
import { COMPETITIONS } from "../config/competitions.js";

const CATEGORIES = [
  { key: "all", value: null, labelKey: "newsCategoryAll" },
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

export default function NewsPage({ lang, t }) {
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [result, setResult] = useState({ items: [], loading: true, failed: false });
  const [retryVersion, setRetryVersion] = useState(0);
  const cache = useRef(new Map());
  const requestVersion = useRef(0);
  const selectedOption = CATEGORIES.find((category) => category.key === selectedCategory);

  useEffect(() => {
    const cachedItems = cache.current.get(selectedCategory);
    if (cachedItems) {
      setResult({ items: cachedItems, loading: false, failed: false });
      return undefined;
    }

    const controller = new AbortController();
    const currentRequest = requestVersion.current + 1;
    requestVersion.current = currentRequest;
    setResult({ items: [], loading: true, failed: false });

    fetchNews({ category: selectedOption?.value, signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`News request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (controller.signal.aborted || requestVersion.current !== currentRequest) return;
        const items = Array.isArray(payload?.news) ? payload.news : [];
        cache.current.set(selectedCategory, items);
        setResult({ items, loading: false, failed: false });
      })
      .catch((error) => {
        if (error.name === "AbortError" || requestVersion.current !== currentRequest) return;
        console.error("Failed to load News:", error);
        setResult({ items: [], loading: false, failed: true });
      });

    return () => controller.abort();
  }, [retryVersion, selectedCategory, selectedOption?.value]);

  const selectCategory = (categoryKey) => {
    if (categoryKey === selectedCategory) return;
    setSelectedCategory(categoryKey);
  };
  const retry = () => {
    cache.current.delete(selectedCategory);
    setRetryVersion((version) => version + 1);
  };

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

      {result.loading && <NewsSkeleton />}

      {!result.loading && result.failed && (
        <div className="home-empty-state structured-news-error">
          <p>{t.newsLoadError}</p>
          <button onClick={retry} type="button">{t.retry}</button>
        </div>
      )}

      {!result.loading && !result.failed && result.items.length === 0 && (
        <div className="home-empty-state">{t.newsCategoryEmpty}</div>
      )}

      {!result.loading && !result.failed && result.items.length > 0 && (
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
