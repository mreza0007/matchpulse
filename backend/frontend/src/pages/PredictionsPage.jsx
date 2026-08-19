import { useEffect, useMemo, useRef, useState } from "react";
import { fetchCompetitions } from "../api/football.js";
import {
  fetchPredictableMatches,
  fetchPredictionHistory,
  fetchPredictionLeaderboard,
  fetchPredictionStats,
  fetchUserPredictions,
  savePrediction,
} from "../api/predictions.js";
import CompetitionLogo from "../components/competitions/CompetitionLogo.jsx";
import PredictionHistoryItem from "../components/predictions/PredictionHistoryItem.jsx";
import PredictionLeaderboard from "../components/predictions/PredictionLeaderboard.jsx";
import PredictionMatchCard from "../components/predictions/PredictionMatchCard.jsx";
import { getCompetitionName } from "../utils/competitions.js";

const EMPTY_STATS = { points: 0, correct: 0, wrong: 0, pending: 0, total: 0 };

function scopeKey(competition) {
  return `${competition.competition_key}:${competition.season_key}`;
}

function normalizeStats(value) {
  return {
    points: Number(value?.points) || 0,
    correct: Number(value?.correct) || 0,
    wrong: Number(value?.wrong) || 0,
    pending: Number(value?.pending) || 0,
    total: Number(value?.total) || 0,
  };
}

async function responseJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (response.ok) return payload;
  const error = new Error("Prediction request failed");
  error.status = response.status;
  throw error;
}

function predictionErrorLabel(status, t) {
  if (status === 409) return t.predictionDeadlinePassed;
  if (status === 404) return t.predictionMatchUnavailable;
  if (status === 501) return t.predictionCompetitionUnavailable;
  if (status === 502 || status === 503) return t.predictionServiceUnavailable;
  return t.predictionLoadError;
}

function sectionErrorLabel(status, fallback, t) {
  if (status === 502 || status === 503) return t.predictionServiceUnavailable;
  return fallback;
}

