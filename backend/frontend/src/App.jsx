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

  if (match?.is_live || status === "live") return "live";
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

function getMatchStatus(match, t) {
  const normalizedStatus = normalizeMatchStatus(match);

  if (normalizedStatus === "live") {
    return { key: "live", label: t.statusLive };
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
    pastMatches: "نتایج",
    latestNews: "آخرین اخبار",
    favorites: "تیم‌های محبوب",
    chooseFavorite: "تیم محبوبت را انتخاب کن",
    favoriteTeams: "تیم‌های محبوب",
    addedFavorite: "به تیم‌های محبوب اضافه شد",
    removedFavorite: "از تیم‌های محبوب حذف شد",
    addedReminder: "یادآور مسابقه ذخیره شد",
    removedReminder: "یادآور مسابقه حذف شد",
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
    noEvents: "رویدادی برای این بازی ثبت نشده یا در منبع فعلی در دسترس نیست",
    eventSourceUnavailable: "رویدادی برای این بازی ثبت نشده یا در منبع فعلی در دسترس نیست",
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
    pastMatches: "Results",
    latestNews: "Latest News",
    favorites: "Favorite Teams",
    chooseFavorite: "Choose your favorite team",
    favoriteTeams: "Favorite Teams",
    addedFavorite: "Added to favorite teams",
    removedFavorite: "Removed from favorite teams",
    addedReminder: "Match reminder saved",
    removedReminder: "Match reminder removed",
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
    noEvents: "No event is recorded for this match or available from the current source.",
    eventSourceUnavailable: "No event is recorded for this match or available from the current source.",
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
    own_goal: "\u06af\u0644 \u0628\u0647 \u062e\u0648\u062f\u06cc",
    var_disallowed_goal: "\u06af\u0644 \u0645\u0631\u062f\u0648\u062f \u0628\u0627 VAR",
    disallowed_goal: "\u06af\u0644 \u0645\u0631\u062f\u0648\u062f \u0628\u0627 VAR",
    penalty_missed: "\u067e\u0646\u0627\u0644\u062a\u06cc \u0627\u0632 \u062f\u0633\u062a \u0631\u0641\u062a\u0647",
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
    own_goal: "Own goal",
    var_disallowed_goal: "VAR-disallowed goal",
    disallowed_goal: "VAR-disallowed goal",
    penalty_missed: "Missed penalty",
    assist: "Assist",
    yellow_card: "Yellow card",
    red_card: "Red card",
    substitution: "Substitution",
    var: "VAR",
    unknown: "Event",
  },
};

