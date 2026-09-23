export const COMPETITION_DIRECTORY_TTL_MS = 5 * 60 * 1000;

function forConsumer(promise, signal) {
  if (!signal) return promise;
  if (signal.aborted) return Promise.reject(new DOMException("Aborted", "AbortError"));

  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback, value) => {
      if (settled) return;
      settled = true;
      signal.removeEventListener("abort", abort);
      callback(value);
    };
    const abort = () => finish(reject, new DOMException("Aborted", "AbortError"));
    signal.addEventListener("abort", abort, { once: true });
    promise.then(
      (value) => finish(resolve, value),
      (error) => finish(reject, error),
    );
  });
}

export function createCompetitionDirectoryCache({
  fetchPayload,
  now = Date.now,
  ttlMs = COMPETITION_DIRECTORY_TTL_MS,
}) {
  let payload = null;
  let timestamp = null;
  let pending = null;

  return {
    load({ force = false, signal } = {}) {
      if (signal?.aborted) return forConsumer(Promise.resolve(), signal);
      if (pending) return forConsumer(pending, signal);
      if (!force && timestamp !== null && now() - timestamp < ttlMs) {
        return forConsumer(Promise.resolve(payload), signal);
      }

      const request = Promise.resolve()
        .then(fetchPayload)
        .then((nextPayload) => {
          payload = nextPayload;
          timestamp = now();
          return payload;
        });
      pending = request;
      request.then(
        () => {
          if (pending === request) pending = null;
        },
        () => {
          if (pending === request) pending = null;
        },
      );
      return forConsumer(request, signal);
    },
  };
}
