import { useEffect, useState } from "react";
import { loadCompetitionDirectory } from "../api/competitionDirectory.js";

export function useCompetitionMetadata() {
  const [competitions, setCompetitions] = useState({});
  useEffect(() => {
    const controller = new AbortController();
    loadCompetitionDirectory({ signal: controller.signal }).then((payload) => {
      if (!controller.signal.aborted) setCompetitions(Object.fromEntries(
        (payload.competitions || []).map((competition) => [competition.competition_key, competition]),
      ));
    }).catch(() => {}); // Fail closed: no speculative add controls.
    return () => controller.abort();
  }, []);
  return competitions;
}
