import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { fetchMatchesByDate } from "../api/football.js";
import { createDailyMatchCache } from "../utils/dailyMatchCache.js";
import { getTehranCalendarDates } from "../utils/dates.js";

// Shared across Home/Live mounts. No component AbortController owns this fetch.
const dailyMatches = createDailyMatchCache({
  fetchPayload: async (date) => {
    const response = await fetchMatchesByDate(date);
    if (!response.ok) throw new Error("Daily matches unavailable");
    return response.json();
  },
});

export function useDailyMatches(date) {
  const subscribe = useCallback((listener) => dailyMatches.subscribe(date, listener), [date]);
  const getSnapshot = useCallback(() => dailyMatches.getSnapshot(date), [date]);
  const result = useSyncExternalStore(subscribe, getSnapshot);
  useEffect(() => { void dailyMatches.load(date); }, [date]);
  const retry = useCallback(() => { void dailyMatches.load(date, { force: true }); }, [date]);
  return { ...result, retry };
}

export function useTehranCalendarDates() {
  const [dates, setDates] = useState(() => getTehranCalendarDates());
  useEffect(() => {
    let timer;
    const checkDate = () => {
      const next = getTehranCalendarDates();
      setDates((current) => current.today === next.today ? current : next);
      window.clearTimeout(timer);
      timer = window.setTimeout(checkDate, 60_000 - Date.now() % 60_000 + 1);
    };
    // Clock-aligned calendar check includes midnight; never polls match data.
    timer = window.setTimeout(checkDate, 60_000 - Date.now() % 60_000 + 1);
    window.addEventListener("focus", checkDate);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("focus", checkDate);
    };
  }, []);
  return dates;
}
