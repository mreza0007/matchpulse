import { formatCountdown, getKickoffTime } from "./dates.js";
import { getLocalizedTeamName } from "./teams.js";

export function getScoreValue(match, keys) {
  for (const key of keys) {
    const value = match?.[key];

    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }

  return null;
}

export function getMatchScore(match) {
  const homeScore = getScoreValue(match, [
    "home_score",
    "homeScore",
    "home_goals",
    "homeGoals",
    "home_team_score",
    "homeTeamScore",
    "score_home",
    "scoreHome",
  ]);
  const awayScore = getScoreValue(match, [
    "away_score",
    "awayScore",
    "away_goals",
    "awayGoals",
    "away_team_score",
    "awayTeamScore",
    "score_away",
    "scoreAway",
  ]);

  if (homeScore === null || awayScore === null) return "";

  return `${homeScore} - ${awayScore}`;
}

export function getMatchScoreSignature(match) {
  return `${getScoreValue(match, ["home_score", "homeScore"])}:${getScoreValue(match, [
    "away_score",
    "awayScore",
  ])}`;
}

export function matchesAreEqual(currentMatch, nextMatch) {
  return JSON.stringify(currentMatch) === JSON.stringify(nextMatch);
}


export function normalizeMatchStatus(match) {
  const status = String(match?.status || "").toLowerCase().replace(/[-\s]/g, "_");

  const statusText = [
    match?.status_title,
    match?.statusTitle,
    match?.time_elapsed,
    match?.live_badge,
    match?.raw_live_badge,
    match?.match_status,
    match?.raw_provider_status?.status,
    match?.raw_provider_status?.statusTitle,
    match?.raw_provider_status?.status_title,
  ].filter(Boolean).join(" ").toLowerCase();
  const activeBreak = [
    "half time",
    "half-time",
    "halftime",
    "intermission",
    "break",
    "extra time break",
    "penalty shootout",
    "\u067e\u0627\u06cc\u0627\u0646 \u0646\u06cc\u0645\u0647 \u0627\u0648\u0644",
    "\u067e\u0627\u06cc\u0627\u0646 \u0646\u06cc\u0645\u0647",
    "\u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647",
    "\u0627\u0633\u062a\u0631\u0627\u062d\u062a \u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647",
    "\u0627\u0633\u062a\u0631\u0627\u062d\u062a \u0648\u0642\u062a \u0627\u0636\u0627\u0641\u0647",
    "\u0636\u0631\u0628\u0627\u062a \u067e\u0646\u0627\u0644\u062a\u06cc",
    "ظ¾ط§غŒط§ظ† ظ†غŒظ…ظ‡",
    "ظ¾ط§غŒط§ظ† ظ†غŒظ…ظ‡ ط§ظˆظ„",
    "ط¨غŒظ† ط¯ظˆ ظ†غŒظ…ظ‡",
  ].some((marker) => statusText.includes(marker));

  if (match?.is_live || [
    "live", "in_progress", "ht", "half_time", "halftime", "break", "et",
    "extra_time_break", "penalties", "penalty_shootout", "shootout",
    "intermission", "pause", "extra_time_halftime",
  ].includes(status) || activeBreak) return "live";
  if (match?.is_finished || status === "finished") return "finished";
  if (status === "pending_result") return "pending_result";
  return "upcoming";
}

export function isFinishedMatch(match) {
  return normalizeMatchStatus(match) === "finished" || match?.is_finished === true;
}

export function isPendingResultMatch(match) {
  return normalizeMatchStatus(match) === "pending_result";
}

export function isResultTabMatch(match) {
  return isFinishedMatch(match) || isPendingResultMatch(match);
}

export function isLiveMatch(match) {
  return normalizeMatchStatus(match) === "live" || match?.is_live === true;
}

export function isPastPendingResult(match) {
  if (!isPendingResultMatch(match)) return false;
  const kickoff = getKickoffTime(match);
  return Number.isFinite(kickoff) && kickoff <= Date.now();
}

export function canShowEvents(match) {
  if (!match?.id) return false;
  if (match.can_show_event_button === true) return true;
  return isFinishedMatch(match) || isLiveMatch(match) || isPastPendingResult(match);
}

