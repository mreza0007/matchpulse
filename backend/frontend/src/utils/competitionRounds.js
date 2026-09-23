import { getKickoffTime } from "./dates.js";
import {
  isFinishedMatch,
  isLiveMatch,
  isPostponedMatch,
} from "./matches.js";

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";
const roundNumberFormatters = new Map();

const STAGE_LABELS = [
  {
    key: "league_phase",
    patterns: [/^league phase$/i, /^league stage$/i, /^مرحله لیگ$/u, /^فاز لیگ$/u],
    fa: "مرحله لیگ",
    en: "League Phase",
  },
  {
    key: "group_stage",
    patterns: [/^group stage$/i, /^groups?$/i, /^مرحله گروهی$/u],
    fa: "مرحله گروهی",
    en: "Group Stage",
  },
  {
    key: "qualifying",
    patterns: [/^qualif(?:ying|iers?)$/i, /^preliminary$/i, /^مقدماتی$/u],
    fa: "مقدماتی",
    en: "Qualifying",
  },
  {
    key: "round_of_16",
    patterns: [/^round of 16$/i, /^last 16$/i, /^1\/8 finals?$/i, /^یک هشتم نهایی$/u, /^1\/8 نهایی$/u],
    fa: "یک‌هشتم نهایی",
    en: "Round of 16",
  },
  {
    key: "quarter_finals",
    patterns: [/^quarter[ -]?finals?$/i, /^1\/4 finals?$/i, /^یک چهارم نهایی$/u, /^1\/4 نهایی$/u],
    fa: "یک‌چهارم نهایی",
    en: "Quarter-finals",
  },
  {
    key: "semi_finals",
    patterns: [/^semi[ -]?finals?$/i, /^نیمه نهایی$/u],
    fa: "نیمه‌نهایی",
    en: "Semi-finals",
  },
  {
    key: "final",
    patterns: [/^final$/i, /^فینال$/u, /^نهایی$/u],
    fa: "فینال",
    en: "Final",
  },
];

