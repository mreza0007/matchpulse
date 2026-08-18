function profileInitials(user) {
  const initials = [user?.first_name, user?.last_name]
    .filter(Boolean)
    .map((value) => String(value).trim().charAt(0))
    .join("");
  return initials || "MP";
}

export default function AppHeader({ telegramUser, onProfileOpen, onToggleLanguage, langButton }) {
  return (
    <header className="app-shell-header">
      <div className="app-shell-brand" aria-label="MatchPulse">
        <span className="app-shell-brand-mark" aria-hidden="true">MP</span>
        <strong>MatchPulse</strong>
      </div>

      <div className="app-shell-actions">
        <button className="header-lang-btn" onClick={onToggleLanguage} type="button">
          {langButton}
        </button>
        <button
          aria-disabled="true"
          aria-label="جستجو"
          className="header-icon-btn"
          title="جستجو"
          type="button"
        >
          ⌕
        </button>
        <button
          aria-label="پروفایل"
          className="header-profile-btn"
          onClick={onProfileOpen}
          type="button"
        >
          {telegramUser?.photo_url ? (
            <img src={telegramUser.photo_url} alt="" />
          ) : (
            <span>{profileInitials(telegramUser)}</span>
          )}
        </button>
      </div>
    </header>
  );
}
