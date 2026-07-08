import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_URL;

const TEAM_FLAG_OVERRIDES = {
  England: "gb-eng",
  Scotland: "gb-sct",
  Wales: "gb-wls",
  "Northern Ireland": "gb-nir",
  "United States": "us",
  USA: "us",
  "Korea Republic": "kr",
  "South Korea": "kr",
  "Côte d'Ivoire": "ci",
  "Ivory Coast": "ci",
};

function getCountryCodeFromFlagEmoji(flagEmoji) {
  if (!flagEmoji || typeof flagEmoji !== "string") return "";

  const codePoints = Array.from(flagEmoji.trim());
  if (codePoints.length < 2) return "";

  const letters = codePoints
    .slice(0, 2)
    .map((char) => char.codePointAt(0) - 127397);

  if (letters.some((letter) => letter < 65 || letter > 90)) return "";

  return letters.map((letter) => String.fromCharCode(letter).toLowerCase()).join("");
}

function getFlagImageUrl(flagEmoji, teamName) {
  const code = TEAM_FLAG_OVERRIDES[teamName] || getCountryCodeFromFlagEmoji(flagEmoji);
  return code ? `https://flagcdn.com/w80/${code}.png` : "";
}

function TeamFlag({ flagEmoji, teamName }) {
  const imageUrl = getFlagImageUrl(flagEmoji, teamName);
  const [failedImageUrl, setFailedImageUrl] = useState("");
  const hasError = failedImageUrl === imageUrl;

  return (
    <span className="team-flag" aria-hidden="true">
      {imageUrl && !hasError ? (
        <img
          className="team-flag-img"
          src={imageUrl}
          alt=""
          loading="lazy"
          onError={() => setFailedImageUrl(imageUrl)}
        />
      ) : (
        <span className="team-flag-fallback">{flagEmoji || "⚽"}</span>
      )}
    </span>
  );
}

function BrandLogo() {
  const [hasError, setHasError] = useState(false);

  return (
    <div className="brand-logo" aria-label="World Cup 2026">
      {!hasError ? (
        <img
          className="brand-logo-img"
          src="/world-cup-2026-logo.webp"
          alt="World Cup 2026"
          onError={() => setHasError(true)}
        />
      ) : (
        <span className="brand-logo-fallback">WC 2026</span>
      )}
    </div>
  );
}

function getScoreValue(match, keys) {
  for (const key of keys) {
    const value = match?.[key];

    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }

  return null;
}

function getMatchScore(match) {
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

function getMatchScoreSignature(match) {
  return `${getScoreValue(match, ["home_score", "homeScore"])}:${getScoreValue(match, [
    "away_score",
    "awayScore",
  ])}`;
}

function matchesAreEqual(currentMatch, nextMatch) {
  return JSON.stringify(currentMatch) === JSON.stringify(nextMatch);
}

function getLocalizedTeamName(match, side, lang) {
  const localizedKey = `${side}_${lang}`;
  const englishKey = `${side}_en`;

  return match?.[localizedKey] || match?.[englishKey] || "";
}

function normalizeTeamKey(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, "");
}

