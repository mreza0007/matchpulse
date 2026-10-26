export const NEWS_PAGE_SIZE = 20;

export function safeArticleUrl(value) {
  if (typeof value !== "string" || [...value].some((char) => char.charCodeAt(0) <= 32
    || char.charCodeAt(0) === 127 || char === "\\")) return "";
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")
      || !host.includes(".") || host.endsWith(".") || host.endsWith(".localhost")
      || host.endsWith(".local") || host.endsWith(".internal") || host.includes(":")
      || /^[\d.]+$/.test(host)) return "";
    return url.href;
  } catch {
    return "";
  }
}

export function openArticle(event, url, telegram = globalThis.window?.Telegram?.WebApp) {
  const safe = safeArticleUrl(url);
  if (!safe || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  if (typeof telegram?.openLink === "function") {
    try {
      telegram.openLink(safe);
      event.preventDefault();
    } catch { /* The safe native anchor remains the fallback. */ }
  }
}

export function articleHeadline(item, lang) {
  return (lang === "fa" ? item.title_fa || item.title_en : item.title_en || item.title_fa)
    || item.original_headline || item.headline || "";
}

export function articleDate(value, lang, now = Date.now()) {
  // Do not interpret timezone-naive provider values in the device's timezone.
  if (typeof value !== "string" || !/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) return null;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  return {
    iso: date.toISOString(),
    label: new Intl.DateTimeFormat(lang === "fa" ? "fa-IR" : "en-GB", {
      dateStyle: "medium", timeStyle: "short",
    }).format(date),
    stale: now - date.getTime() > 7 * 86400000,
  };
}

export function favoriteNewsRevision(favorites = []) {
  return JSON.stringify([...new Set(favorites.filter((item) => item?.competition_key && item?.team_id != null)
    .map((item) => JSON.stringify([item.competition_key, String(item.team_id)])))].sort());
}

// One feed lifecycle; never caches a favorite feed independently of its scope.
export function createNewsFeed(load, onChange) {
  let state = { items: [], loading: false, error: false, hasMore: false };
  let controller, disposed = false, version = 0, offset = 0, retryAppend = false;
  const publish = (patch) => {
    state = { ...state, ...patch };
    if (!disposed) onChange(state);
  };
  async function request(append = false) {
    if (disposed || (append && state.loading)) return;
    controller?.abort();
    controller = new AbortController();
    const signal = controller.signal;
    const current = ++version;
    retryAppend = append;
    publish({ loading: true, error: false });
    try {
      const response = await load({ limit: NEWS_PAGE_SIZE, offset: append ? offset : 0, signal });
      if (!response.ok) throw new Error("News unavailable");
      const payload = await response.json();
      if (!Array.isArray(payload?.news)) throw new Error("Invalid news response");
      if (disposed || signal.aborted || current !== version) return;
      const page = payload.news;
      const items = [...new Map([...(append ? state.items : []), ...page].map((item) => [item.id, item])).values()];
      offset = (append ? offset : 0) + page.length;
      publish({ items, loading: false, error: false, hasMore: page.length === NEWS_PAGE_SIZE && offset <= 10000 });
    } catch {
      if (!disposed && !signal.aborted && current === version) publish({ loading: false, error: true });
    }
  }
  return {
    refresh: () => request(false),
    loadMore: () => state.hasMore ? request(true) : Promise.resolve(),
    retry: () => request(retryAppend),
    dispose() { disposed = true; ++version; controller?.abort(); },
  };
}
