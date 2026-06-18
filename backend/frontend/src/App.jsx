import { useEffect, useMemo, useState } from "react";
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
  const [hasError, setHasError] = useState(false);
  const imageUrl = getFlagImageUrl(flagEmoji, teamName);

  useEffect(() => {
    setHasError(false);
  }, [imageUrl]);

  return (
    <span className="team-flag" aria-hidden="true">
      {imageUrl && !hasError ? (
        <img
          className="team-flag-img"
          src={imageUrl}
          alt=""
          loading="lazy"
          onError={() => setHasError(true)}
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
          src="/world-cup-2026-logo.png"
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
    upcoming: "بازی‌های پیش‌رو",
    past: "نتایج",
    news: "اخبار",
    profile: "پروفایل",
    vs: "مقابل",
    group: "گروه",
    stage: "مرحله",
    city: "شهر",
    stadium: "ورزشگاه",
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
    upcoming: "Upcoming",
    past: "Results",
    news: "News",
    profile: "Profile",
    vs: "vs",
    group: "Group",
    stage: "Stage",
    city: "City",
    stadium: "Stadium",
    viewAll: "View all",
    teams: "Teams",
    matches: "Matches",
    cities: "Cities",
  },
};

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
}) {
  const teamButtons = [homeTeam, awayTeam].filter(Boolean);
  const matchScore = getMatchScore(match);

  return (
    <article className="match-card">
      <div className="match-top">
        <span className="match-date">{match.date_iran}</span>
        <span className="match-stage">{match.stage_label || match.stage}</span>
      </div>

      <div className="teams">
        <strong className="team-name">
          <TeamFlag flagEmoji={match.home_flag} teamName={match.home_en} />
          {match.home_en}
        </strong>
        <span className={matchScore ? "match-score" : "match-vs"}>
          {matchScore || t.vs}
        </span>
        <strong className="team-name">
          <TeamFlag flagEmoji={match.away_flag} teamName={match.away_en} />
          {match.away_en}
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
        <div className="card-actions favorite-actions">
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
          onClick={() => onReminderToggle(match.id)}
        >
          {isReminderActive ? `🔕 ${t.cancelReminder}` : `🔔 ${t.remind}`}
        </button>
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
  const [lang, setLang] = useState("fa");
  const [activeTab, setActiveTab] = useState("home");
  const [telegramUser, setTelegramUser] = useState(null);
  const [isUserSaved, setIsUserSaved] = useState(false);

  const [upcomingMatches, setUpcomingMatches] = useState([]);
  const [pastMatches, setPastMatches] = useState([]);
  const [newsItems, setNewsItems] = useState([]);
  const [teams, setTeams] = useState([]);
  const [favoriteTeams, setFavoriteTeams] = useState([]);
  const [favoriteMessage, setFavoriteMessage] = useState("");
  const [reminders, setReminders] = useState([]);
  const [reminderMessage, setReminderMessage] = useState("");

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

  useEffect(() => {
    const tg = window.Telegram?.WebApp;

    if (tg) {
      tg.ready();
      tg.expand();

      const user = tg.initDataUnsafe?.user;

      if (user) {
        setTelegramUser(user);

        fetch(`${API_BASE_URL}/user`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            telegram_id: user.id,
            first_name: user.first_name || "",
            last_name: user.last_name || "",
            username: user.username || "",
            language_code: user.language_code || "",
          }),
        })
          .then((response) => response.json())
          .then((data) => {
            if (data.success) setIsUserSaved(true);
          })
          .catch((error) => console.error("Failed to save user:", error));

        fetch(`${API_BASE_URL}/favorite-teams/${user.id}`)
          .then((response) => response.json())
          .then((data) => setFavoriteTeams(data.favorite_teams || []))
          .catch((error) => console.error("Failed to load favorite teams:", error));

        fetch(`${API_BASE_URL}/reminders/${user.id}`)
          .then((response) => response.json())
          .then((data) => setReminders(data.reminders || []))
          .catch((error) => console.error("Failed to load reminders:", error));
      }
    }

    fetch(`${API_BASE_URL}/matches?status=upcoming`)
      .then((response) => response.json())
      .then((data) => setUpcomingMatches(data.matches || []))
      .catch((error) => console.error("Failed to load upcoming matches:", error));

    fetch(`${API_BASE_URL}/matches?status=past`)
      .then((response) => response.json())
      .then((data) => setPastMatches(data.matches || []))
      .catch((error) => console.error("Failed to load past matches:", error));

    fetch(`${API_BASE_URL}/news`)
      .then((response) => response.json())
      .then((data) => setNewsItems(data.news || []))
      .catch((error) => console.error("Failed to load news:", error));

    fetch(`${API_BASE_URL}/teams`)
      .then((response) => response.json())
      .then((data) => setTeams(data.teams || []))
      .catch((error) => console.error("Failed to load teams:", error));
  }, []);

  const toggleLang = () => {
    setLang((current) => (current === "fa" ? "en" : "fa"));
  };

  const addFavoriteTeam = (teamId) => {
    if (!telegramUser) return;

    fetch(`${API_BASE_URL}/favorite-team`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_id: telegramUser.id,
        team_id: teamId,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          setFavoriteTeams(data.favorite_teams || []);
          setFavoriteMessage(`✅ ${t.addedFavorite}`);
        }
      })
      .catch((error) => console.error("Failed to save favorite team:", error));
  };

  const removeFavoriteTeam = (teamId) => {
    if (!telegramUser) return;

    fetch(`${API_BASE_URL}/favorite-team`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_id: telegramUser.id,
        team_id: teamId,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          setFavoriteTeams(data.favorite_teams || []);
          setFavoriteMessage(`✅ ${t.removedFavorite}`);
        }
      })
      .catch((error) => console.error("Failed to remove favorite team:", error));
  };

  const toggleFavoriteTeam = (teamId) => {
    if (favoriteTeamIds.has(teamId)) {
      removeFavoriteTeam(teamId);
    } else {
      addFavoriteTeam(teamId);
    }
  };

  const addReminder = (matchId) => {
    if (!telegramUser) return;

    fetch(`${API_BASE_URL}/reminder`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_id: telegramUser.id,
        match_id: matchId,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          setReminders(data.reminders || []);
          setReminderMessage(`✅ ${t.addedReminder}`);
        }
      })
      .catch((error) => console.error("Failed to save reminder:", error));
  };

  const removeReminder = (matchId) => {
    if (!telegramUser) return;

    fetch(`${API_BASE_URL}/reminder`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_id: telegramUser.id,
        match_id: matchId,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          setReminders(data.reminders || []);
          setReminderMessage(`✅ ${t.removedReminder}`);
        }
      })
      .catch((error) => console.error("Failed to remove reminder:", error));
  };

  const toggleReminder = (matchId) => {
    if (reminderIds.has(matchId)) {
      removeReminder(matchId);
    } else {
      addReminder(matchId);
    }
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

  const nextMatch = upcomingMatches[0];

  const renderMatchCard = (match, options = {}) => {
    const { homeTeam, awayTeam } = getMatchTeams(match);

    return (
      <MatchCard
        key={match.id}
        match={match}
        t={t}
        onReminderToggle={toggleReminder}
        isReminderActive={reminderIds.has(match.id)}
        homeTeam={homeTeam}
        awayTeam={awayTeam}
        favoriteTeamIds={favoriteTeamIds}
        onFavoriteToggle={toggleFavoriteTeam}
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
          <span>{t.nextMatch}</span>
          {nextMatch ? (
            <div className="hero-next-match">
              <strong className="hero-next-team">
                <TeamFlag flagEmoji={nextMatch.home_flag} teamName={nextMatch.home_en} />
                {nextMatch.home_en}
              </strong>
              <b>{t.vs}</b>
              <strong className="hero-next-team">
                <TeamFlag flagEmoji={nextMatch.away_flag} teamName={nextMatch.away_en} />
                {nextMatch.away_en}
              </strong>
            </div>
          ) : (
            <strong>{t.loadingMatches}</strong>
          )}
          <small>
            {nextMatch ? `${nextMatch.date_iran} - ${nextMatch.time_iran}` : ""}
          </small>
        </div>
      </section>

      {activeTab === "home" && (
        <>
          <section className="quick-actions">
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
              <h2>{t.nextMatches}</h2>
              <span onClick={() => setActiveTab("upcoming")}>{t.viewAll}</span>
            </div>

            <div className="matches">
              {upcomingMatches.length === 0 && <p>{t.loadingMatches}</p>}
              {upcomingMatches.slice(0, 5).map((match) => renderMatchCard(match))}
            </div>

            {(reminderMessage || favoriteMessage) && (
              <p className="status-message">{reminderMessage || favoriteMessage}</p>
            )}
          </section>
        </>
      )}

      {activeTab === "upcoming" && (
        <section className="section">
          <div className="section-header">
            <h2>{t.nextMatches}</h2>
          </div>

          <div className="matches">
            {upcomingMatches.length === 0 && <p>{t.loadingMatches}</p>}
            {upcomingMatches.map((match) => renderMatchCard(match))}
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
            {pastMatches.length === 0 && <p>{t.loadingMatches}</p>}
            {pastMatches.map((match) => renderMatchCard(match, { showReminder: false }))}
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
