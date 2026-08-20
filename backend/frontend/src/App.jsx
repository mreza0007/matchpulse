import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { COMPETITIONS } from "./config/competitions.js";
import { translations } from "./config/translations.js";
import {
  fetchCompetitionMatches,
  fetchCompetitionTeams,
  fetchMatchEvents,
  fetchWorldCupSummary,
} from "./api/football.js";
import {
  createReminder,
  deleteReminder,
  fetchPredictions,
  fetchPredictionStats,
  fetchReminders,
  savePrediction,
  saveTelegramUser,
} from "./api/user.js";
import {
  addFavoriteTeam,
  deleteFavoriteTeam,
  fetchFavoriteTeams,
} from "./api/favorites.js";
import MatchCard from "./components/matches/MatchCard.jsx";
import AppHeader from "./components/layout/AppHeader.jsx";
import BottomNav from "./components/layout/BottomNav.jsx";
import WorldCupArchive from "./components/worldcup/WorldCupArchive.jsx";
import HomePage from "./pages/HomePage.jsx";
import LivePage from "./pages/LivePage.jsx";
import CompetitionsPage from "./pages/CompetitionsPage.jsx";
import NewsPage from "./pages/NewsPage.jsx";
import PredictionsPage from "./pages/PredictionsPage.jsx";
import ProfilePage from "./pages/ProfilePage.jsx";
import {
  getMatchScoreSignature,
  isFinishedMatch,
  isFutureMatchStatus,
  isLiveMatch,
  isResultTabMatch,
  matchesAreEqual,
  normalizeMatchStatus,
  normalizeMatchPayload,
  toPersianDigits,
} from "./utils/matches.js";
import { getKickoffTime, groupMatchesByDate } from "./utils/dates.js";
import { normalizeTeamKey } from "./utils/teams.js";

const EMPTY_SET = new Set();

function BrandLogo({ competition, lang }) {
  const [hasError, setHasError] = useState(false);
  const label = competition.labels[lang] || competition.labels.en;
  const showImage = Boolean(competition.logoSrc) && !hasError;

  return (
    <div className="brand-logo" aria-label={label}>
      {showImage ? (
        <img
          className="brand-logo-img"
          src={competition.logoSrc}
          alt={label}
          onError={() => setHasError(true)}
        />
      ) : (
        <span className="brand-logo-fallback">{competition.logoFallback}</span>
      )}
    </div>
  );
}

function favoriteIdentityKey(competitionKey, teamId) {
  return `${competitionKey}:${String(teamId)}`;
}

function favoriteFailureStatus(status) {
  if (status === 503) return "migration";
  if (status === 502) return "provider";
  return "error";
}

