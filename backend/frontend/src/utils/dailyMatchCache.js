const emptyState = (date) => ({
  date, groups: [], errors: [], failed: false, loading: true, hasPayload: false,
});

// Only the cache owns network work. Consumer cancellation never aborts that work.
function forConsumer(promise, signal) {
  if (!signal) return promise;
  if (signal.aborted) return Promise.reject(new DOMException("Aborted", "AbortError"));
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException("Aborted", "AbortError"));
    signal.addEventListener("abort", abort, { once: true });
    promise.then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}

export function createDailyMatchCache({ fetchPayload, now = Date.now, ttlMs = 10_000, maxEntries = 7 }) {
  const entries = new Map();
  const entryFor = (date) => {
    if (!entries.has(date)) {
      entries.set(date, { state: emptyState(date), timestamp: null, pending: null, listeners: new Set() });
    }
    return entries.get(date);
  };
  const publish = (entry, state) => {
    entry.state = state;
    entry.listeners.forEach((listener) => listener());
  };
  const prune = () => {
    for (const [date, entry] of entries) {
      if (entries.size <= maxEntries) break;
      if (!entry.pending && entry.listeners.size === 0) entries.delete(date);
    }
  };
  const cache = {
    getSnapshot(date) {
      return entryFor(date).state;
    },
    subscribe(date, listener) {
      const entry = entryFor(date);
      entry.listeners.add(listener);
      return () => { entry.listeners.delete(listener); prune(); };
    },
    load(date, { force = false, signal } = {}) {
      if (signal?.aborted) return forConsumer(Promise.resolve(), signal);
      const entry = entryFor(date);
      if (entry.pending) return forConsumer(entry.pending, signal);
      if (!force && entry.timestamp !== null && now() - entry.timestamp < ttlMs) {
        return forConsumer(Promise.resolve(entry.state), signal);
      }
      publish(entry, { ...entry.state, failed: false, loading: true });
      entry.pending = Promise.resolve().then(() => fetchPayload(date)).then((payload) => {
        if (payload?.date !== date || !Array.isArray(payload.groups) || !Array.isArray(payload.errors)) {
          throw new Error("Invalid daily response");
        }
        if (payload.errors.length) {
          // A degraded response must never overwrite the last successful snapshot.
          publish(entry, {
            ...(entry.timestamp === null ? { ...emptyState(date), groups: payload.groups, hasPayload: true } : entry.state),
            errors: payload.errors, failed: true, loading: false,
          });
          return entry.state;
        }
        entry.timestamp = now();
        publish(entry, { date, groups: payload.groups, errors: [], failed: false, loading: false, hasPayload: true });
        return entry.state;
      }).catch(() => {
        publish(entry, { ...entry.state, failed: true, loading: false });
        return entry.state;
      }).finally(() => {
        entry.pending = null;
        prune();
      });
      return forConsumer(entry.pending, signal);
    },
  };
  return cache;
}