export function isFutureMatchStatus(match) {
  if (match?.is_upcoming) return true;

  const status = String(match?.status || "").toLowerCase().replace(/[-\s]/g, "_");
  return ["scheduled", "upcoming", "notstarted", "not_started"].includes(status);
}

export function isPredictionLocked(match) {
  if (isLiveMatch(match) || isFinishedMatch(match) || isPendingResultMatch(match)) return true;
  if (!isFutureMatchStatus(match)) return true;
  const kickoffTime = getKickoffTime(match);
  return !Number.isFinite(kickoffTime) || kickoffTime <= Date.now();
}

export function getPredictionLabel(match, prediction, lang, t) {
  if (prediction === "draw") return t.predictionDraw;
  const side = prediction === "home" ? "home" : "away";
  return t.predictionWin.replace("{team}", getLocalizedTeamName(match, side, lang));
}


export function getHeroMatch(liveMatches, upcomingMatches, resultMatches) {
  return liveMatches[0] || upcomingMatches[0] || resultMatches[0] || null;
}

export function getHeroMode(match) {
  if (!match) return "empty";
  if (isLiveMatch(match)) return "live";
  if (isFutureMatchStatus(match)) return "upcoming";
  return "result";
}

export function filterHeroFromList(matches, heroMatch) {
  if (!heroMatch?.id) return matches;
  return matches.filter((match) => String(match.id) !== String(heroMatch.id));
}


export function hasPenaltyScores(match) {
  return match?.home_penalty_score != null && match?.away_penalty_score != null;
}

export function getPenaltyShootoutLabel(lang) {
  return lang === "fa" ? "ضربات پنالتی" : "Penalty shootout";
}

export function isLivePenaltyShootout(match) {
  if (!match || isFinishedMatch(match) || !isLiveMatch(match) || !hasPenaltyScores(match)) return false;

  const text = [
    match.live_phase,
    match.live_badge,
    match.raw_live_badge,
    match.status_title,
    match.statusTitle,
    match.raw_provider_status?.statusTitle,
    match.raw_provider_status?.status_title,
  ].filter(Boolean).join(" ").toLowerCase();

  return text.includes("penalty_shootout") ||
    text.includes("penalty shootout") ||
    text.includes("penalties") ||
    text.includes("ضربات پنالتی") ||
    hasPenaltyScores(match);
}

