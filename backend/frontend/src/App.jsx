import { useEffect, useState } from "react";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000";

const translations = {
  fa: {
    dir: "rtl",
    langButton: "English",
    worldCup: "جام جهانی ۲۰۲۶",
    title: "MatchPulse",
    subtitle: "برنامه بازی‌ها، یادآورها، اخبار و مسابقه‌های فوتبالی در تلگرام.",
    nextMatch: "بازی بعدی",
    nextMatches: "بازی‌های نزدیک",
    pastMatches: "بازی‌های گذشته",
    latestNews: "آخرین اخبار",
    favorites: "⭐ تیم‌های محبوب",
    chooseFavorite: "تیم محبوبت را انتخاب کن",
    favoriteTeams: "تیم‌های محبوب",
    addedFavorite: "به تیم‌های محبوب اضافه شد",
    addedReminder: "یادآور مسابقه ذخیره شد",
    activeReminders: "یادآورهای فعال",
    profileTitle: "پروفایل من",
    profileText: "اینجا تیم‌های محبوب و یادآورها نمایش داده می‌شود.",
    telegramUser: "کاربر تلگرام",
    noUsername: "بدون یوزرنیم",
    saved: "کاربر در بک‌اند ذخیره شد",
    notSaved: "هنوز در بک‌اند ذخیره نشده",
    loadingMatches: "در حال دریافت بازی‌ها...",
    loadingNews: "در حال دریافت اخبار...",
    loadingTeams: "در حال دریافت تیم‌ها...",
    remind: "یادآوری ۱ ساعت قبل",
    home: "خانه",
    upcoming: "آینده",
    past: "گذشته",
    news: "اخبار",
    profile: "پروفایل",
    vs: "مقابل",
    group: "گروه",
    stage: "مرحله",
    city: "شهر",
    stadium: "ورزشگاه",
  },
  en: {
    dir: "ltr",
    langButton: "فارسی",
    worldCup: "World Cup 2026",
    title: "MatchPulse",
    subtitle: "Fixtures, reminders, news and football alerts inside Telegram.",
    nextMatch: "Next Match",
    nextMatches: "Upcoming Matches",
    pastMatches: "Past Matches",
    latestNews: "Latest News",
    favorites: "⭐ Favorite Teams",
    chooseFavorite: "Choose your favorite team",
    favoriteTeams: "Favorite Teams",
    addedFavorite: "Added to favorite teams",
    addedReminder: "Match reminder saved",
    activeReminders: "Active Reminders",
    profileTitle: "My Profile",
    profileText: "Favorite teams and reminders will appear here.",
    telegramUser: "Telegram User",
    noUsername: "No username",
    saved: "User saved in backend",
    notSaved: "Not saved in backend yet",
    loadingMatches: "Loading matches...",
    loadingNews: "Loading news...",
    loadingTeams: "Loading teams...",
    remind: "Remind me 1 hour before",
    home: "Home",
    upcoming: "Upcoming",
    past: "Past",
    news: "News",
    profile: "Profile",
    vs: "vs",
    group: "Group",
    stage: "Stage",
    city: "City",
    stadium: "Stadium",
  },
};

