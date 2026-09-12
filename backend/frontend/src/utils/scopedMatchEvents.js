import {
  canShowEvents,
} from "./matches.js";
import {
  competitionEventIdentity,
  competitionEventIdentityKey,
  eventRequestFailureKind,
  isCurrentEventRequest,
} from "./events.js";

export const EMPTY_MATCH_EVENT_STATE = Object.freeze({
  events: [],
  failed: false,
  loaded: false,
  loading: false,
  unavailable: false,
});

export function matchEventIdentity(match) {
  return competitionEventIdentity({
    competition_key: match?.competition_key,
    season_key: match?.season_key,
  }, match);
}

export function createScopedMatchEventController(fetchEvents) {
  let activeRequest = null;
  let requestVersion = 0;
  let snapshot = { selectedIdentityKey: "", statesByIdentity: {} };
  const listeners = new Set();
  const publish = (next) => {
    snapshot = next;
    listeners.forEach((listener) => listener());
  };
  const updateEventState = (identityKey, eventState) => {
    publish({
      ...snapshot,
      statesByIdentity: {
        ...snapshot.statesByIdentity,
        [identityKey]: eventState,
      },
    });
  };
  const stopActiveRequest = () => {
    if (!activeRequest) return;
    const { identityKey } = activeRequest;
    requestVersion += 1;
    activeRequest.controller.abort();
    activeRequest = null;
    updateEventState(identityKey, {
      ...(snapshot.statesByIdentity[identityKey] || EMPTY_MATCH_EVENT_STATE),
      loading: false,
    });
  };

  const controller = {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    eventProps(match) {
      const identity = matchEventIdentity(match);
      const identityKey = competitionEventIdentityKey(identity);
      const eventState = snapshot.statesByIdentity[identityKey] || EMPTY_MATCH_EVENT_STATE;
      return {
        events: eventState.events,
        eventsFailed: eventState.failed,
        eventsUnavailable: eventState.unavailable,
        isExpanded: Boolean(identityKey && snapshot.selectedIdentityKey === identityKey),
        isLoadingEvents: eventState.loading,
        onDetailsClick: controller.toggle,
        showEvents: Boolean(identityKey && canShowEvents(match)),
      };
    },
    resetSelection() {
      stopActiveRequest();
      if (snapshot.selectedIdentityKey) {
        publish({ ...snapshot, selectedIdentityKey: "" });
      }
    },
    toggle(match) {
      const identity = matchEventIdentity(match);
      const identityKey = competitionEventIdentityKey(identity);
      if (!identityKey || !canShowEvents(match)) return Promise.resolve();

      if (snapshot.selectedIdentityKey === identityKey) {
        stopActiveRequest();
        publish({ ...snapshot, selectedIdentityKey: "" });
        return Promise.resolve();
      }

      stopActiveRequest();
      publish({ ...snapshot, selectedIdentityKey: identityKey });
      const cachedState = snapshot.statesByIdentity[identityKey];
      if (cachedState?.loaded) return Promise.resolve();

      const requestController = new AbortController();
      const version = requestVersion + 1;
      requestVersion = version;
      activeRequest = { controller: requestController, identityKey, version };
      updateEventState(identityKey, {
        events: cachedState?.events || [],
        failed: false,
        loaded: false,
        loading: true,
        unavailable: false,
      });

      return Promise.resolve().then(() => fetchEvents(
        identity.competition_key,
        identity.season_key,
        identity.match_id,
        { signal: requestController.signal },
      )).then((response) => {
        if (!response.ok) {
          const error = new Error("Match events request failed");
          error.status = response.status;
          throw error;
        }
        return response.json();
      }).then((payload) => {
        if (!isCurrentEventRequest(activeRequest, identityKey, version)) return;
        const events = Array.isArray(payload?.events) ? payload.events : [];
        const sourceUnavailable = events.length === 0 && Boolean(
          payload?.warning
          || payload?.error
          || (Array.isArray(payload?.warnings) && payload.warnings.length > 0),
        );
        updateEventState(identityKey, {
          events,
          failed: false,
          loaded: !sourceUnavailable,
          loading: false,
          unavailable: sourceUnavailable,
        });
      }).catch((error) => {
        if (error.name === "AbortError") return;
        if (!isCurrentEventRequest(activeRequest, identityKey, version)) return;
        const failureKind = eventRequestFailureKind(error.status);
        console.error("Failed to load daily match events", {
          status: Number(error.status) || 0,
        });
        updateEventState(identityKey, {
          events: [],
          failed: failureKind === "failed",
          loaded: false,
          loading: false,
          unavailable: failureKind === "unavailable",
        });
      }).finally(() => {
        if (isCurrentEventRequest(activeRequest, identityKey, version)) {
          activeRequest = null;
        }
      });
    },
    dispose() {
      controller.resetSelection();
      listeners.clear();
    },
  };
  return controller;
}
