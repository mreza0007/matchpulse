import { useEffect, useState, useSyncExternalStore } from "react";
import { fetchCompetitionMatchEvents } from "../api/football.js";
import { createScopedMatchEventController } from "../utils/scopedMatchEvents.js";

export function useScopedMatchEvents() {
  const [controller] = useState(() => (
    createScopedMatchEventController(fetchCompetitionMatchEvents)
  ));
  useEffect(() => () => controller.dispose(), [controller]);
  useSyncExternalStore(controller.subscribe, controller.getSnapshot);
  return controller;
}