function MatchCard({ match, t, showReminder = true, onReminder }) {
  return (
    <article className="match-card">
      <div className="match-top">
        <span>{match.date_iran}</span>
        <span>{match.stage_label || match.stage}</span>
      </div>

      <div className="teams">
        <strong>
          {match.home_flag} {match.home_en}
        </strong>
        <span>{t.vs}</span>
        <strong>
          {match.away_flag} {match.away_en}
        </strong>
      </div>

      <div className="match-info">
        <span>🕒 {match.time_iran}</span>
        {match.group && <span>🏆 {t.group} {match.group}</span>}
      </div>

      <div className="match-info">
        <span>🏟 {match.stadium}</span>
      </div>

      <div className="match-info">
        <span>📍 {match.city}</span>
      </div>

      {match.result && (
        <div className="match-info">
          <span>📊 {match.result}</span>
        </div>
      )}

      {showReminder && (
        <button className="remind-btn" onClick={() => onReminder(match.id)}>
          {t.remind}
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

function TeamCard({ team, lang, onAdd }) {
  return (
    <article className="news-card">
      <span>{team.emoji}</span>
      <h3>{lang === "fa" ? team.name_fa : team.name_en}</h3>
      <button className="remind-btn" onClick={() => onAdd(team.id)}>
        ⭐
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

  const profileName = telegramUser
    ? `${telegramUser.first_name || ""} ${telegramUser.last_name || ""}`.trim()
    : t.profileTitle;

  const profileUsername = telegramUser?.username
    ? `@${telegramUser.username}`
    : t.noUsername;

  const nextMatch = upcomingMatches[0];

  return (
    <main className={`app ${lang}`} dir={t.dir}>
      <section className="hero">
        <button className="lang-btn" onClick={toggleLang}>
          {t.langButton}
        </button>

        <div>
          <p className="eyebrow">{t.worldCup}</p>
          <h1>{t.title}</h1>
          <p className="subtitle">{t.subtitle}</p>
        </div>

        <div className="stats-row">
          <div>
            <strong>{lang === "fa" ? "۴۸" : "48"}</strong>
            <span>{lang === "fa" ? "تیم" : "Teams"}</span>
          </div>
          <div>
            <strong>{lang === "fa" ? "۱۰۴" : "104"}</strong>
            <span>{lang === "fa" ? "بازی" : "Matches"}</span>
          </div>
          <div>
            <strong>{lang === "fa" ? "۱۶" : "16"}</strong>
            <span>{lang === "fa" ? "شهر" : "Cities"}</span>
          </div>
        </div>

        <div className="hero-card">
          <span>{t.nextMatch}</span>
          <strong>
            {nextMatch
              ? `${nextMatch.home_flag} ${nextMatch.home_en} ${t.vs} ${nextMatch.away_flag} ${nextMatch.away_en}`
              : t.loadingMatches}
          </strong>
          <small>
            {nextMatch ? `${nextMatch.date_iran} - ${nextMatch.time_iran}` : ""}
          </small>
        </div>
      </section>

      {activeTab === "home" && (
        <>
          <section className="quick-actions">
            <button onClick={() => setActiveTab("upcoming")}>{t.nextMatches}</button>
            <button onClick={() => setActiveTab("past")}>{t.pastMatches}</button>
            <button onClick={() => setActiveTab("favorites")}>{t.favorites}</button>
          </section>

          <section className="section">
            <div className="section-header">
              <h2>{t.nextMatches}</h2>
              <span onClick={() => setActiveTab("upcoming")}>
                {lang === "fa" ? "مشاهده همه" : "View all"}
              </span>
            </div>

            <div className="matches">
              {upcomingMatches.length === 0 && <p>{t.loadingMatches}</p>}

              {upcomingMatches.slice(0, 5).map((match) => (
                <MatchCard
                  key={match.id}
                  match={match}
                  t={t}
                  onReminder={addReminder}
                />
              ))}
            </div>

            {reminderMessage && <p>{reminderMessage}</p>}
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

            {upcomingMatches.map((match) => (
              <MatchCard
                key={match.id}
                match={match}
                t={t}
                onReminder={addReminder}
              />
            ))}
          </div>

          {reminderMessage && <p>{reminderMessage}</p>}
        </section>
      )}

      {activeTab === "past" && (
        <section className="section">
          <div className="section-header">
            <h2>{t.pastMatches}</h2>
          </div>

          <div className="matches">
            {pastMatches.length === 0 && <p>{t.loadingMatches}</p>}

            {pastMatches.map((match) => (
              <MatchCard
                key={match.id}
                match={match}
                t={t}
                showReminder={false}
                onReminder={addReminder}
              />
            ))}
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

          {favoriteMessage && <p>{favoriteMessage}</p>}

          <div className="news-list">
            {teams.length === 0 && <p>{t.loadingTeams}</p>}

            {teams.map((team) => (
              <TeamCard
                key={team.id}
                team={team}
                lang={lang}
                onAdd={addFavoriteTeam}
              />
            ))}
          </div>
        </section>
      )}

      {activeTab === "profile" && (
        <section className="section">
          <article className="profile-card">
            <div className="avatar">⚽</div>

            <h2>{profileName || t.telegramUser}</h2>
            <p>{telegramUser ? profileUsername : t.profileText}</p>

            {telegramUser && (
              <p>{isUserSaved ? `✅ ${t.saved}` : `⏳ ${t.notSaved}`}</p>
            )}

            <p>⭐ {t.favoriteTeams}: {favoriteTeams.length}</p>

            {favoriteTeams.map((team) => (
              <p key={team.id}>
                {team.emoji} {lang === "fa" ? team.name_fa : team.name_en}
              </p>
            ))}

            <p>🔔 {t.activeReminders}: {reminders.length}</p>

            {reminders.map((match) => (
              <p key={match.id}>
                {match.home_flag} {match.home_en} {t.vs} {match.away_flag}{" "}
                {match.away_en} - {match.date_iran} {match.time_iran}
              </p>
            ))}
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