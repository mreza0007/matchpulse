import { fetchCompetitions } from "./football.js";
import { createCompetitionDirectoryCache } from "../utils/competitionDirectoryCache.js";

const competitionDirectory = createCompetitionDirectoryCache({
  fetchPayload: async () => {
    const response = await fetchCompetitions();
    if (!response.ok) {
      const error = new Error("Competitions directory unavailable");
      error.status = response.status;
      throw error;
    }
    return response.json();
  },
});

export function loadCompetitionDirectory(options) {
  return competitionDirectory.load(options);
}