function App() {
  const initialTelegramUser = window.Telegram?.WebApp?.initDataUnsafe?.user || null;
  const [lang, setLang] = useState("fa");
  const [activeTab, setActiveTab] = useState("home");
  const [selectedCompetitionKey, setSelectedCompetitionKey] = useState("worldcup2026");
  const [telegramUser] = useState(initialTelegramUser);
  const [isUserSaved, setIsUserSaved] = useState(false);

  const [matches, setMatches] = useState([]);
  const [isLoadingMatches, setIsLoadingMatches] = useState(true);
  const [matchesError, setMatchesError] = useState("");
  const [currentTime, setCurrentTime] = useState(0);
  const [worldcupSummary, setWorldcupSummary] = useState(null);
  const [isLoadingWorldcupSummary, setIsLoadingWorldcupSummary] = useState(true);
  const [worldcupSummaryError, setWorldcupSummaryError] = useState("");
  const [teams, setTeams] = useState([]);
  const [favoriteTeams, setFavoriteTeams] = useState([]);
  const [favoriteMessage, setFavoriteMessage] = useState("");
  const [favoriteStatus, setFavoriteStatus] = useState(
    initialTelegramUser?.id ? "loading" : "idle",
  );
  const [favoriteMeta, setFavoriteMeta] = useState({ resolutionErrors: 0, unresolvedCount: 0 });
  const [favoritePendingKeys, setFavoritePendingKeys] = useState(() => new Set());
  const [reminders, setReminders] = useState([]);
  const [reminderMessage, setReminderMessage] = useState("");
  const [predictionsByMatch, setPredictionsByMatch] = useState({});
  const [predictionStats, setPredictionStats] = useState({ points: 0, correct: 0, wrong: 0, pending: 0, total: 0 });
  const [savingPredictionMatchId, setSavingPredictionMatchId] = useState(null);
  const [predictionSavedMatchId, setPredictionSavedMatchId] = useState(null);
  const [predictionLockedMatchIds, setPredictionLockedMatchIds] = useState(() => new Set());
  const [predictionErrorMatchIds, setPredictionErrorMatchIds] = useState(() => new Set());
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [matchEventsById, setMatchEventsById] = useState({});
  const [eventUnavailableMatchIds, setEventUnavailableMatchIds] = useState(() => new Set());
  const [eventFailedMatchIds, setEventFailedMatchIds] = useState(() => new Set());
  const [loadingEventsId, setLoadingEventsId] = useState(null);
  const [scoreChangedMatchIds, setScoreChangedMatchIds] = useState(() => new Set());
  const scoreChangeTimeouts = useRef(new Map());
  const eventRequestController = useRef(null);
  const favoriteMutationVersion = useRef(0);
  const favoriteMutationControllers = useRef(new Set());
  const favoriteRequestController = useRef(null);
  const predictionMutationVersion = useRef(0);
  const predictionSaveRequests = useRef(new Map());

  const t = translations[lang];
  const telegramId = telegramUser?.id;
  const selectedCompetition = COMPETITIONS[selectedCompetitionKey] || COMPETITIONS.worldcup2026;
  const selectedCompetitionLabel = selectedCompetition.labels[lang] || selectedCompetition.labels.en;
  const heroEyebrow = selectedCompetitionKey === "worldcup2026"
    ? t.worldCup
    : selectedCompetitionLabel;
  const heroSubtitle = selectedCompetitionKey === "worldcup2026"
    ? t.subtitle
    : selectedCompetition.subtitles[lang] || selectedCompetition.subtitles.en;

  const favoriteIdentityKeys = useMemo(
    () => new Set(favoriteTeams.map(
      (team) => `${team.competition_key}:${String(team.team_id)}`,
    )),
    [favoriteTeams],
  );

  const reminderIds = useMemo(
    () => new Set(reminders.map((match) => match.id)),
    [reminders],
  );

  const predictionResultsVersion = useMemo(
    () => JSON.stringify(matches.map((match) => [
      match.id,
      match.status,
      match.is_finished,
      match.result,
      match.home_score,
      match.away_score,
      match.penalty_winner_side,
    ])),
    [matches],
  );

  const teamsByName = useMemo(() => {
    const lookup = new Map();
    teams.forEach((team) => {
      if (team.name_en) lookup.set(team.name_en, team);
      if (team.name_fa) lookup.set(team.name_fa, team);
    });
    return lookup;
  }, [teams]);

  const getTeamDisplayName = (team) => (
    lang === "fa"
      ? team.name_fa || team.team_name || team.name_en
      : team.name_en || team.team_name || team.name_fa
  );

  const teamFromMatch = (match, side) => ({
    id: match[`${side}_team_id`] || match[`${side}_en`] || match[`${side}_fa`] || `${match.id}-${side}`,
    team_key: normalizeTeamKey(match[`${side}_en`] || match[`${side}_fa`] || match[`${side}_team`]),
    team_name: match[`${side}_en`] || match[`${side}_fa`] || match[`${side}_team`],
    name_en: match[`${side}_en`] || match[`${side}_team`] || "",
    name_fa: match[`${side}_fa`] || match[`${side}_en`] || "",
    emoji: match[`${side}_flag`] || "\u26bd",
    flag: match[`${side}_flag`] || "\u26bd",
  });

  const futureMatches = useMemo(
    () => matches
      .map((match, originalIndex) => ({ match, originalIndex }))
      .filter(
        ({ match }) =>
          match.is_finished !== true &&
          match.is_live !== true &&
          !isFinishedMatch(match) &&
          !isLiveMatch(match) &&
          isFutureMatchStatus(match),
      )
      .map(({ match, originalIndex }) => ({ match, originalIndex, kickoffTime: getKickoffTime(match) }))
      .filter(({ match, kickoffTime }) => (
        Number.isFinite(kickoffTime)
          ? kickoffTime > currentTime
          : normalizeMatchStatus(match) === "upcoming"
      ))
      .sort((first, second) => {
        const firstHasKickoff = Number.isFinite(first.kickoffTime);
        const secondHasKickoff = Number.isFinite(second.kickoffTime);

        if (firstHasKickoff && secondHasKickoff) return first.kickoffTime - second.kickoffTime;
        if (firstHasKickoff) return -1;
        if (secondHasKickoff) return 1;
        return first.originalIndex - second.originalIndex;
      })
      .map(({ match }) => match),
    [currentTime, matches],
  );

  const upcomingOnlyMatches = futureMatches;

  const pastOnlyMatches = useMemo(
    () => matches
      .filter((match) => isResultTabMatch(match))
      .map((match) => ({ match, kickoffTime: getKickoffTime(match) }))
      .sort((first, second) => second.kickoffTime - first.kickoffTime)
      .map(({ match }) => match),
    [matches],
  );

  const upcomingMatchGroups = useMemo(
    () => groupMatchesByDate(upcomingOnlyMatches, lang),
    [lang, upcomingOnlyMatches],
  );

  const pastMatchGroups = useMemo(
    () => groupMatchesByDate(pastOnlyMatches, lang),
    [lang, pastOnlyMatches],
  );

  useEffect(() => {
    if (!pastOnlyMatches.length) return;

    const firstResult = pastOnlyMatches[0];
    const lastResult = pastOnlyMatches[pastOnlyMatches.length - 1];
    console.debug(
      "[RESULTS_DEBUG]",
      `first_result=${firstResult?.home_en || ""} vs ${firstResult?.away_en || ""}`,
      `last_result=${lastResult?.home_en || ""} vs ${lastResult?.away_en || ""}`,
      `count=${pastOnlyMatches.length}`,
    );
  }, [pastOnlyMatches]);

  useEffect(() => {
    const telegramWebApp = window.Telegram?.WebApp;
    if (!telegramWebApp) return;

    try {
      telegramWebApp.ready?.();
      telegramWebApp.expand?.();
      telegramWebApp.disableVerticalSwipes?.();
    } catch (error) {
      console.warn("Telegram WebApp initialization was not fully available:", error);
    }
  }, []);

  useEffect(() => {
    // Existing behavior intentionally resets the archive request state when this effect starts.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoadingWorldcupSummary(true);
    setWorldcupSummaryError("");

    fetchWorldCupSummary()
      .then((response) => {
        if (!response.ok) throw new Error(`World Cup summary request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setWorldcupSummary(data);
        setWorldcupSummaryError("");
      })
      .catch((error) => {
        console.error("Failed to load World Cup summary:", error);
        setWorldcupSummaryError(t.worldcupArchiveError);
      })
      .finally(() => setIsLoadingWorldcupSummary(false));
  }, [t.worldcupArchiveError]);

  useEffect(() => {
    const scoreTimeouts = scoreChangeTimeouts.current;
    const requestController = new AbortController();

    const markScoreChanged = (matchId) => {
      setScoreChangedMatchIds((currentIds) => new Set(currentIds).add(matchId));

      const existingTimeout = scoreTimeouts.get(matchId);
      if (existingTimeout) window.clearTimeout(existingTimeout);

      const timeout = window.setTimeout(() => {
        setScoreChangedMatchIds((currentIds) => {
          const nextIds = new Set(currentIds);
          nextIds.delete(matchId);
          return nextIds;
        });
        scoreTimeouts.delete(matchId);
      }, 1800);

      scoreTimeouts.set(matchId, timeout);
    };

    const updateMatches = (nextMatches) => {
      setMatches((currentMatches) => {
        const currentById = new Map(currentMatches.map((match) => [match.id, match]));
        let didChange = currentMatches.length !== nextMatches.length;

        const mergedMatches = nextMatches.map((nextMatch) => {
          const currentMatch = currentById.get(nextMatch.id);

          if (!currentMatch) {
            didChange = true;
            return nextMatch;
          }

          if (matchesAreEqual(currentMatch, nextMatch)) {
            return currentMatch;
          }

          didChange = true;

          if (
            currentMatch.status === "live" &&
            nextMatch.status === "live" &&
            getMatchScoreSignature(currentMatch) !== getMatchScoreSignature(nextMatch)
          ) {
            markScoreChanged(nextMatch.id);
          }

          return nextMatch;
        });

        return didChange ? mergedMatches : currentMatches;
      });
    };

    const loadMatches = (isInitialLoad = false) => {
      if (isInitialLoad) {
        setIsLoadingMatches(true);
        setMatchesError("");
      }

      return fetchCompetitionMatches(selectedCompetition, { signal: requestController.signal })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Matches request failed: ${response.status}`);
          }

          return response.json();
        })
        .then((data) => {
          setCurrentTime(Date.now());
          const normalizedMatches = Array.isArray(data.matches)
            ? data.matches.map(normalizeMatchPayload)
            : [];
          updateMatches(normalizedMatches);
          setMatchesError("");
        })
        .catch((error) => {
          if (error.name === "AbortError") return;
          console.error("Failed to load matches:", error);
          setMatchesError(t.matchesError);
        })
        .finally(() => {
          if (isInitialLoad && !requestController.signal.aborted) setIsLoadingMatches(false);
        });
    };

    loadMatches(true);
    const matchRefresh = window.setInterval(loadMatches, 30000);

    return () => {
      requestController.abort();
      window.clearInterval(matchRefresh);
      scoreTimeouts.forEach((timeout) => window.clearTimeout(timeout));
      scoreTimeouts.clear();
    };
  }, [selectedCompetition, t.matchesError]);

  useEffect(() => {
    const requestController = new AbortController();

    fetchCompetitionTeams(selectedCompetition, { signal: requestController.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Teams request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => setTeams(Array.isArray(data.teams) ? data.teams : []))
      .catch((error) => {
        if (error.name !== "AbortError") console.error("Failed to load teams:", error);
      });

    return () => requestController.abort();
  }, [selectedCompetition]);

  useEffect(() => () => {
    eventRequestController.current?.abort();
    favoriteRequestController.current?.abort();
    favoriteMutationControllers.current.forEach((controller) => controller.abort());
    favoriteMutationControllers.current.clear();
  }, []);

  useEffect(() => {
    if (!telegramId) return;

    saveTelegramUser(telegramId, telegramUser)
      .then((response) => {
        if (!response.ok) throw new Error(`User request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => setIsUserSaved(Boolean(data.success)))
      .catch((error) => {
        console.error("Failed to save Telegram user:", error);
        setIsUserSaved(false);
      });

    fetchReminders(telegramId)
      .then((response) => {
        if (!response.ok) throw new Error(`Reminders request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => setReminders(Array.isArray(data.reminders) ? data.reminders : []))
      .catch((error) => console.error("Failed to load reminders:", error));

    const predictionFetchVersion = predictionMutationVersion.current;
    fetchPredictions(telegramId)
      .then((response) => {
        if (!response.ok) throw new Error(`Predictions request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (predictionMutationVersion.current !== predictionFetchVersion) return;
        const predictions = Array.isArray(data.predictions) ? data.predictions : [];
        setPredictionsByMatch(Object.fromEntries(
          predictions.map((prediction) => [String(prediction.match_id), prediction.prediction]),
        ));
      })
      .catch((error) => console.error("Failed to load predictions:", error));

    fetchPredictionStats(telegramId)
      .then((response) => {
        if (!response.ok) throw new Error(`Prediction stats request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => setPredictionStats({
        points: Number(data.points) || 0,
        correct: Number(data.correct) || 0,
        wrong: Number(data.wrong) || 0,
        pending: Number(data.pending) || 0,
        total: Number(data.total) || 0,
      }))
      .catch((error) => console.error("Failed to load prediction stats:", error));
  }, [telegramId, telegramUser]);

  useEffect(() => {
    favoriteRequestController.current?.abort();
    if (!telegramId) {
      return undefined;
    }

    const controller = new AbortController();
    const requestVersion = favoriteMutationVersion.current;
    favoriteRequestController.current = controller;

    fetchFavoriteTeams(telegramId, { signal: controller.signal })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const error = new Error(`Favorites request failed: ${response.status}`);
          error.status = response.status;
          throw error;
        }
        return data;
      })
      .then((data) => {
        if (controller.signal.aborted || favoriteMutationVersion.current !== requestVersion) return;
        setFavoriteTeams(Array.isArray(data.favorite_teams) ? data.favorite_teams : []);
        setFavoriteMeta({
          resolutionErrors: Number(data.resolution_errors) || 0,
          unresolvedCount: Number(data.unresolved_count) || 0,
        });
        setFavoriteStatus("ready");
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        if (favoriteMutationVersion.current !== requestVersion) return;
        console.error("Failed to load favorite teams:", error);
        setFavoriteStatus(favoriteFailureStatus(error.status));
      })
      .finally(() => {
        if (favoriteRequestController.current === controller) {
          favoriteRequestController.current = null;
        }
      });

    return () => controller.abort();
  }, [telegramId]);

  useEffect(() => {
    if (!telegramId || !predictionResultsVersion) return;

    fetchPredictionStats(telegramId)
      .then((response) => {
        if (!response.ok) throw new Error(`Prediction stats refresh failed: ${response.status}`);
        return response.json();
      })
      .then((data) => setPredictionStats({
        points: Number(data.points) || 0,
        correct: Number(data.correct) || 0,
        wrong: Number(data.wrong) || 0,
        pending: Number(data.pending) || 0,
        total: Number(data.total) || 0,
      }))
      .catch((error) => console.error("Failed to refresh prediction stats:", error));
  }, [predictionResultsVersion, telegramId]);

  const toggleLang = () => {
    setLang((current) => (current === "fa" ? "en" : "fa"));
  };

  const handleCompetitionChange = (competitionKey) => {
    if (!COMPETITIONS[competitionKey] || competitionKey === selectedCompetitionKey) return;

    eventRequestController.current?.abort();
    eventRequestController.current = null;
    scoreChangeTimeouts.current.forEach((timeout) => window.clearTimeout(timeout));
    scoreChangeTimeouts.current.clear();
    setMatches([]);
    setTeams([]);
    setIsLoadingMatches(true);
    setMatchesError("");
    setSelectedMatchId(null);
    setMatchEventsById({});
    setEventUnavailableMatchIds(new Set());
    setEventFailedMatchIds(new Set());
    setLoadingEventsId(null);
    setScoreChangedMatchIds(new Set());
    setReminderMessage("");
    setFavoriteMessage("");
    setSelectedCompetitionKey(competitionKey);
  };

  const readFavoriteResponse = async (response, operation) => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(`${operation} failed: ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return data;
  };

  const favoriteMutationFailed = (error, fallbackMessage) => {
    if (error.name === "AbortError") return;
    console.error("Favorite mutation failed:", error);
    if (error.status === 503) {
      setFavoriteStatus("migration");
      setFavoriteMessage(t.favoriteMigrationRequired);
    } else if (error.status === 502) {
      setFavoriteMessage(t.favoriteProviderError);
    } else {
      setFavoriteMessage(fallbackMessage);
    }
  };

  const addScopedFavorite = (competitionKey, team) => {
    if (!telegramId) {
      setFavoriteMessage(t.favoriteIdentityRequired);
      return;
    }
    if (!competitionKey || team?.id === undefined || team?.id === null) return;

    const teamId = String(team.id);
    const identityKey = favoriteIdentityKey(competitionKey, teamId);
    const displayName = getTeamDisplayName(team);
    const controller = new AbortController();
    favoriteMutationVersion.current += 1;
    favoriteMutationControllers.current.add(controller);
    setFavoritePendingKeys((current) => new Set(current).add(identityKey));
    setFavoriteMessage("");

    addFavoriteTeam({
      telegram_id: telegramId,
      competition_key: competitionKey,
      team_id: teamId,
    }, { signal: controller.signal })
      .then((response) => readFavoriteResponse(response, "Favorite add"))
      .then((data) => {
        const favorite = data.favorite;
        if (favorite?.competition_key && favorite?.team_id !== undefined) {
          setFavoriteTeams((current) => {
            const next = current.filter(
              (item) => favoriteIdentityKey(item.competition_key, item.team_id) !== identityKey,
            );
            next.push(favorite);
            return next;
          });
        }
        setFavoriteMeta({
          resolutionErrors: Number(data.resolution_errors) || 0,
          unresolvedCount: Number(data.unresolved_count) || 0,
        });
        setFavoriteStatus("ready");
        setFavoriteMessage(`${displayName} ${t.addedFavorite}`.trim());
      })
      .catch((error) => favoriteMutationFailed(error, t.favoriteAddError))
      .finally(() => {
        favoriteMutationControllers.current.delete(controller);
        setFavoritePendingKeys((current) => {
          const next = new Set(current);
          next.delete(identityKey);
          return next;
        });
      });
  };

  const removeScopedFavorite = (favorite) => {
    if (!telegramId) {
      setFavoriteMessage(t.favoriteIdentityRequired);
      return;
    }
    if (!favorite?.competition_key || favorite.team_id === undefined || favorite.team_id === null) return;

    const teamId = String(favorite.team_id);
    const identityKey = favoriteIdentityKey(favorite.competition_key, teamId);
    const displayName = getTeamDisplayName(favorite);
    const controller = new AbortController();
    favoriteMutationVersion.current += 1;
    favoriteMutationControllers.current.add(controller);
    setFavoritePendingKeys((current) => new Set(current).add(identityKey));
    setFavoriteMessage("");

    deleteFavoriteTeam({
      telegram_id: telegramId,
      competition_key: favorite.competition_key,
      team_id: teamId,
    }, { signal: controller.signal })
      .then((response) => readFavoriteResponse(response, "Favorite delete"))
      .then((data) => {
        setFavoriteTeams((current) => current.filter(
          (item) => favoriteIdentityKey(item.competition_key, item.team_id) !== identityKey,
        ));
        setFavoriteMeta({
          resolutionErrors: Number(data.resolution_errors) || 0,
          unresolvedCount: Number(data.unresolved_count) || 0,
        });
        setFavoriteStatus("ready");
        setFavoriteMessage(`${displayName} ${t.removedFavorite}`.trim());
      })
      .catch((error) => favoriteMutationFailed(error, t.favoriteRemoveError))
      .finally(() => {
        favoriteMutationControllers.current.delete(controller);
        setFavoritePendingKeys((current) => {
          const next = new Set(current);
          next.delete(identityKey);
          return next;
        });
      });
  };

  const toggleScopedFavorite = (competitionKey, team) => {
    const identityKey = favoriteIdentityKey(competitionKey, team.id);
    if (favoriteIdentityKeys.has(identityKey)) {
      const favorite = favoriteTeams.find(
        (item) => favoriteIdentityKey(item.competition_key, item.team_id) === identityKey,
      );
      if (favorite) removeScopedFavorite(favorite);
    } else {
      addScopedFavorite(competitionKey, team);
    }
  };

  const addReminder = (matchId) => {
    if (!selectedCompetition.supportsReminders) return;

    if (!telegramId) {
      setReminderMessage(t.unavailable);
      return;
    }

    createReminder(telegramId, matchId)
      .then((response) => {
        if (!response.ok) throw new Error(`Reminder request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setReminders(Array.isArray(data.reminders) ? data.reminders : []);
        setReminderMessage(t.addedReminder);
      })
      .catch((error) => {
        console.error("Failed to add reminder:", error);
        setReminderMessage(t.unavailable);
      });
  };

  const removeReminder = (matchId) => {
    if (!selectedCompetition.supportsReminders) return;

    if (!telegramId) {
      setReminderMessage(t.unavailable);
      return;
    }

    deleteReminder(telegramId, matchId)
      .then((response) => {
        if (!response.ok) throw new Error(`Reminder delete failed: ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setReminders(Array.isArray(data.reminders) ? data.reminders : []);
        setReminderMessage(t.removedReminder);
      })
      .catch((error) => {
        console.error("Failed to remove reminder:", error);
        setReminderMessage(t.unavailable);
      });
  };

  const toggleReminder = (matchId) => {
    if (reminderIds.has(matchId)) {
      removeReminder(matchId);
    } else {
      addReminder(matchId);
    }
  };

  const saveMatchPrediction = (matchId, prediction) => {
    if (!selectedCompetition.supportsPredictions) return;

    const matchKey = String(matchId);

    if (!telegramId) {
      setFavoriteMessage(t.unavailable);
      setPredictionErrorMatchIds((currentIds) => new Set(currentIds).add(matchKey));
      return;
    }

    const previousPrediction = predictionsByMatch[matchKey] || "";
    const requestVersion = predictionMutationVersion.current + 1;
    predictionMutationVersion.current = requestVersion;
    predictionSaveRequests.current.set(matchKey, requestVersion);
    const isCurrentSave = () => predictionSaveRequests.current.get(matchKey) === requestVersion;

    setPredictionsByMatch((current) => ({ ...current, [matchKey]: prediction }));
    setSavingPredictionMatchId(matchKey);
    setPredictionSavedMatchId(null);
    setPredictionErrorMatchIds((currentIds) => {
      const nextIds = new Set(currentIds);
      nextIds.delete(matchKey);
      return nextIds;
    });

    savePrediction(telegramId, matchId, prediction)
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          if (!isCurrentSave()) return null;
          if (response.status === 409) {
            setPredictionLockedMatchIds((currentIds) => new Set(currentIds).add(matchKey));
          }
          throw new Error(data.detail || `Prediction request failed: ${response.status}`);
        }
        return data;
      })
      .then((data) => {
        if (!data || !isCurrentSave()) return;

        const predictions = Array.isArray(data.predictions) ? data.predictions : [];
        setPredictionsByMatch((current) => ({
          ...current,
          ...Object.fromEntries(
            predictions.map((item) => [String(item.match_id), item.prediction]),
          ),
        }));
        setPredictionSavedMatchId(matchKey);
        setPredictionErrorMatchIds((currentIds) => {
          const nextIds = new Set(currentIds);
          nextIds.delete(matchKey);
          return nextIds;
        });

        fetchPredictionStats(telegramId)
          .then((response) => {
            if (!response.ok) throw new Error(`Prediction stats request failed: ${response.status}`);
            return response.json();
          })
          .then((statsData) => {
            if (!isCurrentSave()) return;
            setPredictionStats({
              points: Number(statsData.points) || 0,
              correct: Number(statsData.correct) || 0,
              wrong: Number(statsData.wrong) || 0,
              pending: Number(statsData.pending) || 0,
              total: Number(statsData.total) || 0,
            });
          })
          .catch((error) => {
            console.warn("Prediction was saved, but stats refresh failed:", error);
          });
      })
      .catch((error) => {
        if (!isCurrentSave()) return;

        setPredictionsByMatch((current) => {
          const next = { ...current };
          if (previousPrediction) next[matchKey] = previousPrediction;
          else delete next[matchKey];
          return next;
        });
        setPredictionErrorMatchIds((currentIds) => new Set(currentIds).add(matchKey));
        console.error("Failed to save prediction:", error);
      })
      .finally(() => {
        if (isCurrentSave()) setSavingPredictionMatchId(null);
      });
  };

  const handleMatchDetailsClick = (match) => {
    if (!match?.id) return;

    setSelectedMatchId((currentId) => (currentId === match.id ? null : match.id));

    if ((matchEventsById[match.id] || []).length > 0) return;

    setEventUnavailableMatchIds((currentIds) => {
      const nextIds = new Set(currentIds);
      nextIds.delete(match.id);
      return nextIds;
    });
    setEventFailedMatchIds((currentIds) => {
      const nextIds = new Set(currentIds);
      nextIds.delete(match.id);
      return nextIds;
    });
    setLoadingEventsId(match.id);
    eventRequestController.current?.abort();
    const requestController = new AbortController();
    eventRequestController.current = requestController;

    fetchMatchEvents(selectedCompetition, match.id, { signal: requestController.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Events request failed: ${response.status}`);
        }

        return response.json();
      })
      .then((data) => {
        const events = Array.isArray(data.events) ? data.events : [];
        setMatchEventsById((currentEvents) => ({
          ...currentEvents,
          [match.id]: events,
        }));

        if (events.length === 0 && (data.warning || data.error || data.warnings?.length)) {
          setEventUnavailableMatchIds((currentIds) => new Set(currentIds).add(match.id));
        }
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        console.error("Failed to load match events:", error);
        setEventFailedMatchIds((currentIds) => new Set(currentIds).add(match.id));
      })
      .finally(() => {
        if (eventRequestController.current === requestController) {
          eventRequestController.current = null;
          setLoadingEventsId(null);
        }
      });
  };

  const getMatchTeams = (match) => ({
    homeTeam: teamsByName.get(match.home_en) || teamsByName.get(match.home_fa) || teamFromMatch(match, "home"),
    awayTeam: teamsByName.get(match.away_en) || teamsByName.get(match.away_fa) || teamFromMatch(match, "away"),
  });

  const heroStats = selectedCompetition.fixedStats
    ? [
        { key: "teams", value: selectedCompetition.fixedStats.teams, label: t.teams },
        { key: "matches", value: selectedCompetition.fixedStats.matches, label: t.matches },
        { key: "cities", value: selectedCompetition.fixedStats.cities, label: t.cities },
      ]
    : [
        { key: "teams", value: teams.length, label: t.teams },
        { key: "matches", value: matches.length, label: t.matches },
      ];
  const formatStatValue = (value) => (lang === "fa" ? toPersianDigits(value) : String(value));

  const renderMatchCard = (match, options = {}) => {
    const { homeTeam, awayTeam } = getMatchTeams(match);
    const matchKey = String(match.id);

    return (
      <MatchCard
        key={match.id}
        match={match}
        t={t}
        lang={lang}
        onReminderToggle={toggleReminder}
        isReminderActive={reminderIds.has(match.id)}
        homeTeam={homeTeam}
        awayTeam={awayTeam}
        favoriteTeamIds={EMPTY_SET}
        favoriteTeamKeys={EMPTY_SET}
        onDetailsClick={handleMatchDetailsClick}
        isExpanded={selectedMatchId === match.id}
        events={matchEventsById[match.id] || []}
        isLoadingEvents={loadingEventsId === match.id}
        eventsUnavailable={eventUnavailableMatchIds.has(match.id)}
        eventsFailed={eventFailedMatchIds.has(match.id)}
        isScoreChanged={scoreChangedMatchIds.has(match.id)}
        prediction={predictionsByMatch[matchKey] || ""}
        onPredictionSelect={saveMatchPrediction}
        isPredictionSaving={savingPredictionMatchId === matchKey}
        predictionWasSaved={predictionSavedMatchId === matchKey}
        predictionSaveFailed={predictionErrorMatchIds.has(matchKey)}
        predictionForceLocked={predictionLockedMatchIds.has(matchKey)}
        {...options}
        showReminder={selectedCompetition.supportsReminders && (options.showReminder ?? true)}
        showFavorites={false}
        showPredictions={selectedCompetition.supportsPredictions}
      />
    );
  };

  return (
    <main className={`app ${lang}`} dir={t.dir}>
      <AppHeader
        langButton={t.langButton}
        onProfileOpen={() => setActiveTab("profile")}
        onToggleLanguage={toggleLang}
        telegramUser={telegramUser}
      />

      {!['home', 'live', 'competitions', 'news', 'predictions'].includes(activeTab) && (
        <section className="hero legacy-hero">
          <div className="hero-toolbar">
            <BrandLogo key={selectedCompetition.competitionKey} competition={selectedCompetition} lang={lang} />
            <div className="brand-copy">
              <strong>{t.title}</strong>
              <small>{selectedCompetitionKey === "worldcup2026" ? t.brandLabel : selectedCompetitionLabel}</small>
            </div>
          </div>

          <div className="competition-selector" aria-label={t.competitionSelector} role="group">
            {Object.values(COMPETITIONS).map((competition) => (
              <button
                className={selectedCompetitionKey === competition.competitionKey ? "active" : ""}
                key={competition.competitionKey}
                onClick={() => handleCompetitionChange(competition.competitionKey)}
                type="button"
              >
                {competition.labels[lang] || competition.labels.en}
              </button>
            ))}
          </div>

          <div>
            <p className="eyebrow">{heroEyebrow}</p>
            <h1>{t.title}</h1>
            <p className="subtitle">{heroSubtitle}</p>
          </div>

          <div className={`stats-row ${heroStats.length === 2 ? "two-stats" : ""}`}>
            {heroStats.map((stat) => (
              <div key={stat.key}>
                <strong>{formatStatValue(stat.value)}</strong>
                <span>{stat.label}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {activeTab === "home" && <HomePage lang={lang} t={t} />}

      {activeTab === "live" && <LivePage lang={lang} t={t} />}

      {activeTab === "competitions" && (
        <CompetitionsPage
          favoriteMessage={favoriteMessage}
          favoriteIdentityKeys={favoriteIdentityKeys}
          favoritePendingKeys={favoritePendingKeys}
          lang={lang}
          onFavoriteToggle={toggleScopedFavorite}
          t={t}
          telegramId={telegramId}
        />
      )}

      {activeTab === "news" && <NewsPage lang={lang} t={t} />}

      {activeTab === "predictions" && (
        <PredictionsPage lang={lang} t={t} telegramId={telegramId} />
      )}

      {activeTab === "upcoming" && (
        <section className="section">
          <div className="section-header">
            <h2>{t.nextMatches}</h2>
          </div>

          <div className="matches">
            {isLoadingMatches && <p>{t.loadingMatches}</p>}
            {!isLoadingMatches && matchesError && <p>{matchesError}</p>}
            {!isLoadingMatches && !matchesError && upcomingOnlyMatches.length === 0 && (
              <p>{t.noUpcomingMatches}</p>
            )}
            {upcomingMatchGroups.map((group) => (
              <section className="match-day-group" key={group.dateKey}>
                <h3 className="match-day-header">{group.label}</h3>
                <div className="match-day-list">
                  {group.matches.map((match) => renderMatchCard(match))}
                </div>
              </section>
            ))}
          </div>

          {(reminderMessage || favoriteMessage) && (
            <p className="status-message">{reminderMessage || favoriteMessage}</p>
          )}
        </section>
      )}

      {activeTab === "past" && (
        <section className="section">
          <div className="section-header">
            <h2>{t.pastMatches}</h2>
          </div>

          <div className="matches">
            {isLoadingMatches && <p>{t.loadingMatches}</p>}
            {!isLoadingMatches && matchesError && <p>{matchesError}</p>}
            {!isLoadingMatches && !matchesError && pastOnlyMatches.length === 0 && (
              <p>{t.noPastMatches}</p>
            )}
            {pastMatchGroups.map((group) => (
              <section className="match-day-group" key={group.dateKey}>
                <h3 className="match-day-header">{group.label}</h3>
                <div className="match-day-list">
                  {group.matches.map((match) => renderMatchCard(match, { showReminder: false }))}
                </div>
              </section>
            ))}
          </div>
        </section>
      )}

      {activeTab === "worldcup" && (
        <section className="section archive-section">
          <div className="section-header">
            <div>
              <p className="eyebrow">{t.worldcupArchiveSubtitle}</p>
              <h2>{t.worldcupArchiveTitle}</h2>
            </div>
          </div>

          <WorldCupArchive
            summary={worldcupSummary}
            isLoading={isLoadingWorldcupSummary}
            error={worldcupSummaryError}
            lang={lang}
            t={t}
          />
        </section>
      )}

      {activeTab === "profile" && (
        <ProfilePage
          canRemoveReminders={selectedCompetition.supportsReminders}
          favoriteMessage={favoriteMessage}
          favoriteMeta={favoriteMeta}
          favoritePendingKeys={favoritePendingKeys}
          favoriteStatus={favoriteStatus}
          favoriteTeams={favoriteTeams}
          isUserSaved={isUserSaved}
          lang={lang}
          onRemoveFavorite={removeScopedFavorite}
          onRemoveReminder={removeReminder}
          predictionStats={predictionStats}
          reminders={reminders}
          t={t}
          telegramUser={telegramUser}
        />
      )}

      <BottomNav activeTab={activeTab} onChange={setActiveTab} />
    </main>
  );
}

export default App;