function getEventTypeLabel(type, lang) {
  return EVENT_LABELS[lang]?.[type] || type || "";
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
    var_disallowed_goal: "\u274c",
    disallowed_goal: "\u274c",
    penalty_missed: "\u274c",
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
  const title = getEventTypeLabel(type, lang) || event.description || type;
  const eventIcon = getRenderedEventIcon(type);
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
  isScoreChanged = false,
}) {
  const matchStatus = getMatchStatus(match, t);
  const isLive = match.status === "live";
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
      className={`match-card ${isLive ? "live-match" : ""} ${isExpanded ? "selected" : ""}`}
    >
      <div className="match-top">
        <div className="match-top-main">
          <span className="match-date">{matchDateTime.date}</span>
          <span className="match-stage">{match.stage_label || match.stage}</span>
        </div>
        {isLive && <span className="match-status live live-pulse">{matchStatus.label}</span>}
      </div>

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

      {match.result && (
        <div className="match-info">
          <span>📊 {match.result}</span>
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

function BracketMatchCard({ match, lang, t }) {
  if (!match) return <div className="bracket-match bracket-match-empty" aria-hidden="true" />;

  const status = getMatchStatus(match, t);
  const score = getMatchScore(match);
  const showScore = ["live", "finished"].includes(status.key);
  const homeName = getLocalizedTeamName(match, "home", lang) || match.home_team_label || t.unavailable;
  const awayName = getLocalizedTeamName(match, "away", lang) || match.away_team_label || t.unavailable;

  return (
    <article
      className={`bracket-match ${status.key === "live" ? "is-live" : ""} ${status.key === "finished" ? "is-finished" : ""}`}
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
  const matchesById = useMemo(
    () => new Map(
      matches
        .filter((match) => Number(match.id) >= 73 && Number(match.id) <= 104)
        .map((match) => [Number(match.id), match]),
    ),
    [matches],
  );

  return (
    <div className="bracket-scroll" dir="ltr">
      <div className="bracket-board">
        <BracketColumn ids={[73, 75, 74, 77, 76, 78, 79, 80]} matchesById={matchesById} round="r32" title={t.roundOf32} side="left" lang={lang} t={t} />
        <BracketColumn ids={[90, 89, 91, 92]} matchesById={matchesById} round="r16" title={t.roundOf16} side="left" lang={lang} t={t} />
        <BracketColumn ids={[97, 99]} matchesById={matchesById} round="qf" title={t.quarterfinals} side="left" lang={lang} t={t} />
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
        <BracketColumn ids={[98, 100]} matchesById={matchesById} round="qf" title={t.quarterfinals} side="right" lang={lang} t={t} />
        <BracketColumn ids={[93, 94, 95, 96]} matchesById={matchesById} round="r16" title={t.roundOf16} side="right" lang={lang} t={t} />
        <BracketColumn ids={[83, 84, 81, 82, 86, 88, 85, 87]} matchesById={matchesById} round="r32" title={t.roundOf32} side="right" lang={lang} t={t} />
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
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [matchEventsById, setMatchEventsById] = useState({});
  const [eventUnavailableMatchIds, setEventUnavailableMatchIds] = useState(() => new Set());
  const [loadingEventsId, setLoadingEventsId] = useState(null);
  const [scoreChangedMatchIds, setScoreChangedMatchIds] = useState(() => new Set());
  const scoreChangeTimeouts = useRef(new Map());

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
    const tg = window.Telegram?.WebApp;
    const scoreTimeouts = scoreChangeTimeouts.current;

    if (tg) {
      tg.ready();
      tg.expand();
    }

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
          updateMatches(Array.isArray(data.matches) ? data.matches : []);
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
  }, [telegramId, telegramUser]);

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

  const handleMatchDetailsClick = (match) => {
    if (!match?.id) return;

    setSelectedMatchId((currentId) => (currentId === match.id ? null : match.id));

    if (matchEventsById[match.id]) return;

    setEventUnavailableMatchIds((currentIds) => {
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
        setMatchEventsById((currentEvents) => ({
          ...currentEvents,
          [match.id]: Array.isArray(data.events) ? data.events : [],
        }));
      })
      .catch((error) => {
        console.error("Failed to load match events:", error);
        setEventUnavailableMatchIds((currentIds) => new Set(currentIds).add(match.id));
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

  const nextKickoffTime = upcomingOnlyMatches.reduce(
    (earliestKickoff, match) => Math.min(earliestKickoff, getKickoffTime(match)),
    Number.POSITIVE_INFINITY,
  );
  const nextMatchesAtSameTime = Number.isFinite(nextKickoffTime)
    ? upcomingOnlyMatches.filter((match) => Math.abs(getKickoffTime(match) - nextKickoffTime) <= 60000)
    : [];
  const hasLiveMatches = liveMatches.length > 0;
  const homeFeaturedMatches = hasLiveMatches ? liveMatches : nextMatchesAtSameTime;
  const homeFeaturedTitle = hasLiveMatches
    ? t.liveMatches
    : nextMatchesAtSameTime.length > 1
      ? t.nextMatchesTitle
      : t.nextMatch;
  const homeFeaturedTab = hasLiveMatches ? "live" : "upcoming";
  const homeEmptyMessage = hasLiveMatches ? t.noLiveMatches : t.noUpcomingMatches;

  const renderMatchCard = (match, options = {}) => {
    const { homeTeam, awayTeam } = getMatchTeams(match);

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
        isScoreChanged={scoreChangedMatchIds.has(match.id)}
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

        <div className="hero-card">
          <span>{homeFeaturedTitle}</span>
          {homeFeaturedMatches.length > 0 ? (
            <div className="hero-next-list">
              {homeFeaturedMatches.map((match) => {
                const matchDateTime = formatTehranMatchDateTime(match, lang);
                const { homeTeam, awayTeam } = getMatchTeams(match);
                const isHomeFavorite = isTeamFavorite(homeTeam);
                const isAwayFavorite = isTeamFavorite(awayTeam);
                const showHeroEvents = canShowEvents(match);

                return (
                  <div className="hero-next-item" key={match.id}>
                    <div className="hero-next-match">
                      <strong className="hero-next-team">
                        <TeamFlag flagEmoji={match.home_flag} teamName={match.home_en} />
                        {getLocalizedTeamName(match, "home", lang)}
                        <button
                          className={`favorite-star ${isHomeFavorite ? "active" : ""}`}
                          aria-label={isHomeFavorite ? t.removeFavorite : t.addFavorite}
                          onClick={() => toggleFavoriteTeam(homeTeam)}
                        >
                          {isHomeFavorite ? "\u2605" : "\u2606"}
                        </button>
                      </strong>
                      <b>
                        {hasLiveMatches ? getMatchScore(match) || "0 - 0" : t.vs}
                      </b>
                      <strong className="hero-next-team">
                        <TeamFlag flagEmoji={match.away_flag} teamName={match.away_en} />
                        {getLocalizedTeamName(match, "away", lang)}
                        <button
                          className={`favorite-star ${isAwayFavorite ? "active" : ""}`}
                          aria-label={isAwayFavorite ? t.removeFavorite : t.addFavorite}
                          onClick={() => toggleFavoriteTeam(awayTeam)}
                        >
                          {isAwayFavorite ? "\u2605" : "\u2606"}
                        </button>
                      </strong>
                    </div>
                    <small>{matchDateTime.compact}</small>
                    {showHeroEvents && (
                      <button
                        className="details-btn hero-details-btn"
                        onClick={() => handleMatchDetailsClick(match)}
                      >
                        {t.viewEvents}
                      </button>
                    )}
                    {showHeroEvents && selectedMatchId === match.id && (
                      <div className="match-events">
                        <h3>{t.matchEvents}</h3>
                        {loadingEventsId === match.id ? (
                          <p>{t.loadingEvents}</p>
                        ) : eventUnavailableMatchIds.has(match.id) ? (
                          <p>{t.eventSourceUnavailable}</p>
                        ) : (matchEventsById[match.id] || []).length > 0 ? (
                          <ol className="event-timeline">
                            {(matchEventsById[match.id] || []).map((event, index) => (
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
                  </div>
                );
              })}
            </div>
          ) : (
            <strong>
              {isLoadingMatches ? t.loadingMatches : matchesError || t.noUpcomingMatches}
            </strong>
          )}
        </div>
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
              <h2>{homeFeaturedTitle}</h2>
              <span onClick={() => setActiveTab(homeFeaturedTab)}>{t.viewAll}</span>
            </div>

            <div className="matches">
              {isLoadingMatches && <p>{t.loadingMatches}</p>}
              {!isLoadingMatches && matchesError && <p>{matchesError}</p>}
              {!isLoadingMatches && !matchesError && homeFeaturedMatches.length === 0 && (
                <p>{homeEmptyMessage}</p>
              )}
              {homeFeaturedMatches.map((match) =>
                renderMatchCard(match, { showReminder: !hasLiveMatches }),
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