function PredictionsSkeleton() {
  return (
    <div className="predictions-skeleton" aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}

function PredictionSectionSkeleton() {
  return <div className="prediction-section-skeleton" aria-hidden="true"><span /><span /></div>;
}

export default function PredictionsPage({ lang, t, telegramId }) {
  const hasUsableTelegramId = (
    (Number.isSafeInteger(telegramId) && telegramId > 0)
    || (typeof telegramId === "string" && /^[1-9]\d*$/.test(telegramId))
  );
  const [competitions, setCompetitions] = useState([]);
  const [directoryStatus, setDirectoryStatus] = useState("loading");
  const [directoryRetry, setDirectoryRetry] = useState(0);
  const [selectedKey, setSelectedKey] = useState("");
  const [retryVersion, setRetryVersion] = useState(0);
  const [view, setView] = useState({
    matches: [],
    predictions: [],
    stats: EMPTY_STATS,
    isLoading: false,
    errorStatus: null,
  });
  const [matchStates, setMatchStates] = useState({});
  const [historyView, setHistoryView] = useState({
    items: [],
    evaluationErrors: 0,
    isLoading: false,
    errorStatus: null,
  });
  const [leaderboardView, setLeaderboardView] = useState({
    entries: [],
    evaluationErrors: 0,
    isLoading: false,
    errorStatus: null,
  });
  const [historyRefreshVersion, setHistoryRefreshVersion] = useState(0);
  const [leaderboardRefreshVersion, setLeaderboardRefreshVersion] = useState(0);
  const cache = useRef(new Map());
  const historyCache = useRef(new Map());
  const leaderboardCache = useRef(new Map());
  const activeRequest = useRef(null);
  const activeHistoryRequest = useRef(null);
  const activeLeaderboardRequest = useRef(null);
  const requestVersion = useRef(0);
  const historyRequestVersion = useRef(0);
  const leaderboardRequestVersion = useRef(0);
  const saveRequests = useRef(new Map());

  useEffect(() => {
    const controller = new AbortController();
    fetchCompetitions({ signal: controller.signal })
      .then(responseJson)
      .then((payload) => {
        if (controller.signal.aborted) return;
        const enabled = Array.isArray(payload.competitions)
          ? payload.competitions.filter(
              (competition) => competition?.supports_predictions === true && competition?.season_key,
            )
          : [];
        setCompetitions(enabled);
        setDirectoryStatus("ready");
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        console.error("Failed to load prediction competitions:", error);
        setDirectoryStatus("error");
      });
    return () => controller.abort();
  }, [directoryRetry]);

  const selectedCompetition = useMemo(
    () => competitions.find((item) => item.competition_key === selectedKey) || competitions[0] || null,
    [competitions, selectedKey],
  );
  const selectedScope = selectedCompetition ? scopeKey(selectedCompetition) : "";
  const selectedScopeRef = useRef(selectedScope);
  selectedScopeRef.current = selectedScope;

  useEffect(() => {
    if (!hasUsableTelegramId || !selectedCompetition) return undefined;
    const key = scopeKey(selectedCompetition);
    const cached = cache.current.get(key) || {};
    const isComplete = Object.hasOwn(cached, "matches")
      && Object.hasOwn(cached, "predictions")
      && Object.hasOwn(cached, "stats");

    if (isComplete && retryVersion === 0) {
      setView({ ...cached, isLoading: false, errorStatus: null });
      return undefined;
    }

    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const version = requestVersion.current + 1;
    requestVersion.current = version;
    setView({
      matches: cached.matches || [],
      predictions: cached.predictions || [],
      stats: cached.stats || EMPTY_STATS,
      isLoading: true,
      errorStatus: null,
    });

    const requestOptions = {
      competitionKey: selectedCompetition.competition_key,
      seasonKey: selectedCompetition.season_key,
      signal: controller.signal,
    };
    const requests = [
      fetchPredictableMatches(
        selectedCompetition.competition_key,
        selectedCompetition.season_key,
        { signal: controller.signal },
      ).then(responseJson).then((payload) => ["matches", Array.isArray(payload.matches) ? payload.matches : []]),
      fetchUserPredictions(telegramId, requestOptions)
        .then(responseJson)
        .then((payload) => ["predictions", Array.isArray(payload.predictions) ? payload.predictions : []]),
      fetchPredictionStats(telegramId, requestOptions)
        .then(responseJson)
        .then((payload) => ["stats", normalizeStats(payload)]),
    ];

    Promise.allSettled(requests).then((results) => {
      if (controller.signal.aborted || requestVersion.current !== version) return;
      const next = { ...cached };
      let errorStatus = null;
      results.forEach((result) => {
        if (result.status === "fulfilled") {
          const [field, value] = result.value;
          next[field] = value;
        } else if (result.reason?.name !== "AbortError" && errorStatus == null) {
          errorStatus = result.reason?.status || 0;
        }
      });
      cache.current.set(key, next);
      setView({
        matches: next.matches || [],
        predictions: next.predictions || [],
        stats: next.stats || EMPTY_STATS,
        isLoading: false,
        errorStatus,
      });
    });

    return () => controller.abort();
  }, [hasUsableTelegramId, retryVersion, selectedCompetition, telegramId]);

  useEffect(() => {
    if (!hasUsableTelegramId || !selectedCompetition) return undefined;
    const key = scopeKey(selectedCompetition);
    const cached = historyCache.current.get(key);
    if (cached && historyRefreshVersion === 0) {
      setHistoryView({ ...cached, isLoading: false, errorStatus: null });
      return undefined;
    }

    activeHistoryRequest.current?.abort();
    const controller = new AbortController();
    activeHistoryRequest.current = controller;
    const version = historyRequestVersion.current + 1;
    historyRequestVersion.current = version;
    setHistoryView({
      items: cached?.items || [],
      evaluationErrors: cached?.evaluationErrors || 0,
      isLoading: true,
      errorStatus: null,
    });

    fetchPredictionHistory(telegramId, {
      competitionKey: selectedCompetition.competition_key,
      seasonKey: selectedCompetition.season_key,
      signal: controller.signal,
    })
      .then(responseJson)
      .then((payload) => {
        if (controller.signal.aborted || historyRequestVersion.current !== version) return;
        const next = {
          items: Array.isArray(payload.history) ? payload.history : [],
          evaluationErrors: Number(payload.evaluation_errors) || 0,
        };
        historyCache.current.set(key, next);
        setHistoryView({ ...next, isLoading: false, errorStatus: null });
      })
      .catch((error) => {
        if (error.name === "AbortError" || historyRequestVersion.current !== version) return;
        setHistoryView({
          items: cached?.items || [],
          evaluationErrors: cached?.evaluationErrors || 0,
          isLoading: false,
          errorStatus: error.status || 0,
        });
      });

    return () => controller.abort();
  }, [hasUsableTelegramId, historyRefreshVersion, selectedCompetition, telegramId]);

  useEffect(() => {
    if (!hasUsableTelegramId || !selectedCompetition) return undefined;
    const key = scopeKey(selectedCompetition);
    const cached = leaderboardCache.current.get(key);
    if (cached && leaderboardRefreshVersion === 0) {
      setLeaderboardView({ ...cached, isLoading: false, errorStatus: null });
      return undefined;
    }

    activeLeaderboardRequest.current?.abort();
    const controller = new AbortController();
    activeLeaderboardRequest.current = controller;
    const version = leaderboardRequestVersion.current + 1;
    leaderboardRequestVersion.current = version;
    setLeaderboardView({
      entries: cached?.entries || [],
      evaluationErrors: cached?.evaluationErrors || 0,
      isLoading: true,
      errorStatus: null,
    });

    fetchPredictionLeaderboard({
      competitionKey: selectedCompetition.competition_key,
      seasonKey: selectedCompetition.season_key,
      signal: controller.signal,
    })
      .then(responseJson)
      .then((payload) => {
        if (controller.signal.aborted || leaderboardRequestVersion.current !== version) return;
        const next = {
          entries: Array.isArray(payload.leaderboard) ? payload.leaderboard : [],
          evaluationErrors: Number(payload.evaluation_errors) || 0,
        };
        leaderboardCache.current.set(key, next);
        setLeaderboardView({ ...next, isLoading: false, errorStatus: null });
      })
      .catch((error) => {
        if (error.name === "AbortError" || leaderboardRequestVersion.current !== version) return;
        setLeaderboardView({
          entries: cached?.entries || [],
          evaluationErrors: cached?.evaluationErrors || 0,
          isLoading: false,
          errorStatus: error.status || 0,
        });
      });

    return () => controller.abort();
  }, [hasUsableTelegramId, leaderboardRefreshVersion, selectedCompetition]);

  useEffect(() => () => {
    activeRequest.current?.abort();
    activeHistoryRequest.current?.abort();
    activeLeaderboardRequest.current?.abort();
    saveRequests.current.forEach((controller) => controller.abort());
  }, []);

  const predictionsByMatch = useMemo(
    () => new Map(view.predictions.map((prediction) => [String(prediction.match_id), prediction])),
    [view.predictions],
  );

  const competitionView = selectedCompetition
    ? { ...selectedCompetition, name: getCompetitionName(selectedCompetition, lang) }
    : null;

  const saveExactScore = async (matchId, homeScore, awayScore) => {
    if (!hasUsableTelegramId || !selectedCompetition) return;
    const matchKey = String(matchId);
    const key = scopeKey(selectedCompetition);
    const stateKey = `${key}:${matchKey}`;
    saveRequests.current.get(stateKey)?.abort();
    const controller = new AbortController();
    saveRequests.current.set(stateKey, controller);
    setMatchStates((current) => ({
      ...current,
      [stateKey]: { isSaving: true, isLocked: false, errorMessage: "", saved: false },
    }));

    try {
      const payload = await savePrediction({
        telegram_id: telegramId,
        competition_key: selectedCompetition.competition_key,
        season_key: selectedCompetition.season_key,
        match_id: matchKey,
        prediction_type: "exact_score",
        home_score: homeScore,
        away_score: awayScore,
      }, { signal: controller.signal }).then(responseJson);
      if (controller.signal.aborted) return;

      const scopedPredictions = (Array.isArray(payload.predictions) ? payload.predictions : [])
        .filter((prediction) => (
          prediction.competition_key === selectedCompetition.competition_key
          && prediction.season_key === selectedCompetition.season_key
        ));
      const cached = cache.current.get(key) || {};
      const nextPredictions = scopedPredictions.length > 0
        ? scopedPredictions
        : [
            ...(cached.predictions || []).filter((item) => String(item.match_id) !== matchKey),
            {
              competition_key: selectedCompetition.competition_key,
              season_key: selectedCompetition.season_key,
              match_id: matchKey,
              prediction_type: "exact_score",
              home_score: homeScore,
              away_score: awayScore,
            },
          ];
      const nextCache = { ...cached, predictions: nextPredictions };
      cache.current.set(key, nextCache);
      if (selectedScopeRef.current === key) {
        setView((current) => ({ ...current, predictions: nextPredictions }));
      }
      setMatchStates((current) => ({
        ...current,
        [stateKey]: { isSaving: false, isLocked: false, errorMessage: "", saved: true },
      }));

      historyCache.current.delete(key);
      leaderboardCache.current.delete(key);
      if (selectedScopeRef.current === key) {
        setHistoryRefreshVersion((value) => value + 1);
        setLeaderboardRefreshVersion((value) => value + 1);
      }

      try {
        const stats = normalizeStats(await fetchPredictionStats(telegramId, {
          competitionKey: selectedCompetition.competition_key,
          seasonKey: selectedCompetition.season_key,
          signal: controller.signal,
        }).then(responseJson));
        cache.current.set(key, { ...nextCache, stats });
        if (selectedScopeRef.current === key) {
          setView((current) => ({ ...current, stats }));
        }
      } catch (error) {
        if (error.name !== "AbortError") console.warn("Prediction saved; stats refresh failed.");
      }
    } catch (error) {
      if (error.name === "AbortError") return;
      const isLocked = error.status === 409 || error.status === 404;
      setMatchStates((current) => ({
        ...current,
        [stateKey]: {
          isSaving: false,
          isLocked,
          errorMessage: predictionErrorLabel(error.status, t),
          saved: false,
        },
      }));
    } finally {
      if (saveRequests.current.get(stateKey) === controller) saveRequests.current.delete(stateKey);
    }
  };

  if (!hasUsableTelegramId) {
    return (
      <section className="predictions-page">
        <h1>{t.predictionsPage}</h1>
        <div className="home-empty-state predictions-auth-state">{t.predictionSignInRequired}</div>
      </section>
    );
  }

  if (directoryStatus === "loading") {
    return <section className="predictions-page"><h1>{t.predictionsPage}</h1><PredictionsSkeleton /></section>;
  }

  if (directoryStatus === "error") {
    return (
      <section className="predictions-page">
        <h1>{t.predictionsPage}</h1>
        <div className="home-empty-state predictions-error-state">
          <p>{t.predictionCompetitionsLoadError}</p>
          <button onClick={() => {
            setDirectoryStatus("loading");
            setDirectoryRetry((value) => value + 1);
          }} type="button">{t.retry}</button>
        </div>
      </section>
    );
  }

  if (!selectedCompetition) {
    return (
      <section className="predictions-page">
        <h1>{t.predictionsPage}</h1>
        <div className="home-empty-state">{t.predictionNoSupportedCompetitions}</div>
      </section>
    );
  }

  return (
    <section className="predictions-page">
      <h1>{t.predictionsPage}</h1>

      <section className="prediction-summary" aria-label={t.predictionSummary}>
        <div className="prediction-summary-primary">
          <span>{t.predictionPoints}</span>
          <strong>{view.stats.points}</strong>
        </div>
        <div className="prediction-summary-grid">
          <span>{t.predictionTotal}<strong>{view.stats.total}</strong></span>
          <span>{t.predictionCorrect}<strong>{view.stats.correct}</strong></span>
          <span>{t.predictionPending}<strong>{view.stats.pending}</strong></span>
          <span>{t.predictionWrong}<strong>{view.stats.wrong}</strong></span>
        </div>
      </section>

      <section className="prediction-competition-section">
        <h2>{t.predictionCompetitions}</h2>
        <div className="prediction-competition-selector">
          {competitions.map((competition) => (
            <button
              className={competition.competition_key === selectedCompetition.competition_key ? "active" : ""}
              key={scopeKey(competition)}
              onClick={() => {
                setSelectedKey(competition.competition_key);
                setRetryVersion(0);
                setHistoryRefreshVersion(0);
                setLeaderboardRefreshVersion(0);
              }}
              type="button"
            >
              <CompetitionLogo competition={competition} />
              <span>
                <strong>{getCompetitionName(competition, lang)}</strong>
                <small>{t.season}: {competition.season_key}</small>
              </span>
            </button>
          ))}
        </div>
      </section>

      {view.isLoading && view.matches.length === 0 && <PredictionsSkeleton />}

      {!view.isLoading && view.errorStatus != null && view.matches.length === 0 && (
        <div className="home-empty-state predictions-error-state">
          <p>{predictionErrorLabel(view.errorStatus, t)}</p>
          <button onClick={() => setRetryVersion((value) => value + 1)} type="button">
            {t.retry}
          </button>
        </div>
      )}

      {view.errorStatus != null && view.matches.length > 0 && (
        <p className="home-inline-warning">{predictionErrorLabel(view.errorStatus, t)}</p>
      )}

      {!view.isLoading && view.errorStatus == null && view.matches.length === 0 && (
        <div className="home-empty-state">{t.predictionNoMatches}</div>
      )}

      {view.matches.length > 0 && (
        <div className={`prediction-match-list ${view.isLoading ? "loading" : ""}`}>
          {view.matches.map((match) => {
            const matchKey = String(match.id);
            const state = matchStates[`${scopeKey(selectedCompetition)}:${matchKey}`] || {};
            const prediction = predictionsByMatch.get(matchKey);
            return (
              <PredictionMatchCard
                competition={competitionView}
                errorMessage={state.errorMessage}
                isLocked={state.isLocked}
                isSaving={state.isSaving}
                key={`${scopeKey(selectedCompetition)}:${matchKey}`}
                lang={lang}
                match={match}
                onSave={saveExactScore}
                prediction={prediction}
                saveWasSuccessful={state.saved}
                t={t}
              />
            );
          })}
        </div>
      )}

      <section className="prediction-history-section">
        <h2>{t.predictionHistoryTitle}</h2>
        {historyView.isLoading && historyView.items.length === 0 && <PredictionSectionSkeleton />}
        {historyView.errorStatus != null && historyView.items.length === 0 && (
          <div className="prediction-section-state">
            <p>{sectionErrorLabel(historyView.errorStatus, t.predictionHistoryLoadError, t)}</p>
            <button onClick={() => setHistoryRefreshVersion((value) => value + 1)} type="button">
              {t.retry}
            </button>
          </div>
        )}
        {historyView.errorStatus != null && historyView.items.length > 0 && (
          <p className="home-inline-warning">
            {sectionErrorLabel(historyView.errorStatus, t.predictionHistoryLoadError, t)}
          </p>
        )}
        {!historyView.isLoading && historyView.errorStatus == null && historyView.items.length === 0 && (
          <div className="prediction-section-state">{t.predictionHistoryEmpty}</div>
        )}
        {historyView.evaluationErrors > 0 && (
          <p className="home-inline-warning">{t.predictionEvaluationWarning}</p>
        )}
        {historyView.items.length > 0 && (
          <div className={`prediction-history-list ${historyView.isLoading ? "loading" : ""}`}>
            {historyView.items.map((item, index) => (
              <PredictionHistoryItem item={item} key={`${item.updated_at || "history"}:${index}`} t={t} />
            ))}
          </div>
        )}
      </section>

      <section className="prediction-leaderboard-section">
        <h2>{t.predictionLeaderboardTitle}</h2>
        {leaderboardView.isLoading && leaderboardView.entries.length === 0 && <PredictionSectionSkeleton />}
        {leaderboardView.errorStatus != null && leaderboardView.entries.length === 0 && (
          <div className="prediction-section-state">
            <p>{sectionErrorLabel(
              leaderboardView.errorStatus,
              t.predictionLeaderboardLoadError,
              t,
            )}</p>
            <button onClick={() => setLeaderboardRefreshVersion((value) => value + 1)} type="button">
              {t.retry}
            </button>
          </div>
        )}
        {leaderboardView.errorStatus != null && leaderboardView.entries.length > 0 && (
          <p className="home-inline-warning">
            {sectionErrorLabel(leaderboardView.errorStatus, t.predictionLeaderboardLoadError, t)}
          </p>
        )}
        {!leaderboardView.isLoading
          && leaderboardView.errorStatus == null
          && leaderboardView.entries.length === 0 && (
            <div className="prediction-section-state">{t.predictionLeaderboardEmpty}</div>
          )}
        {leaderboardView.evaluationErrors > 0 && (
          <p className="home-inline-warning">{t.predictionEvaluationWarning}</p>
        )}
        {leaderboardView.entries.length > 0 && (
          <div className={leaderboardView.isLoading ? "prediction-section-loading" : ""}>
            <PredictionLeaderboard entries={leaderboardView.entries} t={t} />
          </div>
        )}
      </section>
    </section>
  );
}