function normalizeMatchStatus(match) {
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

function isFinishedMatch(match) {
  return normalizeMatchStatus(match) === "finished" || match?.is_finished === true;
}

function isPendingResultMatch(match) {
  return normalizeMatchStatus(match) === "pending_result";
}

function isResultTabMatch(match) {
  return isFinishedMatch(match) || isPendingResultMatch(match);
}

function isLiveMatch(match) {
  return normalizeMatchStatus(match) === "live" || match?.is_live === true;
}

function isPastPendingResult(match) {
  if (!isPendingResultMatch(match)) return false;
  const kickoff = getKickoffTime(match);
  return Number.isFinite(kickoff) && kickoff <= Date.now();
}

function canShowEvents(match) {
  if (!match?.id) return false;
  if (match.can_show_event_button === true) return true;
  return isFinishedMatch(match) || isLiveMatch(match) || isPastPendingResult(match);
}

function isFutureMatchStatus(match) {
  if (match?.is_upcoming) return true;

  const status = String(match?.status || "").toLowerCase().replace(/[-\s]/g, "_");
  return ["scheduled", "upcoming", "notstarted", "not_started"].includes(status);
}

function isPredictionLocked(match) {
  if (isLiveMatch(match) || isFinishedMatch(match) || isPendingResultMatch(match)) return true;
  if (!isFutureMatchStatus(match)) return true;
  const kickoffTime = getKickoffTime(match);
  return !Number.isFinite(kickoffTime) || kickoffTime <= Date.now();
}

function getPredictionLabel(match, prediction, lang, t) {
  if (prediction === "draw") return t.predictionDraw;
  const side = prediction === "home" ? "home" : "away";
  return t.predictionWin.replace("{team}", getLocalizedTeamName(match, side, lang));
}

function parseKickoffDate(match) {
  const kickoffValue = match?.kickoff_iso || match?.kickoff_utc || match?.kickoff;

  if (!kickoffValue || typeof kickoffValue !== "string") return null;
  if (!/^\d{4}-\d{2}-\d{2}T/.test(kickoffValue)) return null;

  const isoValue = kickoffValue.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(kickoffValue)
    ? kickoffValue
    : `${kickoffValue}Z`;
  const date = new Date(isoValue);

  return Number.isNaN(date.getTime()) ? null : date;
}

function getKickoffTime(match) {
  const kickoffTs = Number(match?.kickoff_ts ?? match?.kickoff_timestamp);

  if (Number.isFinite(kickoffTs)) {
    return kickoffTs * 1000;
  }

  return parseKickoffDate(match)?.getTime() ?? Number.POSITIVE_INFINITY;
}

function getMatchDateKey(match) {
  if (match?.date_key) return match.date_key;

  const kickoffDate = parseKickoffDate(match);
  if (!kickoffDate) return "";

  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(kickoffDate);
}

function formatTehranMatchDateTime(match, lang) {
  const kickoffDate = parseKickoffDate(match);

  if (!kickoffDate) {
    return {
      date: match?.date_iran || "",
      time: match?.time_iran || "",
      compact: [match?.date_iran, match?.time_iran].filter(Boolean).join(" - "),
    };
  }

  const locale = lang === "fa" ? "fa-IR-u-ca-persian" : "en-US";
  const date = new Intl.DateTimeFormat(locale, {
    timeZone: "Asia/Tehran",
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(kickoffDate);
  const time = new Intl.DateTimeFormat(locale, {
    timeZone: "Asia/Tehran",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(kickoffDate);

  return {
    date,
    time,
    compact: `${date} - ${time}`,
  };
}

function getGroupLabel(match, lang) {
  if (lang === "fa") {
    return [match.weekday_fa, match.date_label_fa || match.date_iran].filter(Boolean).join(" - ");
  }

  return formatTehranMatchDateTime(match, lang).date;
}

function groupMatchesByDate(matches, lang) {
  const groups = [];

  matches.forEach((match) => {
    const dateKey = getMatchDateKey(match) || `unknown-${groups.length}`;
    const currentGroup = groups[groups.length - 1];

    if (currentGroup?.dateKey === dateKey) {
      currentGroup.matches.push(match);
      return;
    }

    groups.push({
      dateKey,
      label: getGroupLabel(match, lang),
      match,
      matches: [match],
    });
  });

  return groups;
}

function getHeroMatch(liveMatches, upcomingMatches, resultMatches) {
  return liveMatches[0] || upcomingMatches[0] || resultMatches[0] || null;
}

function getHeroMode(match) {
  if (!match) return "empty";
  if (isLiveMatch(match)) return "live";
  if (isFutureMatchStatus(match)) return "upcoming";
  return "result";
}

function filterHeroFromList(matches, heroMatch) {
  if (!heroMatch?.id) return matches;
  return matches.filter((match) => String(match.id) !== String(heroMatch.id));
}

function localizeCountdownDigits(value, lang) {
  if (lang !== "fa") return value;
  return value.replace(/\d/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

function formatCountdown(milliseconds, lang) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const twoDigits = (value) => String(value).padStart(2, "0");

  if (days > 0) {
    const dayCountdown = lang === "fa"
      ? `${days} روز و ${twoDigits(hours)}:${twoDigits(minutes)}`
      : `${days}d ${twoDigits(hours)}:${twoDigits(minutes)}`;
    return localizeCountdownDigits(dayCountdown, lang);
  }

  return localizeCountdownDigits(
    `${twoDigits(hours)}:${twoDigits(minutes)}:${twoDigits(seconds)}`,
    lang,
  );
}

function hasPenaltyScores(match) {
  return match?.home_penalty_score != null && match?.away_penalty_score != null;
}

function getPenaltyShootoutLabel(lang) {
  return lang === "fa" ? "ضربات پنالتی" : "Penalty shootout";
}

function isLivePenaltyShootout(match) {
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

function getLiveDisplayBadge(match, lang, t) {
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

function getHeroStatusLine(match, heroMode, lang, t, now) {
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

function getMatchStatus(match, lang, t) {
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

const translations = {
  fa: {
    dir: "rtl",
    langButton: "English",
    worldCup: "جام جهانی ۲۰۲۶",
    title: "MatchPulse",
    brandLabel: "همراه جام جهانی",
    subtitle: "برنامه هوشمند بازی‌های جام جهانی؛ دنبال‌کردن مسابقه‌ها، تیم‌های محبوب و یادآورها در یک‌جا.",
    nextMatch: "بازی بعدی",
    nextMatchesTitle: "بازی‌های بعدی",
    nextMatches: "بازی‌های پیش‌رو",
    liveMatches: "بازی‌های در جریان",
    heroLive: "بازی در جریان",
    heroUpcoming: "بازی بعدی",
    heroResult: "آخرین نتیجه",
    otherLiveMatches: "سایر بازی‌های در جریان",
    homeNextMatches: "بازی‌های بعدی",
    latestResults: "آخرین نتایج",
    kickoffIn: "شروع بازی تا",
    liveNow: "در جریان",
    halfTime: "بین دو نیمه",
    matchFinished: "بازی به پایان رسید",
    pastMatches: "نتایج",
    latestNews: "آخرین اخبار",
    favorites: "تیم‌های محبوب",
    chooseFavorite: "تیم محبوبت را انتخاب کن",
    favoriteTeams: "تیم‌های محبوب",
    addedFavorite: "به تیم‌های محبوب اضافه شد",
    removedFavorite: "از تیم‌های محبوب حذف شد",
    addedReminder: "یادآور مسابقه ذخیره شد",
    removedReminder: "یادآور مسابقه حذف شد",
    prediction: "پیش‌بینی",
    predictionWin: "برد {team}",
    predictionDraw: "مساوی",
    predictionSaved: "پیش‌بینی ثبت شد",
    yourPrediction: "پیش‌بینی شما",
    predictionSaveFailed: "ثبت پیش‌بینی ناموفق بود",
    predictionLocked: "پیش‌بینی قفل شد",
    predictionPoints: "امتیاز پیش‌بینی",
    predictionCorrect: "درست",
    predictionWrong: "نادرست",
    predictionPending: "در انتظار",
    activeReminders: "یادآورهای فعال",
    profileTitle: "پروفایل من",
    profileText: "اطلاعات تلگرام، تیم‌های محبوب و یادآورهای فعال تو اینجا نمایش داده می‌شود.",
    telegramUser: "کاربر تلگرام",
    telegramId: "شناسه تلگرام",
    username: "نام کاربری",
    language: "زبان",
    noUsername: "بدون نام کاربری",
    saved: "کاربر در بک‌اند ذخیره شد",
    notSaved: "هنوز در بک‌اند ذخیره نشده",
    loadingMatches: "در حال دریافت بازی‌ها...",
    loadingNews: "در حال دریافت اخبار...",
    loadingTeams: "در حال دریافت تیم‌ها...",
    remind: "یادآوری ۱ ساعت قبل",
    cancelReminder: "حذف یادآور",
    addFavorite: "محبوب کن",
    removeFavorite: "حذف محبوب",
    noFavorites: "هنوز تیم محبوبی انتخاب نکردی",
    noReminders: "هنوز یادآور فعالی ثبت نشده.",
    noLiveMatches: "فعلاً بازی زنده‌ای در جریان نیست",
    noUpcomingMatches: "فعلاً بازی پیش‌رویی پیدا نشد",
    noPastMatches: "هنوز نتیجه‌ای ثبت نشده است",
    noNews: "فعلاً خبری برای نمایش نیست",
    matchesError: "دریافت بازی‌ها ناموفق بود. دوباره تلاش کن.",
    unavailable: "نامشخص",
    home: "خانه",
    live: "زنده",
    upcoming: "بازی‌های پیش‌رو",
    past: "نتایج",
    bracket: "نمودار بازی‌ها",
    bracketTitle: "مسیر قهرمانی",
    bracketSubtitle: "مسیر مرحله حذفی جام جهانی؛ از یک‌شانزدهم نهایی تا فینال",
    bracketSwipeHint: "برای دیدن کامل نمودار، به چپ و راست بکشید",
    zoomIn: "بزرگ‌نمایی",
    zoomOut: "کوچک‌نمایی",
    resetZoom: "بازنشانی",
    roundOf32: "یک‌شانزدهم نهایی",
    roundOf16: "یک‌هشتم نهایی",
    quarterfinals: "یک‌چهارم نهایی",
    semifinals: "نیمه‌نهایی",
    final: "فینال",
    thirdPlace: "رده‌بندی",
    news: "اخبار",
    profile: "پروفایل",
    vs: "مقابل",
    group: "گروه",
    stage: "مرحله",
    city: "شهر",
    stadium: "ورزشگاه",
    statusLive: "زنده",
    statusFinished: "تمام‌شده",
    statusUpcoming: "پیش‌رو",
    scorePending: "نتیجه هنوز ثبت نشده",
    matchEvents: "رویدادها",
    loadingEvents: "در حال دریافت رویدادها...",
    noEvents: "رویدادی برای این بازی ثبت نشده است.",
    eventSourceUnavailable: "رویدادها فعلاً از منبع داده دریافت نشدند.",
    eventRequestFailed: "دریافت رویدادها ناموفق بود.",
    viewEvents: "مشاهده رویدادها",
    assistLabel: "پاس گل",
    playerInLabel: "",
    playerOutLabel: "",
    viewAll: "مشاهده همه",
    teams: "تیم",
    matches: "بازی",
    cities: "شهر",
  },
  en: {
    dir: "ltr",
    langButton: "فارسی",
    worldCup: "World Cup 2026",
    title: "MatchPulse",
    brandLabel: "World Cup Companion",
    subtitle: "Your World Cup companion for fixtures, favorite teams, and match reminders.",
    nextMatch: "Next Match",
    nextMatchesTitle: "Next Matches",
    nextMatches: "Upcoming Matches",
    liveMatches: "Live Matches",
    heroLive: "Live Now",
    heroUpcoming: "Next Match",
    heroResult: "Latest Result",
    otherLiveMatches: "Other Live Matches",
    homeNextMatches: "Next Matches",
    latestResults: "Latest Results",
    kickoffIn: "Kickoff in",
    liveNow: "Live now",
    halfTime: "HT",
    matchFinished: "Match finished",
    pastMatches: "Results",
    latestNews: "Latest News",
    favorites: "Favorite Teams",
    chooseFavorite: "Choose your favorite team",
    favoriteTeams: "Favorite Teams",
    addedFavorite: "Added to favorite teams",
    removedFavorite: "Removed from favorite teams",
    addedReminder: "Match reminder saved",
    removedReminder: "Match reminder removed",
    prediction: "Prediction",
    predictionWin: "{team} win",
    predictionDraw: "Draw",
    predictionSaved: "Prediction saved",
    yourPrediction: "Your prediction",
    predictionSaveFailed: "Prediction could not be saved",
    predictionLocked: "Prediction locked",
    predictionPoints: "Prediction points",
    predictionCorrect: "Correct",
    predictionWrong: "Wrong",
    predictionPending: "Pending",
    activeReminders: "Active Reminders",
    profileTitle: "My Profile",
    profileText: "Your Telegram info, favorite teams, and active match reminders live here.",
    telegramUser: "Telegram User",
    telegramId: "Telegram ID",
    username: "Username",
    language: "Language",
    noUsername: "No username",
    saved: "User saved in backend",
    notSaved: "Not saved in backend yet",
    loadingMatches: "Loading matches...",
    loadingNews: "Loading news...",
    loadingTeams: "Loading teams...",
    remind: "Remind me 1 hour before",
    cancelReminder: "Remove reminder",
    addFavorite: "Favorite",
    removeFavorite: "Remove favorite",
    noFavorites: "No favorite teams selected yet.",
    noReminders: "No active reminders saved yet.",
    noLiveMatches: "No live matches are currently in progress.",
    noUpcomingMatches: "No future matches were found.",
    noPastMatches: "No results are available yet.",
    noNews: "No news to show yet.",
    matchesError: "Could not load matches. Please try again.",
    unavailable: "Unavailable",
    home: "Home",
    live: "Live",
    upcoming: "Upcoming",
    past: "Results",
    bracket: "Bracket",
    bracketTitle: "Road to the Trophy",
    bracketSubtitle: "The World Cup knockout path, from the round of 32 to the final.",
    bracketSwipeHint: "Swipe horizontally to view the full bracket",
    zoomIn: "Zoom in",
    zoomOut: "Zoom out",
    resetZoom: "Reset",
    roundOf32: "Round of 32",
    roundOf16: "Round of 16",
    quarterfinals: "Quarterfinals",
    semifinals: "Semifinals",
    final: "Final",
    thirdPlace: "Third place",
    news: "News",
    profile: "Profile",
    vs: "vs",
    group: "Group",
    stage: "Stage",
    city: "City",
    stadium: "Stadium",
    statusLive: "LIVE",
    statusFinished: "Finished",
    statusUpcoming: "Upcoming",
    scorePending: "Score not recorded yet",
    matchEvents: "Events",
    loadingEvents: "Loading timeline...",
    noEvents: "No events recorded for this match.",
    eventSourceUnavailable: "Events are temporarily unavailable from the data source.",
    eventRequestFailed: "Failed to load events.",
    viewEvents: "View events",
    assistLabel: "Assist",
    playerInLabel: "",
    playerOutLabel: "",
    viewAll: "View all",
    teams: "Teams",
    matches: "Matches",
    cities: "Cities",
  },
};

const EVENT_LABELS = {
  fa: {
    goal: "\u06af\u0644",
    penalty_goal: "\u06af\u0644 \u067e\u0646\u0627\u0644\u062a\u06cc",
    penalty_event: "\u0631\u0648\u06cc\u062f\u0627\u062f \u067e\u0646\u0627\u0644\u062a\u06cc",
    own_goal: "\u06af\u0644 \u0628\u0647 \u062e\u0648\u062f\u06cc",
    var_disallowed_goal: "\u06af\u0644 \u0645\u0631\u062f\u0648\u062f \u0628\u0627 VAR",
    disallowed_goal: "\u06af\u0644 \u0645\u0631\u062f\u0648\u062f \u0628\u0627 VAR",
    penalty_missed: "\u067e\u0646\u0627\u0644\u062a\u06cc \u062e\u0631\u0627\u0628\u200c\u0634\u062f\u0647",
    missed_penalty: "\u067e\u0646\u0627\u0644\u062a\u06cc \u062e\u0631\u0627\u0628\u200c\u0634\u062f\u0647",
    assist: "\u067e\u0627\u0633 \u06af\u0644",
    yellow_card: "\u06a9\u0627\u0631\u062a \u0632\u0631\u062f",
    red_card: "\u06a9\u0627\u0631\u062a \u0642\u0631\u0645\u0632",
    substitution: "\u062a\u0639\u0648\u06cc\u0636",
    var: "VAR",
    unknown: "\u0631\u0648\u06cc\u062f\u0627\u062f",
  },
  en: {
    goal: "Goal",
    penalty_goal: "Penalty goal",
    penalty_event: "Penalty event",
    own_goal: "Own goal",
    var_disallowed_goal: "VAR-disallowed goal",
    disallowed_goal: "VAR-disallowed goal",
    penalty_missed: "Missed penalty",
    missed_penalty: "Missed penalty",
    assist: "Assist",
    yellow_card: "Yellow card",
    red_card: "Red card",
    substitution: "Substitution",
    var: "VAR",
    unknown: "Event",
  },
};

function getEventTypeLabel(type, lang) {
  return EVENT_LABELS[lang]?.[type] || EVENT_LABELS[lang]?.unknown || "Event";
}

function getEventIcon(type) {
  if (type === "goal") return "⚽";
  if (type === "yellow_card") return "🟨";
  if (type === "red_card") return "🟥";
  if (type === "substitution") return "🔁";
  return "•";
}

function getLegacyEventIcon(type) {
  if (type === "goal") return "⚽";
  if (type === "yellow_card") return "🟨";
  if (type === "red_card") return "🟥";
  if (type === "substitution") return "🔁";
  return "•";
}

void getEventIcon;
void getLegacyEventIcon;

function getFirstEventValue(event, keys) {
  for (const key of keys) {
    const value = event?.[key];

    if (value !== undefined && value !== null && value !== "") return value;
  }

  return "";
}

function normalizeEventSide(event) {
  const side = String(
    getFirstEventValue(event, ["team_side", "side", "home_or_away", "team"]) || "",
  )
    .toLowerCase()
    .replace(/[-\s]/g, "_");

  if (["home", "host", "home_team"].includes(side)) return "home";
  if (["away", "guest", "away_team"].includes(side)) return "away";
  return "";
}

function resolveEventTeam(event, match, lang) {
  const side = normalizeEventSide(event);

  if (side === "home") {
    return {
      flag: match.home_flag,
      name: getLocalizedTeamName(match, "home", lang),
      englishName: match.home_en,
    };
  }

  if (side === "away") {
    return {
      flag: match.away_flag,
      name: getLocalizedTeamName(match, "away", lang),
      englishName: match.away_en,
    };
  }

  const teamName = getFirstEventValue(event, ["team_name", "teamName"]);
  const blockedNames = new Set(["home", "away", "host", "guest", "میزبان", "مهمان"]);

  return {
    flag: "",
    name: blockedNames.has(String(teamName).toLowerCase()) ? "" : teamName,
    englishName: teamName,
  };
}

function getEventPlayer(event) {
  return getFirstEventValue(event, [
    "player",
    "player_name",
    "playerName",
    "scorer",
    "goal_scorer",
  ]);
}

function getNormalizedEventType(event) {
  return String(event?.normalized_type || event?.event_type || event?.type || "unknown").toLowerCase();
}

function getRenderedEventIcon(type) {
  return {
    goal: "\u26bd",
    penalty_goal: "\u26bd",
    own_goal: "\u26bd\u21a9\ufe0f",
    var_disallowed_goal: "\ud83d\udcf9",
    disallowed_goal: "\ud83d\udcf9",
    penalty_event: "\u26aa",
    penalty_missed: "\u274c",
    missed_penalty: "\u274c",
    yellow_card: "\ud83d\udfe8",
    red_card: "\ud83d\udfe5",
    substitution: "\ud83d\udd01",
    var: "\ud83c\udfa5",
  }[type] || "\u2022";
}

function EventRow({ event, match, lang, t, index }) {
  const type = getNormalizedEventType(event);
  const team = resolveEventTeam(event, match, lang);
  const player = getEventPlayer(event);
  const eventMinute = event.display_minute || event.raw_minute || event.minute || "";
  const assist = getFirstEventValue(event, ["assist", "assist_name", "assistName"]);
  const playerIn = getFirstEventValue(event, ["player_in", "playerIn", "in_player"]);
  const playerOut = getFirstEventValue(event, ["player_out", "playerOut", "out_player"]);
  const providedLabel = lang === "fa" ? event.label_fa : event.label_en;
  const title = providedLabel || getEventTypeLabel(type, lang);
  const eventIcon = event.icon || getRenderedEventIcon(type);
  const key = [eventMinute, type, player, playerIn, playerOut, index].join("-");

  return (
    <li className={`event-row ${type}`} key={key}>
      <span className="event-minute">{eventMinute}'</span>
      <span className="event-icon" aria-hidden="true">
        {eventIcon}
      </span>
      <div className="event-body">
        <strong>{title}</strong>
        {type === "substitution" ? (
          <div className="event-lines">
            {playerIn && <span>{"\ud83d\udfe2\u2b06\ufe0f "}{playerIn}</span>}
            {playerOut && <span>{"\ud83d\udd34\u2b07\ufe0f "}{playerOut}</span>}
          </div>
        ) : (
          player && <span className="event-player">{player}</span>
        )}
        {type === "goal" && assist && (
          <span className="event-assist">{"\ud83d\udc5f "}{t.assistLabel}: {assist}</span>
        )}
        {(team.name || team.flag) && (
          <small className="event-team">
            <TeamFlag flagEmoji={team.flag} teamName={team.englishName} />
            {team.name}
          </small>
        )}
      </div>
    </li>
  );
}

function toPersianDigits(value) {
  const digits = "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9";
  return String(value ?? "").replace(/\d/g, (digit) => digits[Number(digit)]);
}

function getPenaltySummary(match, lang) {
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

function normalizeMatchPayload(match) {
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

function PenaltySummary({ match, lang, compact = false }) {
  const summary = getPenaltySummary(match, lang);
  if (!summary) return null;

  return (
    <div className={compact ? "bracket-penalty-summary" : "penalty-summary"}>
      {summary}
    </div>
  );
}

function MatchCard({
  match,
  t,
  showReminder = true,
  onReminderToggle,
  isReminderActive = false,
  homeTeam,
  awayTeam,
  favoriteTeamIds,
  favoriteTeamKeys,
  onFavoriteToggle,
  lang,
  onDetailsClick,
  isExpanded = false,
  events = [],
  isLoadingEvents = false,
  eventsUnavailable = false,
  eventsFailed = false,
  isScoreChanged = false,
  variant = "standard",
  prediction = "",
  onPredictionSelect,
  isPredictionSaving = false,
  predictionWasSaved = false,
  predictionSaveFailed = false,
  predictionForceLocked = false,
}) {
  const matchStatus = getMatchStatus(match, lang, t);
  const isLive = isLiveMatch(match);
  const matchScoreValue = getMatchScore(match);
  const matchScore =
    matchStatus.key === "upcoming" || matchStatus.key === "pending_result"
      ? ""
      : matchScoreValue || (matchStatus.key === "live" ? "0 - 0" : "");
  const homeName = getLocalizedTeamName(match, "home", lang);
  const awayName = getLocalizedTeamName(match, "away", lang);
  const shouldShowScoreFallback = !matchScore && ["finished", "pending_result"].includes(matchStatus.key);
  const matchDateTime = formatTehranMatchDateTime(match, lang);
  const canViewEvents = canShowEvents(match);
  const predictionLocked = predictionForceLocked || isPredictionLocked(match);
  const showPrediction = isFutureMatchStatus(match) || Boolean(prediction);
  const stopCardClick = (event) => event.stopPropagation();
  const renderTeamName = (name, flag, englishName, team) => {
    const isFavorite = team
      ? favoriteTeamIds.has(String(team.id)) ||
        favoriteTeamKeys.has(normalizeTeamKey(team.team_key || team.name_en || team.name_fa || team.team_name || team.id))
      : false;

    return (
      <strong className="team-name">
        <TeamFlag flagEmoji={flag} teamName={englishName} />
        {name}
        {team && (
          <button
            className={`favorite-star ${isFavorite ? "active" : ""}`}
            aria-label={isFavorite ? t.removeFavorite : t.addFavorite}
            onClick={(event) => {
              event.stopPropagation();
              onFavoriteToggle(team);
            }}
          >
            {isFavorite ? "\u2605" : "\u2606"}
          </button>
        )}
      </strong>
    );
  };

  return (
    <article
      className={`match-card ${variant === "hero" ? "hero-match-card" : ""} ${isLive ? "live-match" : ""} ${isExpanded ? "selected" : ""}`}
    >
      <div className="match-top">
        <div className="match-top-main">
          <span className="match-date">{matchDateTime.date}</span>
          <span className="match-stage">{match.stage_label || match.stage}</span>
        </div>
        {isLive && variant !== "hero" && <span className="match-status live live-pulse">{matchStatus.label}</span>}
      </div>

      <div className="match-score-block">
        <div className="teams">
          {renderTeamName(homeName, match.home_flag, match.home_en, homeTeam)}
          <span
            className={
              matchScore
                ? `match-score ${isScoreChanged ? "score-changed" : ""}`
                : shouldShowScoreFallback
                  ? "match-score-pending"
                  : "match-vs"
            }
          >
            {matchScore || (shouldShowScoreFallback ? t.scorePending : t.vs)}
          </span>
          {renderTeamName(awayName, match.away_flag, match.away_en, awayTeam)}
        </div>
        <PenaltySummary match={match} lang={lang} />
      </div>

      <div className="match-meta-grid">
        <span>🕒 {matchDateTime.time}</span>
        {match.group && (
          <span>
            🏆 {t.group} {match.group}
          </span>
        )}
        <span>🏟 {match.stadium}</span>
        <span>📍 {match.city}</span>
      </div>

      {match.result && match.score_source !== "football-data.org" && (
        <div className="match-info">
          <span>📊 {match.result}</span>
        </div>
      )}

      {showPrediction && (
        <div className={`prediction-panel ${predictionLocked ? "locked" : ""}`}>
          <div className="prediction-heading">
            <strong>{t.prediction}</strong>
            {predictionLocked && <span>{t.predictionLocked}</span>}
            {!predictionLocked && predictionWasSaved && <span>{t.predictionSaved}</span>}
          </div>
          <div className="prediction-options">
            {["home", "draw", "away"].map((value) => (
              <button
                className={prediction === value ? "selected" : ""}
                disabled={predictionLocked || isPredictionSaving}
                key={value}
                onClick={() => onPredictionSelect?.(match.id, value)}
                type="button"
              >
                {getPredictionLabel(match, value, lang, t)}
              </button>
            ))}
          </div>
          {prediction && (
            <p className="prediction-selection">
              {t.yourPrediction}: <strong>{getPredictionLabel(match, prediction, lang, t)}</strong>
            </p>
          )}
          {predictionSaveFailed && <p className="prediction-error">{t.predictionSaveFailed}</p>}
        </div>
      )}

      {showReminder && (
        <button
          className={`remind-btn ${isReminderActive ? "active" : ""}`}
          onClick={(event) => {
            event.stopPropagation();
            onReminderToggle(match.id);
          }}
        >
          {isReminderActive ? `🔕 ${t.cancelReminder}` : `🔔 ${t.remind}`}
        </button>
      )}

      {canViewEvents && (
        <button className="details-btn" onClick={() => onDetailsClick?.(match)}>
          {t.viewEvents}
        </button>
      )}

      {isExpanded && (
        <div className="match-events" onClick={stopCardClick}>
          <h3>{t.matchEvents}</h3>
          {isLoadingEvents ? (
            <p>{t.loadingEvents}</p>
          ) : eventsFailed ? (
            <p>{t.eventRequestFailed}</p>
          ) : eventsUnavailable ? (
            <p>{t.eventSourceUnavailable}</p>
          ) : events.length > 0 ? (
            <ol className="event-timeline">
              {events.map((event, index) => (
                <EventRow
                  event={event}
                  index={index}
                  key={`${event.display_minute || event.raw_minute || event.minute}-${event.type}-${event.player}-${event.team}-${index}`}
                  lang={lang}
                  match={match}
                  t={t}
                />
              ))}
            </ol>
          ) : (
            <p>{t.noEvents}</p>
          )}
        </div>
      )}
    </article>
  );
}

function HeroMatchCard({ label, mode, match, lang, t, children }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (mode !== "upcoming") return undefined;

    const countdownTimer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(countdownTimer);
  }, [match?.id, mode]);

  const statusLine = getHeroStatusLine(match, mode, lang, t, now);

  return (
    <section className={`smart-hero-card ${mode}`} aria-label={label}>
      <div className="smart-hero-heading">
        <span className="smart-hero-kicker">{label}</span>
      </div>
      <div className={`smart-hero-status ${statusLine.isCountdown ? "countdown" : ""}`}>
        {statusLine.label && <span>{statusLine.label}</span>}
        <strong dir={statusLine.isCountdown ? "ltr" : t.dir}>{statusLine.value}</strong>
      </div>
      {children}
    </section>
  );
}

function BracketMatchCard({ match, lang, t }) {
  if (!match) return <div className="bracket-match bracket-match-empty" aria-hidden="true" />;

  const status = getMatchStatus(match, lang, t);
  const score = getMatchScore(match);
  const showScore = ["live", "finished"].includes(status.key);
  const homeName = getLocalizedTeamName(match, "home", lang) || match.home_team_label || t.unavailable;
  const awayName = getLocalizedTeamName(match, "away", lang) || match.away_team_label || t.unavailable;
  const penaltySummary = getPenaltySummary(match, lang);

  return (
    <article
      className={`bracket-match ${status.key === "live" ? "is-live" : ""} ${status.key === "finished" ? "is-finished" : ""} ${penaltySummary ? "has-penalties" : ""}`}
      dir={t.dir}
    >
      <header className="bracket-match-meta">
        <span>{match.date_iran || "—"}</span>
        <span>{match.time_iran || "—"}</span>
        <span className={`bracket-status ${status.key}`}>{status.label}</span>
      </header>

      <div className="bracket-team-row">
        <TeamFlag flagEmoji={match.home_flag} teamName={match.home_en} />
        <strong title={homeName}>{homeName}</strong>
        <b>{showScore ? getScoreValue(match, ["home_score", "homeScore"]) ?? "—" : ""}</b>
      </div>
      <div className="bracket-team-row">
        <TeamFlag flagEmoji={match.away_flag} teamName={match.away_en} />
        <strong title={awayName}>{awayName}</strong>
        <b>{showScore ? getScoreValue(match, ["away_score", "awayScore"]) ?? "—" : ""}</b>
      </div>

      <PenaltySummary match={match} lang={lang} compact />

      {showScore && score && <span className="bracket-score-summary">{score}</span>}
      <span className="bracket-match-number">#{match.id}</span>
    </article>
  );
}

function BracketColumn({ ids, matchesById, round, title, side, lang, t }) {
  return (
    <section className={`bracket-column round-${round} side-${side}`}>
      <h3>{title}</h3>
      <div className="bracket-slots">
        {ids.map((id) => (
          <div className="bracket-slot" key={id}>
            <BracketMatchCard match={matchesById.get(id)} lang={lang} t={t} />
          </div>
        ))}
      </div>
    </section>
  );
}

function KnockoutBracket({ matches, lang, t }) {
  const [zoom, setZoom] = useState(1);
  const matchesById = useMemo(
    () => new Map(
      matches
        .filter((match) => Number(match.id) >= 73 && Number(match.id) <= 104)
        .map((match) => [Number(match.id), match]),
    ),
    [matches],
  );
  const updateZoom = (change) => {
    setZoom((current) => Math.min(1.25, Math.max(0.75, Number((current + change).toFixed(2)))));
  };
  const stageStyle = {
    "--bracket-zoom": zoom,
    width: `${1668 * zoom}px`,
    height: `${1090 * zoom}px`,
  };

  return (
    <div className="bracket-scroll-shell">
      <div className="bracket-tools" dir={t.dir}>
        <p>{t.bracketSwipeHint}</p>
        <div className="bracket-zoom-controls" aria-label={t.bracketTitle}>
          <button type="button" title={t.zoomOut} aria-label={t.zoomOut} onClick={() => updateZoom(-0.1)} disabled={zoom <= 0.75}>−</button>
          <span aria-live="polite">{Math.round(zoom * 100)}%</span>
          <button type="button" title={t.zoomIn} aria-label={t.zoomIn} onClick={() => updateZoom(0.1)} disabled={zoom >= 1.25}>+</button>
          <button type="button" className="bracket-reset-btn" onClick={() => setZoom(1)} disabled={zoom === 1}>{t.resetZoom}</button>
        </div>
      </div>

      <div className="bracket-scroll bracket-scroll-area" dir="ltr">
        <div className="bracket-stage" style={stageStyle}>
          <div className="bracket-board">
            <BracketColumn ids={[74, 77, 73, 75, 83, 84, 81, 82]} matchesById={matchesById} round="r32" title={t.roundOf32} side="left" lang={lang} t={t} />
            <BracketColumn ids={[89, 90, 93, 94]} matchesById={matchesById} round="r16" title={t.roundOf16} side="left" lang={lang} t={t} />
            <BracketColumn ids={[97, 98]} matchesById={matchesById} round="qf" title={t.quarterfinals} side="left" lang={lang} t={t} />
            <BracketColumn ids={[101]} matchesById={matchesById} round="sf" title={t.semifinals} side="left" lang={lang} t={t} />

            <section className="bracket-center" dir={t.dir}>
              <div className="bracket-center-match final-match">
                <h3>{t.final}</h3>
                <BracketMatchCard match={matchesById.get(104)} lang={lang} t={t} />
              </div>
              <div className="bracket-trophy" aria-hidden="true"><span>MP</span></div>
              <div className="bracket-center-match third-match">
                <h3>{t.thirdPlace}</h3>
                <BracketMatchCard match={matchesById.get(103)} lang={lang} t={t} />
              </div>
            </section>

            <BracketColumn ids={[102]} matchesById={matchesById} round="sf" title={t.semifinals} side="right" lang={lang} t={t} />
            <BracketColumn ids={[99, 100]} matchesById={matchesById} round="qf" title={t.quarterfinals} side="right" lang={lang} t={t} />
            <BracketColumn ids={[91, 92, 95, 96]} matchesById={matchesById} round="r16" title={t.roundOf16} side="right" lang={lang} t={t} />
            <BracketColumn ids={[76, 78, 79, 80, 86, 88, 85, 87]} matchesById={matchesById} round="r32" title={t.roundOf32} side="right" lang={lang} t={t} />
          </div>
        </div>
      </div>
    </div>
  );
}

function NewsCard({ item, lang }) {
  return (
    <article className="news-card">
      <span>{lang === "fa" ? item.tag_fa : item.tag_en}</span>
      <h3>{lang === "fa" ? item.title_fa : item.title_en}</h3>
    </article>
  );
}

function TeamCard({ team, lang, t, isFavorite, onToggle }) {
  return (
    <article className="team-card">
      <div className="team-card-main">
        <span className="team-emoji">{team.emoji}</span>
        <div>
          <h3>{lang === "fa" ? team.name_fa : team.name_en}</h3>
          <small>{isFavorite ? t.favoriteTeams : t.chooseFavorite}</small>
        </div>
      </div>
      <button
        className={`chip-btn ${isFavorite ? "active" : ""}`}
        onClick={() => onToggle(team)}
      >
        <span>{isFavorite ? "\u2605" : "\u2606"}</span>
        {isFavorite ? t.removeFavorite : t.addFavorite}
      </button>
    </article>
  );
}

function App() {
  const initialTelegramUser = window.Telegram?.WebApp?.initDataUnsafe?.user || null;
  const [lang, setLang] = useState("fa");
  const [activeTab, setActiveTab] = useState("home");
  const [telegramUser] = useState(initialTelegramUser);
  const [isUserSaved, setIsUserSaved] = useState(false);

  const [matches, setMatches] = useState([]);
  const [isLoadingMatches, setIsLoadingMatches] = useState(true);
  const [matchesError, setMatchesError] = useState("");
  const [currentTime, setCurrentTime] = useState(0);
  const [newsItems] = useState([]);
  const [teams, setTeams] = useState([]);
  const [favoriteTeams, setFavoriteTeams] = useState([]);
  const [favoriteMessage, setFavoriteMessage] = useState("");
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
  const predictionMutationVersion = useRef(0);
  const predictionSaveRequests = useRef(new Map());

  const t = translations[lang];
  const telegramId = telegramUser?.id;

  const favoriteTeamIds = useMemo(
    () => new Set(favoriteTeams.map((team) => String(team.id))),
    [favoriteTeams],
  );

  const favoriteTeamKeys = useMemo(
    () => new Set(
      favoriteTeams.map((team) => normalizeTeamKey(team.team_key || team.name_en || team.name_fa || team.team_name || team.id)),
    ),
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
      lookup.set(team.name_en, team);
      lookup.set(team.name_fa, team);
    });
    return lookup;
  }, [teams]);

  const teamPayload = (team) => ({
    team_id: team.id,
    team_key: team.team_key || normalizeTeamKey(team.name_en || team.name_fa || team.team_name || team.id),
    team_name: team.team_name || team.name_en || team.name_fa,
    name_en: team.name_en || team.team_name || team.name_fa,
    name_fa: team.name_fa || team.team_name || team.name_en,
    emoji: team.emoji || team.flag || "\u26bd",
  });

  const isTeamFavorite = (team) => (
    favoriteTeamIds.has(String(team.id)) ||
    favoriteTeamKeys.has(normalizeTeamKey(team.team_key || team.name_en || team.name_fa || team.team_name || team.id))
  );

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

  const liveMatches = useMemo(
    () => matches.filter((match) => isLiveMatch(match)),
    [matches],
  );

  const futureMatches = useMemo(
    () => matches
      .filter(
        (match) =>
          match.is_finished !== true &&
          match.is_live !== true &&
          !isFinishedMatch(match) &&
          !isLiveMatch(match) &&
          isFutureMatchStatus(match),
      )
      .map((match) => ({ match, kickoffTime: getKickoffTime(match) }))
      .filter(({ kickoffTime }) => Number.isFinite(kickoffTime) && kickoffTime > currentTime)
      .sort((first, second) => first.kickoffTime - second.kickoffTime)
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
    const scoreTimeouts = scoreChangeTimeouts.current;

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

      return fetch(`${API_BASE_URL}/matches`)
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
          console.error("Failed to load matches:", error);
          setMatchesError(t.matchesError);
        })
        .finally(() => {
          if (isInitialLoad) setIsLoadingMatches(false);
        });
    };

    loadMatches(true);
    const matchRefresh = window.setInterval(loadMatches, 30000);

    return () => {
      window.clearInterval(matchRefresh);
      scoreTimeouts.forEach((timeout) => window.clearTimeout(timeout));
      scoreTimeouts.clear();
    };
  }, [t.matchesError]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/teams`)
      .then((response) => {
        if (!response.ok) throw new Error(`Teams request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => setTeams(Array.isArray(data.teams) ? data.teams : []))
      .catch((error) => console.error("Failed to load teams:", error));
  }, []);

  useEffect(() => {
    if (!telegramId) return;

    fetch(`${API_BASE_URL}/user`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_id: telegramId,
        first_name: telegramUser?.first_name || "",
        last_name: telegramUser?.last_name || "",
        username: telegramUser?.username || "",
        language_code: telegramUser?.language_code || "",
      }),
    })
      .then((response) => {
        if (!response.ok) throw new Error(`User request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => setIsUserSaved(Boolean(data.success)))
      .catch((error) => {
        console.error("Failed to save Telegram user:", error);
        setIsUserSaved(false);
      });

    fetch(`${API_BASE_URL}/favorite-teams/${telegramId}`)
      .then((response) => {
        if (!response.ok) throw new Error(`Favorites request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => setFavoriteTeams(Array.isArray(data.favorite_teams) ? data.favorite_teams : []))
      .catch((error) => console.error("Failed to load favorite teams:", error));

    fetch(`${API_BASE_URL}/reminders/${telegramId}`)
      .then((response) => {
        if (!response.ok) throw new Error(`Reminders request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => setReminders(Array.isArray(data.reminders) ? data.reminders : []))
      .catch((error) => console.error("Failed to load reminders:", error));

    const predictionFetchVersion = predictionMutationVersion.current;
    fetch(`${API_BASE_URL}/predictions/${telegramId}`)
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

    fetch(`${API_BASE_URL}/prediction-stats/${telegramId}`)
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
    if (!telegramId || !predictionResultsVersion) return;

    fetch(`${API_BASE_URL}/prediction-stats/${telegramId}`)
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

  const addFavoriteTeam = (team) => {
    if (!telegramId) {
      setFavoriteMessage(t.unavailable);
      return;
    }

    const displayName = getTeamDisplayName(team);

    fetch(`${API_BASE_URL}/favorite-team`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_id: telegramId,
        ...teamPayload(team),
      }),
    })
      .then((response) => {
        if (!response.ok) throw new Error(`Favorite request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setFavoriteTeams(Array.isArray(data.favorite_teams) ? data.favorite_teams : []);
        setFavoriteMessage(`${displayName} ${t.addedFavorite}`);
      })
      .catch((error) => {
        console.error("Failed to add favorite team:", error);
        setFavoriteMessage(t.unavailable);
      });
  };

  const removeFavoriteTeam = (team) => {
    if (!telegramId) {
      setFavoriteMessage(t.unavailable);
      return;
    }

    const teamId = typeof team === "object" ? team.id : team;
    const existingTeam = favoriteTeams.find((item) => String(item.id) === String(teamId)) || team;
    const displayName = typeof existingTeam === "object" ? getTeamDisplayName(existingTeam) : "";

    fetch(`${API_BASE_URL}/favorite-team`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_id: telegramId,
        team_id: teamId,
        team_key: typeof existingTeam === "object"
          ? existingTeam.team_key || normalizeTeamKey(existingTeam.name_en || existingTeam.name_fa || existingTeam.team_name || existingTeam.id)
          : "",
      }),
    })
      .then((response) => {
        if (!response.ok) throw new Error(`Favorite delete failed: ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setFavoriteTeams(Array.isArray(data.favorite_teams) ? data.favorite_teams : []);
        setFavoriteMessage(`${displayName} ${t.removedFavorite}`.trim());
      })
      .catch((error) => {
        console.error("Failed to remove favorite team:", error);
        setFavoriteMessage(t.unavailable);
      });
  };

  const toggleFavoriteTeam = (team) => {
    if (isTeamFavorite(team)) {
      removeFavoriteTeam(team);
    } else {
      addFavoriteTeam(team);
    }
  };

  const addReminder = (matchId) => {
    if (!telegramId) {
      setReminderMessage(t.unavailable);
      return;
    }

    fetch(`${API_BASE_URL}/reminder`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_id: telegramId,
        match_id: matchId,
      }),
    })
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
    if (!telegramId) {
      setReminderMessage(t.unavailable);
      return;
    }

    fetch(`${API_BASE_URL}/reminder`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_id: telegramId,
        match_id: matchId,
      }),
    })
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

    fetch(`${API_BASE_URL}/prediction`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ telegram_id: telegramId, match_id: matchId, prediction }),
    })
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

        fetch(`${API_BASE_URL}/prediction-stats/${telegramId}`)
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
    fetch(`${API_BASE_URL}/match/${match.id}/events`)
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

        if (events.length === 0 && (data.warning || data.error)) {
          setEventUnavailableMatchIds((currentIds) => new Set(currentIds).add(match.id));
        }
      })
      .catch((error) => {
        console.error("Failed to load match events:", error);
        setEventFailedMatchIds((currentIds) => new Set(currentIds).add(match.id));
      })
      .finally(() => setLoadingEventsId(null));
  };

  const getMatchTeams = (match) => ({
    homeTeam: teamsByName.get(match.home_en) || teamsByName.get(match.home_fa) || teamFromMatch(match, "home"),
    awayTeam: teamsByName.get(match.away_en) || teamsByName.get(match.away_fa) || teamFromMatch(match, "away"),
  });

  const profileName = telegramUser
    ? `${telegramUser.first_name || ""} ${telegramUser.last_name || ""}`.trim()
    : t.profileTitle;

  const profileUsername = telegramUser?.username
    ? `@${telegramUser.username}`
    : t.noUsername;

  const heroMatch = getHeroMatch(liveMatches, upcomingOnlyMatches, pastOnlyMatches);
  const heroMode = getHeroMode(heroMatch);
  const heroLabel = {
    live: t.heroLive,
    upcoming: t.heroUpcoming,
    result: t.heroResult,
  }[heroMode] || t.nextMatch;
  const otherLiveMatches = filterHeroFromList(liveMatches, heroMatch);
  const upcomingWithoutHero = filterHeroFromList(upcomingOnlyMatches, heroMatch);
  const resultsWithoutHero = filterHeroFromList(pastOnlyMatches, heroMatch);

  let homeSectionMatches = [];
  let homeSectionTitle = t.homeNextMatches;
  let homeSectionTab = "upcoming";
  let homeEmptyMessage = t.noUpcomingMatches;

  if (heroMode === "live" && otherLiveMatches.length > 0) {
    homeSectionMatches = otherLiveMatches;
    homeSectionTitle = t.otherLiveMatches;
    homeSectionTab = "live";
    homeEmptyMessage = t.noLiveMatches;
  } else if (heroMode === "live" || heroMode === "upcoming") {
    homeSectionMatches = upcomingWithoutHero.slice(0, 3);
  } else if (heroMode === "result") {
    homeSectionMatches = resultsWithoutHero.slice(0, 3);
    homeSectionTitle = t.latestResults;
    homeSectionTab = "past";
    homeEmptyMessage = t.noPastMatches;
  }

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
        favoriteTeamIds={favoriteTeamIds}
        favoriteTeamKeys={favoriteTeamKeys}
        onFavoriteToggle={toggleFavoriteTeam}
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
      />
    );
  };

  return (
    <main className={`app ${lang}`} dir={t.dir}>
      <section className="hero">
        <div className="hero-toolbar">
          <BrandLogo />
          <div className="brand-copy">
            <strong>{t.title}</strong>
            <small>{t.brandLabel}</small>
          </div>
          <button className="lang-btn" onClick={toggleLang}>
            {t.langButton}
          </button>
        </div>

        <div>
          <p className="eyebrow">{t.worldCup}</p>
          <h1>{t.title}</h1>
          <p className="subtitle">{t.subtitle}</p>
        </div>

        <div className="stats-row">
          <div>
            <strong>{lang === "fa" ? "۴۸" : "48"}</strong>
            <span>{t.teams}</span>
          </div>
          <div>
            <strong>{lang === "fa" ? "۱۰۴" : "104"}</strong>
            <span>{t.matches}</span>
          </div>
          <div>
            <strong>{lang === "fa" ? "۱۶" : "16"}</strong>
            <span>{t.cities}</span>
          </div>
        </div>

        {activeTab === "home" && (
          heroMatch ? (
            <HeroMatchCard key={`${heroMatch.id}-${heroMode}`} label={heroLabel} mode={heroMode} match={heroMatch} lang={lang} t={t}>
              {renderMatchCard(heroMatch, {
                variant: "hero",
                showReminder: heroMode === "upcoming",
              })}
            </HeroMatchCard>
          ) : (
            <div className="hero-card">
              <strong>{isLoadingMatches ? t.loadingMatches : matchesError || t.noUpcomingMatches}</strong>
            </div>
          )
        )}
      </section>

      {activeTab === "home" && (
        <>
          <section className="quick-actions">
            <button onClick={() => setActiveTab("live")}>
              <span>●</span>
              {t.liveMatches}
            </button>
            <button onClick={() => setActiveTab("upcoming")}>
              <span>⚽</span>
              {t.nextMatches}
            </button>
            <button onClick={() => setActiveTab("past")}>
              <span>🏁</span>
              {t.pastMatches}
            </button>
            <button onClick={() => setActiveTab("favorites")}>
              <span>⭐</span>
              {t.favorites}
            </button>
          </section>

          <section className="section">
            <div className="section-header">
              <h2>{homeSectionTitle}</h2>
              <span onClick={() => setActiveTab(homeSectionTab)}>{t.viewAll}</span>
            </div>

            <div className="matches">
              {isLoadingMatches && <p>{t.loadingMatches}</p>}
              {!isLoadingMatches && matchesError && <p>{matchesError}</p>}
              {!isLoadingMatches && !matchesError && homeSectionMatches.length === 0 && (
                <p>{homeEmptyMessage}</p>
              )}
              {homeSectionMatches.map((match) =>
                renderMatchCard(match, { showReminder: isFutureMatchStatus(match) }),
              )}
            </div>

            {(reminderMessage || favoriteMessage) && (
              <p className="status-message">{reminderMessage || favoriteMessage}</p>
            )}
          </section>
        </>
      )}

      {activeTab === "live" && (
        <section className="section">
          <div className="section-header">
            <h2>{t.liveMatches}</h2>
          </div>

          <div className="matches">
            {isLoadingMatches && <p>{t.loadingMatches}</p>}
            {!isLoadingMatches && matchesError && <p>{matchesError}</p>}
            {!isLoadingMatches && !matchesError && liveMatches.length === 0 && (
              <p>{t.noLiveMatches}</p>
            )}
            {liveMatches.map((match) => renderMatchCard(match, { showReminder: false }))}
          </div>
        </section>
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

      {activeTab === "bracket" && (
        <section className="section bracket-section">
          <div className="bracket-heading" dir={t.dir}>
            <div>
              <span className="bracket-kicker">MATCHPULSE 2026</span>
              <h2>{t.bracketTitle}</h2>
              <p>{t.bracketSubtitle}</p>
            </div>
            <span className="bracket-heading-mark" aria-hidden="true">MP</span>
          </div>

          {isLoadingMatches && <p className="bracket-message">{t.loadingMatches}</p>}
          {!isLoadingMatches && matchesError && <p className="bracket-message">{matchesError}</p>}
          {!isLoadingMatches && !matchesError && (
            <KnockoutBracket matches={matches} lang={lang} t={t} />
          )}
        </section>
      )}

      {activeTab === "news" && (
        <section className="section">
          <div className="section-header">
            <h2>{t.latestNews}</h2>
          </div>

          <div className="news-list">
            {newsItems.length === 0 && <p>{t.noNews}</p>}
            {newsItems.map((item) => (
              <NewsCard key={item.id} item={item} lang={lang} />
            ))}
          </div>
        </section>
      )}

      {activeTab === "favorites" && (
        <section className="section">
          <div className="section-header">
            <h2>{t.favoriteTeams}</h2>
          </div>

          {favoriteMessage && <p className="status-message">{favoriteMessage}</p>}

          <div className="profile-list favorites-panel">
            <div className="profile-list-header">
              <h3>{t.favoriteTeams}</h3>
              <span>{favoriteTeams.length}</span>
            </div>

            {favoriteTeams.length === 0 && <p>{t.noFavorites}</p>}
            {favoriteTeams.map((team) => (
              <div className="profile-item" key={team.id}>
                <span>{team.emoji || team.flag || "\u26bd"}</span>
                <div className="profile-item-text">
                  <strong>{getTeamDisplayName(team)}</strong>
                </div>
                <button
                  className="chip-btn profile-remove-btn"
                  onClick={() => removeFavoriteTeam(team)}
                >
                  {t.removeFavorite}
                </button>
              </div>
            ))}
          </div>

          <div className="section-header inline-section-header">
            <h2>{t.chooseFavorite}</h2>
          </div>

          <div className="news-list">
            {teams.length === 0 && <p>{t.noFavorites}</p>}
            {teams.map((team) => (
              <TeamCard
                key={team.id}
                team={team}
                lang={lang}
                t={t}
                isFavorite={isTeamFavorite(team)}
                onToggle={toggleFavoriteTeam}
              />
            ))}
          </div>
        </section>
      )}

      {activeTab === "profile" && (
        <section className="section profile-section">
          <article className="profile-card">
            <div className="profile-header">
              <div className="avatar">
                {telegramUser?.photo_url ? (
                  <img src={telegramUser.photo_url} alt={profileName || t.telegramUser} />
                ) : (
                  "MP"
                )}
              </div>

              <div>
                <p className="eyebrow">{t.telegramUser}</p>
                <h2>{profileName || t.telegramUser}</h2>
                <p>{telegramUser ? profileUsername : t.profileText}</p>
              </div>
            </div>

            <div className="profile-grid">
              <div>
                <span>{t.telegramId}</span>
                <strong>{telegramUser?.id || t.unavailable}</strong>
              </div>
              <div>
                <span>{t.username}</span>
                <strong>{telegramUser ? profileUsername : t.unavailable}</strong>
              </div>
              <div>
                <span>{t.language}</span>
                <strong>{telegramUser?.language_code || t.unavailable}</strong>
              </div>
              <div>
                <span>{t.profile}</span>
                <strong>{telegramUser ? (isUserSaved ? `✅ ${t.saved}` : `⏳ ${t.notSaved}`) : t.unavailable}</strong>
              </div>
            </div>

            <div className="prediction-stats-card">
              <div className="prediction-stats-heading">
                <span>{t.predictionPoints}</span>
                <strong>{predictionStats.points}</strong>
              </div>
              <div className="prediction-stats-grid">
                <span>{t.predictionCorrect}<strong>{predictionStats.correct}</strong></span>
                <span>{t.predictionWrong}<strong>{predictionStats.wrong}</strong></span>
                <span>{t.predictionPending}<strong>{predictionStats.pending}</strong></span>
              </div>
            </div>

            <div className="profile-list">
              <div className="profile-list-header">
                <h3>⭐ {t.favoriteTeams}</h3>
                <span>{favoriteTeams.length}</span>
              </div>

              {favoriteTeams.length === 0 && <p>{t.noFavorites}</p>}
              {favoriteTeams.map((team) => (
                <div className="profile-item" key={team.id}>
                  <span>{team.emoji || team.flag || "\u26bd"}</span>
                  <div className="profile-item-text">
                    <strong>{getTeamDisplayName(team)}</strong>
                  </div>
                  <button
                    className="chip-btn profile-remove-btn"
                    onClick={() => removeFavoriteTeam(team)}
                  >
                    {t.removeFavorite}
                  </button>
                </div>
              ))}
            </div>

            <div className="profile-list">
              <div className="profile-list-header">
                <h3>🔔 {t.activeReminders}</h3>
                <span>{reminders.length}</span>
              </div>

              {reminders.length === 0 && <p>{t.noReminders}</p>}
              {reminders.map((match) => {
                const reminderDateTime = formatTehranMatchDateTime(match, lang);

                return (
                  <div className="profile-item reminder-item" key={match.id}>
                    <TeamFlag flagEmoji={match.home_flag} teamName={match.home_en} />
                    <div className="profile-item-text">
                      <strong>
                        <span className="profile-reminder-match">
                          {match.home_en}
                          <span>{t.vs}</span>
                          <TeamFlag flagEmoji={match.away_flag} teamName={match.away_en} />
                          {match.away_en}
                        </span>
                      </strong>
                      <small>{reminderDateTime.compact}</small>
                    </div>
                    <button
                      className="chip-btn profile-remove-btn"
                      onClick={() => removeReminder(match.id)}
                    >
                      {t.cancelReminder}
                    </button>
                  </div>
                );
              })}
            </div>
          </article>
        </section>
      )}

      <nav className="bottom-nav">
        <button
          className={activeTab === "home" ? "active" : ""}
          onClick={() => setActiveTab("home")}
        >
          🏠 {t.home}
        </button>

        <button
          className={activeTab === "live" ? "active" : ""}
          onClick={() => setActiveTab("live")}
        >
          ● {t.live}
        </button>

        <button
          className={activeTab === "upcoming" ? "active" : ""}
          onClick={() => setActiveTab("upcoming")}
        >
          ⚽ {t.upcoming}
        </button>

        <button
          className={activeTab === "past" ? "active" : ""}
          onClick={() => setActiveTab("past")}
        >
          🏁 {t.past}
        </button>

        <button
          className={activeTab === "bracket" ? "active" : ""}
          onClick={() => setActiveTab("bracket")}
        >
          ◇ {t.bracket}
        </button>

        <button
          className={activeTab === "news" ? "active" : ""}
          onClick={() => setActiveTab("news")}
        >
          📰 {t.news}
        </button>

        <button
          className={activeTab === "profile" ? "active" : ""}
          onClick={() => setActiveTab("profile")}
        >
          👤 {t.profile}
        </button>
      </nav>
    </main>
  );
}

export default App;
