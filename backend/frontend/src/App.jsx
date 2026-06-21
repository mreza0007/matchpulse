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

function normalizeMatchStatus(match) {
  if (match?.status === "live") return "live";
  if (match?.status === "finished") return "finished";
  return "upcoming";
}

function getMatchStatus(match, t) {
  const normalizedStatus = normalizeMatchStatus(match);

  if (normalizedStatus === "live") {
    return { key: "live", label: t.statusLive };
  }

  if (normalizedStatus === "finished") {
    return { key: "finished", label: t.statusFinished };
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
    noFavorites: "هنوز تیم محبوبی انتخاب نشده.",
    noReminders: "هنوز یادآور فعالی ثبت نشده.",
    unavailable: "نامشخص",
    home: "خانه",
    live: "زنده",
    upcoming: "بازی‌های پیش‌رو",
    past: "نتایج",
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
    matchEvents: "خط زمانی بازی",
    loadingEvents: "در حال دریافت رویدادها...",
    noEvents: "هنوز رویدادی ثبت نشده",
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
    unavailable: "Unavailable",
    home: "Home",
    live: "Live",
    upcoming: "Upcoming",
    past: "Results",
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
    matchEvents: "Match timeline",
    loadingEvents: "Loading timeline...",
    noEvents: "No events recorded yet",
    viewAll: "View all",
    teams: "Teams",
    matches: "Matches",
    cities: "Cities",
  },
};