function normalizeDigits(value) {
  return String(value ?? "")
    .replace(/[۰-۹]/g, (digit) => String(PERSIAN_DIGITS.indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String(ARABIC_DIGITS.indexOf(digit)));
}

function normalizedText(value) {
  return normalizeDigits(value)
    .trim()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ");
}

function slug(value) {
  return normalizedText(value)
    .toLowerCase()
    .replace(/[^a-z0-9\u0600-\u06ff]+/gu, "-")
    .replace(/^-|-$/g, "") || "unknown";
}

function localNumber(value, lang) {
  const locale = lang === "fa" ? "fa-IR" : "en-US";
  if (!roundNumberFormatters.has(locale)) {
    roundNumberFormatters.set(locale, new Intl.NumberFormat(locale, { useGrouping: false }));
  }
  return roundNumberFormatters.get(locale).format(value);
}

function firstRoundValue(match) {
  return [
    match?.round,
    match?.round_number,
    match?.roundNumber,
    match?.week,
    match?.matchweek,
    match?.stage_label,
    match?.stage,
    match?.stage_name,
    match?.phase,
  ].find((value) => value !== undefined && value !== null && String(value).trim() !== "");
}

export function normalizeCompetitionRound(match, { league = false } = {}) {
  const rawValue = firstRoundValue(match);
  if (rawValue === undefined) return null;

  const text = normalizedText(rawValue);
  const stage = STAGE_LABELS.find(({ patterns }) => patterns.some((pattern) => pattern.test(text)));
  if (stage) {
    return {
      roundKey: `stage:${stage.key}`,
      roundNumber: null,
      roundLabelFa: stage.fa,
      roundLabelEn: stage.en,
      stageKey: stage.key,
      stageLabelFa: stage.fa,
      stageLabelEn: stage.en,
      roundType: "stage",
      rawValue,
    };
  }

  const numericMatch = text.match(/^(?:(?:round|week|matchweek|mw|هفته)\s*)?(\d+)$/iu);
  if (numericMatch) {
    const roundNumber = Number(numericMatch[1]);
    if (Number.isSafeInteger(roundNumber) && roundNumber >= 0) {
      return {
        roundKey: `round:${roundNumber}`,
        roundNumber,
        roundLabelFa: `${league ? "هفته" : "دور"} ${localNumber(roundNumber, "fa")}`,
        roundLabelEn: `${league ? "MW" : "Round"} ${localNumber(roundNumber, "en")}`,
        stageKey: null,
        stageLabelFa: "",
        stageLabelEn: "",
        roundType: "round",
        rawValue,
      };
    }
  }

  return {
    roundKey: `stage:${slug(text)}`,
    roundNumber: null,
    roundLabelFa: text,
    roundLabelEn: text,
    stageKey: slug(text),
    stageLabelFa: text,
    stageLabelEn: text,
    roundType: "stage",
    rawValue,
  };
}

function scopeStart(matches) {
  const kickoffs = matches.map(getKickoffTime).filter(Number.isFinite);
  return kickoffs.length > 0 ? Math.min(...kickoffs) : Number.POSITIVE_INFINITY;
}

export function buildCompetitionMatchScopes(matches, competition) {
  const safeMatches = Array.isArray(matches) ? matches : [];
  const isLeague = competition?.format === "league" && competition?.supports_standings === true;
  const entries = safeMatches.map((match) => ({
    match,
    round: normalizeCompetitionRound(match, { league: isLeague }),
  }));

  if (entries.length === 0 || entries.some(({ round }) => !round)) {
    return { mode: "fallback", scopes: [] };
  }

  const scopesByKey = new Map();
  entries.forEach(({ match, round }, index) => {
    if (!scopesByKey.has(round.roundKey)) {
      scopesByKey.set(round.roundKey, {
        ...round,
        key: round.roundKey,
        matches: [],
        sourceIndex: index,
      });
    }
    scopesByKey.get(round.roundKey).matches.push(match);
  });

  const scopes = [...scopesByKey.values()];
  if (isLeague) {
    if (!scopes.every((scope) => scope.roundType === "round")) {
      return { mode: "fallback", scopes: [] };
    }
    scopes.sort((left, right) => left.roundNumber - right.roundNumber);
    return { mode: "round", scopes };
  }

  scopes.sort((left, right) => {
    const kickoffDifference = scopeStart(left.matches) - scopeStart(right.matches);
    return Number.isFinite(kickoffDifference) && kickoffDifference !== 0
      ? kickoffDifference
      : left.sourceIndex - right.sourceIndex;
  });
  return { mode: "stage", scopes };
}

function playableUnfinished(match) {
  return !isFinishedMatch(match) && !isPostponedMatch(match);
}

export function selectRelevantRound(scopes, now = Date.now()) {
  if (!Array.isArray(scopes) || scopes.length === 0) {
    return { scopeKey: "", reason: "none" };
  }

  const liveScope = scopes.find((scope) => scope.matches.some(isLiveMatch));
  if (liveScope) return { scopeKey: liveScope.key, reason: "live" };

  const activeScopes = scopes.filter((scope) => {
    const hasBegun = scope.matches.some((match) => {
      const kickoff = getKickoffTime(match);
      return isFinishedMatch(match) || (Number.isFinite(kickoff) && kickoff <= now);
    });
    return hasBegun && scope.matches.some(playableUnfinished);
  });
  if (activeScopes.length > 0) {
    const rankedActiveScopes = activeScopes
      .map((scope, index) => {
        const playableKickoffs = scope.matches
          .filter(playableUnfinished)
          .map(getKickoffTime)
          .filter(Number.isFinite);
        return {
          scope,
          index,
          hasOverdueUnfinished: playableKickoffs.some((kickoff) => kickoff <= now),
          nextKickoff: playableKickoffs
            .filter((kickoff) => kickoff > now)
            .sort((left, right) => left - right)[0] ?? Number.POSITIVE_INFINITY,
        };
      })
      .sort((left, right) => (
        Number(right.hasOverdueUnfinished) - Number(left.hasOverdueUnfinished)
        || left.nextKickoff - right.nextKickoff
        || left.index - right.index
      ));
    return { scopeKey: rankedActiveScopes[0].scope.key, reason: "active" };
  }

  const futureScopes = scopes
    .map((scope) => ({
      scope,
      kickoff: scope.matches
        .filter(playableUnfinished)
        .map(getKickoffTime)
        .filter((kickoff) => Number.isFinite(kickoff) && kickoff > now)
        .sort((left, right) => left - right)[0],
    }))
    .filter(({ kickoff }) => Number.isFinite(kickoff))
    .sort((left, right) => left.kickoff - right.kickoff);
  if (futureScopes.length > 0) {
    return { scopeKey: futureScopes[0].scope.key, reason: "upcoming" };
  }

  const unknownUpcoming = scopes.find((scope) => scope.matches.some(playableUnfinished));
  if (unknownUpcoming) return { scopeKey: unknownUpcoming.key, reason: "upcoming_unknown" };

  return { scopeKey: scopes.at(-1).key, reason: "completed" };
}

export function scopeLabel(scope, lang) {
  return lang === "fa" ? scope?.roundLabelFa : scope?.roundLabelEn;
}
