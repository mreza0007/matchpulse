function normalizeText(value, { lower = false } = {}) {
  const normalized = value === undefined || value === null
    ? ""
    : String(value).trim();
  return lower ? normalized.toLowerCase() : normalized;
}

export function reminderIdentity(competitionKey, seasonKey, matchId) {
  const identity = {
    competition_key: normalizeText(competitionKey, { lower: true }),
    season_key: normalizeText(seasonKey, { lower: true }),
    match_id: normalizeText(matchId),
  };
  if (!identity.competition_key || !identity.season_key || !identity.match_id) {
    return null;
  }
  return identity;
}

export function reminderIdentityFromMatch(competition, match) {
  return reminderIdentity(
    competition?.competition_key,
    competition?.season_key,
    match?.id,
  );
}

export function reminderIdentityFromRecord(reminder) {
  return reminderIdentity(
    reminder?.competition_key,
    reminder?.season_key,
    reminder?.match_id,
  );
}

export function reminderIdentityKey(identity) {
  if (!identity) return "";
  return JSON.stringify([
    identity.competition_key,
    identity.season_key,
    identity.match_id,
  ]);
}

export function reminderIdentityKeyFromRecord(reminder) {
  return reminderIdentityKey(reminderIdentityFromRecord(reminder));
}

export function buildReminderIdentitySet(reminders) {
  return new Set(
    reminders
      .map(reminderIdentityKeyFromRecord)
      .filter(Boolean),
  );
}
export function tryBeginReminderMutation(pendingKeys, identityKey) {
  if (!identityKey || pendingKeys.has(identityKey)) return false;
  pendingKeys.add(identityKey);
  return true;
}

export function finishReminderMutation(pendingKeys, identityKey) {
  pendingKeys.delete(identityKey);
}


export function reminderRequestBody(telegramId, identity) {
  return {
    telegram_id: telegramId,
    competition_key: identity.competition_key,
    season_key: identity.season_key,
    match_id: identity.match_id,
  };
}

export function isReminderEligibleMatch(match, now = Date.now()) {
  const status = normalizeText(
    match?.status_key ?? match?.status,
    { lower: true },
  ).replaceAll("-", "_").replaceAll(" ", "_");
  if (
    status !== "upcoming"
    || match?.is_live === true
    || match?.is_finished === true
  ) {
    return false;
  }

  const kickoff = normalizeText(match?.kickoff_utc);
  if (!/(?:z|[+-]00:00)$/i.test(kickoff)) return false;
  const kickoffTime = Date.parse(kickoff);
  return Number.isFinite(kickoffTime) && kickoffTime > now;
}

export function reminderErrorTranslationKey(status) {
  if (status === 409) return "reminderIneligible";
  if (status === 404) return "reminderStale";
  if (status === 501) return "reminderDisabled";
  if (status === 502) return "reminderProviderError";
  if (status === 503) return "reminderStorageError";
  return "reminderError";
}