const EVENT_LABELS = {
  fa: {
    goal: "\u06af\u0644",
    assist: "\u067e\u0627\u0633 \u06af\u0644",
    yellow_card: "\u06a9\u0627\u0631\u062a \u0632\u0631\u062f",
    red_card: "\u06a9\u0627\u0631\u062a \u0642\u0631\u0645\u0632",
    substitution: "\u062a\u0639\u0648\u06cc\u0636",
  },
  en: {
    goal: "Goal",
    assist: "Assist",
    yellow_card: "Yellow card",
    red_card: "Red card",
    substitution: "Substitution",
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

function getEventTeamLabel(team, lang) {
  if (lang === "fa") {
    if (team === "home") return "\u0645\u06cc\u0632\u0628\u0627\u0646";
    if (team === "away") return "\u0645\u0647\u0645\u0627\u0646";
  }

  if (team === "home") return "Home";
  if (team === "away") return "Away";
  return team || "";
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
  onFavoriteToggle,
  lang,
  onMatchClick,
  isExpanded = false,
  events = [],
  isLoadingEvents = false,
  isScoreChanged = false,
}) {
  const teamButtons = [homeTeam, awayTeam].filter(Boolean);
  const matchStatus = getMatchStatus(match, t);
  const isLive = match.status === "live";
  const matchScoreValue = getMatchScore(match);
  const matchScore =
    matchStatus.key === "upcoming"
      ? ""
      : matchScoreValue || (matchStatus.key === "live" ? "0 - 0" : "");
  const homeName = getLocalizedTeamName(match, "home", lang);
  const awayName = getLocalizedTeamName(match, "away", lang);
  const shouldShowScoreFallback = !matchScore && matchStatus.key === "finished";
  const handleCardClick = () => onMatchClick?.(match);
  const stopCardClick = (event) => event.stopPropagation();

  return (
    <article
      className={`match-card ${isLive ? "live-match" : ""} ${isExpanded ? "selected" : ""}`}
      onClick={handleCardClick}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          handleCardClick();
        }
      }}
      role="button"
      tabIndex={0}
    >
      <div className="match-top">
        <div className="match-top-main">
          <span className="match-date">{match.date_iran}</span>
          <span className="match-stage">{match.stage_label || match.stage}</span>
        </div>
        {isLive && <span className="match-status live live-pulse">{matchStatus.label}</span>}
      </div>

      <div className="teams">
        <strong className="team-name">
          <TeamFlag flagEmoji={match.home_flag} teamName={match.home_en} />
          {homeName}
        </strong>
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
        <strong className="team-name">
          <TeamFlag flagEmoji={match.away_flag} teamName={match.away_en} />
          {awayName}
        </strong>
      </div>

      <div className="match-meta-grid">
        <span>🕒 {match.time_iran}</span>
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

      {teamButtons.length > 0 && (
        <div className="card-actions favorite-actions" onClick={stopCardClick}>
          {teamButtons.map((team) => {
            const isFavorite = favoriteTeamIds.has(team.id);

            return (
              <button
                key={team.id}
                className={`chip-btn ${isFavorite ? "active" : ""}`}
                onClick={() => onFavoriteToggle(team.id)}
              >
                <span>{isFavorite ? "★" : "☆"}</span>
                {team.emoji} {isFavorite ? t.removeFavorite : t.addFavorite}
              </button>
            );
          })}
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

      {isExpanded && (
        <div className="match-events" onClick={stopCardClick}>
          <h3>{t.matchEvents}</h3>
          {isLoadingEvents ? (
            <p>{t.loadingEvents}</p>
          ) : events.length > 0 ? (
            <ol className="event-timeline">
              {events.map((event, index) => (
                <li
                  className={`event-row ${event.type || ""}`}
                  key={`${event.minute}-${event.type}-${event.player}-${event.team}-${index}`}
                >
                  <span className="event-minute">{event.minute ?? ""}'</span>
                  <span className="event-icon" aria-hidden="true">
                    {getEventIcon(event.type)}
                  </span>
                  <strong>{getEventTypeLabel(event.type, lang)}</strong>
                  <span className="event-player">{event.player || ""}</span>
                  <small>{getEventTeamLabel(event.team, lang)}</small>
                </li>
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
        onClick={() => onToggle(team.id)}
      >
        <span>{isFavorite ? "★" : "☆"}</span>
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
  const [isUserSaved] = useState(Boolean(initialTelegramUser));

  const [matches, setMatches] = useState([]);
  const [newsItems] = useState([]);
  const [teams] = useState([]);
  const [favoriteTeams, setFavoriteTeams] = useState([]);
  const [favoriteMessage, setFavoriteMessage] = useState("");
  const [reminders, setReminders] = useState([]);
  const [reminderMessage, setReminderMessage] = useState("");
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [matchEventsById, setMatchEventsById] = useState({});
  const [loadingEventsId, setLoadingEventsId] = useState(null);
  const [scoreChangedMatchIds, setScoreChangedMatchIds] = useState(() => new Set());
  const scoreChangeTimeouts = useRef(new Map());

  const t = translations[lang];

  const favoriteTeamIds = useMemo(
    () => new Set(favoriteTeams.map((team) => team.id)),
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

  const liveMatches = useMemo(
    () => matches.filter((match) => match.status === "live"),
    [matches],
  );

  const upcomingOnlyMatches = useMemo(
    () => matches.filter((match) => normalizeMatchStatus(match) === "upcoming"),
    [matches],
  );

  const pastOnlyMatches = useMemo(
    () => matches.filter((match) => normalizeMatchStatus(match) === "finished"),
    [matches],
  );

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

    const loadMatches = () => fetch(`${API_BASE_URL}/matches`)
      .then((response) => response.json())
      .then((data) => updateMatches(data.matches || []))
      .catch((error) => console.error("Failed to load matches:", error));

    loadMatches();
    const matchRefresh = window.setInterval(loadMatches, 30000);

    return () => {
      window.clearInterval(matchRefresh);
      scoreTimeouts.forEach((timeout) => window.clearTimeout(timeout));
      scoreTimeouts.clear();
    };
  }, []);

  const toggleLang = () => {
    setLang((current) => (current === "fa" ? "en" : "fa"));
  };

  const addFavoriteTeam = (teamId) => {
    setFavoriteTeams((current) => current.filter((team) => team.id !== teamId));
    setFavoriteMessage(t.unavailable);
  };

  const removeFavoriteTeam = (teamId) => {
    setFavoriteTeams((current) => current.filter((team) => team.id !== teamId));
    setFavoriteMessage(t.unavailable);
  };

  const toggleFavoriteTeam = (teamId) => {
    if (favoriteTeamIds.has(teamId)) {
      removeFavoriteTeam(teamId);
    } else {
      addFavoriteTeam(teamId);
    }
  };

  const addReminder = (matchId) => {
    setReminders((current) => current.filter((match) => match.id !== matchId));
    setReminderMessage(t.unavailable);
  };

  const removeReminder = (matchId) => {
    setReminders((current) => current.filter((match) => match.id !== matchId));
    setReminderMessage(t.unavailable);
  };

  const toggleReminder = (matchId) => {
    if (reminderIds.has(matchId)) {
      removeReminder(matchId);
    } else {
      addReminder(matchId);
    }
  };

  const handleMatchClick = (match) => {
    if (!match?.id) return;

    setSelectedMatchId((currentId) => (currentId === match.id ? null : match.id));

    if (matchEventsById[match.id]) return;

    setLoadingEventsId(match.id);
    fetch(`${API_BASE_URL}/match/${match.id}/events`)
      .then((response) => response.json())
      .then((data) => {
        setMatchEventsById((currentEvents) => ({
          ...currentEvents,
          [match.id]: Array.isArray(data.events) ? data.events : [],
        }));
      })
      .catch((error) => console.error("Failed to load match events:", error))
      .finally(() => setLoadingEventsId(null));
  };

  const getMatchTeams = (match) => ({
    homeTeam: teamsByName.get(match.home_en),
    awayTeam: teamsByName.get(match.away_en),
  });

  const profileName = telegramUser
    ? `${telegramUser.first_name || ""} ${telegramUser.last_name || ""}`.trim()
    : t.profileTitle;

  const profileUsername = telegramUser?.username
    ? `@${telegramUser.username}`
    : t.noUsername;

  const nextMatch = upcomingOnlyMatches[0];
  const hasLiveMatches = liveMatches.length > 0;
  const homeFeaturedMatches = hasLiveMatches ? liveMatches : nextMatch ? [nextMatch] : [];
  const featuredMatch = homeFeaturedMatches[0];
  const homeFeaturedTitle = hasLiveMatches ? t.liveMatches : t.nextMatch;
  const homeFeaturedTab = hasLiveMatches ? "live" : "upcoming";

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
        onFavoriteToggle={toggleFavoriteTeam}
        onMatchClick={handleMatchClick}
        isExpanded={selectedMatchId === match.id}
        events={matchEventsById[match.id] || []}
        isLoadingEvents={loadingEventsId === match.id}
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
          {featuredMatch ? (
            <div className="hero-next-match">
              <strong className="hero-next-team">
                <TeamFlag flagEmoji={featuredMatch.home_flag} teamName={featuredMatch.home_en} />
                {getLocalizedTeamName(featuredMatch, "home", lang)}
              </strong>
              <b>
                {hasLiveMatches ? getMatchScore(featuredMatch) || "0 - 0" : t.vs}
              </b>
              <strong className="hero-next-team">
                <TeamFlag flagEmoji={featuredMatch.away_flag} teamName={featuredMatch.away_en} />
                {getLocalizedTeamName(featuredMatch, "away", lang)}
              </strong>
            </div>
          ) : (
            <strong>{t.loadingMatches}</strong>
          )}
          <small>
            {featuredMatch ? `${featuredMatch.date_iran} - ${featuredMatch.time_iran}` : ""}
          </small>
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
              {homeFeaturedMatches.length === 0 && <p>{t.loadingMatches}</p>}
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
            {liveMatches.length === 0 && <p>{t.loadingMatches}</p>}
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
            {upcomingOnlyMatches.length === 0 && <p>{t.loadingMatches}</p>}
            {upcomingOnlyMatches.map((match) => renderMatchCard(match))}
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
            {pastOnlyMatches.length === 0 && <p>{t.loadingMatches}</p>}
            {pastOnlyMatches.map((match) => renderMatchCard(match, { showReminder: false }))}
          </div>
        </section>
      )}

      {activeTab === "news" && (
        <section className="section">
          <div className="section-header">
            <h2>{t.latestNews}</h2>
          </div>

          <div className="news-list">
            {newsItems.length === 0 && <p>{t.loadingNews}</p>}
            {newsItems.map((item) => (
              <NewsCard key={item.id} item={item} lang={lang} />
            ))}
          </div>
        </section>
      )}

      {activeTab === "favorites" && (
        <section className="section">
          <div className="section-header">
            <h2>{t.chooseFavorite}</h2>
          </div>

          {favoriteMessage && <p className="status-message">{favoriteMessage}</p>}

          <div className="news-list">
            {teams.length === 0 && <p>{t.loadingTeams}</p>}
            {teams.map((team) => (
              <TeamCard
                key={team.id}
                team={team}
                lang={lang}
                t={t}
                isFavorite={favoriteTeamIds.has(team.id)}
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
                  <span>{team.emoji}</span>
                  <div className="profile-item-text">
                    <strong>{lang === "fa" ? team.name_fa : team.name_en}</strong>
                  </div>
                  <button
                    className="chip-btn profile-remove-btn"
                    onClick={() => removeFavoriteTeam(team.id)}
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
              {reminders.map((match) => (
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
                    <small>
                      {match.date_iran} - {match.time_iran}
                    </small>
                  </div>
                  <button
                    className="chip-btn profile-remove-btn"
                    onClick={() => removeReminder(match.id)}
                  >
                    {t.cancelReminder}
                  </button>
                </div>
              ))}
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