export function getLiveDisplayBadge(match, lang, t) {
  if (isLivePenaltyShootout(match)) return getPenaltyShootoutLabel(lang);

  const normalizedDisplay = lang === "en"
    ? match?.live_display_en || match?.live_display
    : match?.live_display_fa || match?.live_display;
  if (normalizedDisplay) return String(normalizedDisplay).trim();
  if (match?.live_badge) return String(match.live_badge).trim();

  const values = [
    match?.raw_live_badge,
    match?.time_elapsed,
    match?.raw_minute,
    match?.minute,
    match?.status_title,
    match?.statusTitle,
  ].filter((value) => value !== null && value !== undefined && String(value).trim());
  const minutePattern = /(?:^|\s)([0-9۰-۹٠-٩]{1,3}(?:\s*\+\s*[0-9۰-۹٠-٩]{1,2})?)\s*['′’]?(?:$|\s)/;

  for (const value of values) {
    const matchMinute = String(value).trim().match(minutePattern);
    if (matchMinute) return `${matchMinute[1].replace(/\s+/g, "")}'`;
  }

  const statusText = values.join(" ").toLowerCase();
  const breakMarkers = [
    "ht", "half time", "half-time", "halftime", "interval", "between halves",
    "\u067e\u0627\u06cc\u0627\u0646 \u0646\u06cc\u0645\u0647", "\u0628\u06cc\u0646 \u062f\u0648 \u0646\u06cc\u0645\u0647",
    "ظ¾ط§غŒط§ظ† ظ†غŒظ…ظ‡", "ط¨غŒظ† ط¯ظˆ ظ†غŒظ…ظ‡",
  ];
  if (breakMarkers.some((marker) => statusText.includes(marker))) return t.halfTime;

  const meaningful = values.find((value) => !["live", "true", "false"].includes(String(value).trim().toLowerCase()));
  return meaningful ? String(meaningful).trim() : t.liveNow;
}

export function getHeroStatusLine(match, heroMode, lang, t, now) {
  if (heroMode === "upcoming") {
    const kickoffTime = getKickoffTime(match);
    return {
      label: t.kickoffIn,
      value: formatCountdown(Number.isFinite(kickoffTime) ? kickoffTime - now : 0, lang),
      isCountdown: true,
    };
  }

  if (heroMode === "live") {
    return { label: "", value: getLiveDisplayBadge(match, lang, t), isCountdown: false };
  }

  return { label: "", value: t.matchFinished, isCountdown: false };
}

export function getMatchStatus(match, lang, t) {
  const normalizedStatus = normalizeMatchStatus(match);

  if (normalizedStatus === "live") {
    return { key: "live", label: getLiveDisplayBadge(match, lang, t) };
  }

  if (normalizedStatus === "finished") {
    return { key: "finished", label: t.statusFinished };
  }

  if (normalizedStatus === "pending_result") {
    return { key: "pending_result", label: t.scorePending };
  }

  if (normalizedStatus === "upcoming") {
    return { key: "upcoming", label: t.statusUpcoming };
  }

  return { key: "upcoming", label: t.statusUpcoming };
}


export function toPersianDigits(value) {
  const digits = "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9";
  return String(value ?? "").replace(/\d/g, (digit) => digits[Number(digit)]);
}

export function getPenaltySummary(match, lang) {
  if (isLivePenaltyShootout(match)) {
    const homeName = getLocalizedTeamName(match, "home", lang) || match?.home_team_label || (lang === "fa" ? "میزبان" : "Home");
    const awayName = getLocalizedTeamName(match, "away", lang) || match?.away_team_label || (lang === "fa" ? "مهمان" : "Away");
    const homePenalty = lang === "fa" ? toPersianDigits(match.home_penalty_score) : match.home_penalty_score;
    const awayPenalty = lang === "fa" ? toPersianDigits(match.away_penalty_score) : match.away_penalty_score;

    return lang === "fa"
      ? `ضربات پنالتی در جریان: ${homeName} ${homePenalty} - ${awayPenalty} ${awayName}`
      : `Penalty shootout in progress: ${homeName} ${homePenalty} - ${awayPenalty} ${awayName}`;
  }

  const providedSummary = lang === "fa" ? match?.penalty_summary_fa : match?.penalty_summary_en;
  if (providedSummary) return providedSummary;

  const hasShootout = match?.win_method === "penalty_shootout" ||
    (match?.home_penalty_score != null && match?.away_penalty_score != null);
  if (!hasShootout) return "";

  const winnerSide = match.penalty_winner_side;
  const winnerName = lang === "fa"
    ? match.penalty_winner_fa || getLocalizedTeamName(match, winnerSide, "fa")
    : match.penalty_winner_en || getLocalizedTeamName(match, winnerSide, "en");

  if (!winnerName) return lang === "fa" ? "پیروزی در ضربات پنالتی" : "Won on penalties";
  if (lang === "en") return `${winnerName} won on penalties`;

  const winnerScore = winnerSide === "home" ? match.home_penalty_score : match.away_penalty_score;
  const loserScore = winnerSide === "home" ? match.away_penalty_score : match.home_penalty_score;
  const scoreText = winnerScore != null && loserScore != null
    ? ` ${toPersianDigits(winnerScore)} - ${toPersianDigits(loserScore)}`
    : "";
  return `${winnerName} در ضربات پنالتی${scoreText} پیروز شد`;
}

export function normalizeMatchPayload(match) {
  const shootout = match?.penalty_shootout || match?.penalty || {};

  return {
    ...match,
    home_penalty_score: match?.home_penalty_score ?? shootout.home_penalty_score ?? shootout.home_score,
    away_penalty_score: match?.away_penalty_score ?? shootout.away_penalty_score ?? shootout.away_score,
    penalty_winner_side: match?.penalty_winner_side ?? shootout.winner_side,
    penalty_winner_fa: match?.penalty_winner_fa ?? shootout.winner_fa,
    penalty_winner_en: match?.penalty_winner_en ?? shootout.winner_en,
    penalty_summary_fa: match?.penalty_summary_fa ?? shootout.summary_fa,
    penalty_summary_en: match?.penalty_summary_en ?? shootout.summary_en,
    win_method: match?.win_method ?? shootout.win_method,
  };
}
