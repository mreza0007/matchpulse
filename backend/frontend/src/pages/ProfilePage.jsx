import FavoriteTeamItem from "../components/profile/FavoriteTeamItem.jsx";
import TeamFlag from "../components/teams/TeamFlag.jsx";
import { formatTehranMatchDateTime } from "../utils/dates.js";

function FavoriteGroup({ favorites, isPending, lang, onRemove, t, title }) {
  return (
    <section className="profile-favorite-group">
      <div className="profile-favorite-group-heading">
        <h4>{title}</h4>
        <span>{favorites.length}</span>
      </div>
      {favorites.map((favorite) => (
        <FavoriteTeamItem
          favorite={favorite}
          isRemoving={isPending(favorite)}
          key={`${favorite.competition_key}:${String(favorite.team_id)}`}
          lang={lang}
          onRemove={onRemove}
          t={t}
        />
      ))}
    </section>
  );
}

export default function ProfilePage({
  canRemoveReminders,
  favoriteMessage,
  favoriteMeta,
  favoritePendingKeys,
  favoriteStatus,
  favoriteTeams,
  isUserSaved,
  lang,
  onRemoveFavorite,
  onRemoveReminder,
  predictionStats,
  reminders,
  t,
  telegramUser,
}) {
  const profileName = telegramUser
    ? `${telegramUser.first_name || ""} ${telegramUser.last_name || ""}`.trim()
    : t.profileTitle;
  const profileUsername = telegramUser?.username ? `@${telegramUser.username}` : t.noUsername;
  const clubFavorites = favoriteTeams.filter((team) => team.team_type === "club");
  const nationalFavorites = favoriteTeams.filter((team) => team.team_type === "national");
  const otherFavorites = favoriteTeams.filter(
    (team) => team.team_type !== "club" && team.team_type !== "national",
  );
  const isPending = (favorite) => favoritePendingKeys.has(
    `${favorite.competition_key}:${String(favorite.team_id)}`,
  );
  const showResolutionNotice = favoriteMeta.resolutionErrors > 0 || favoriteMeta.unresolvedCount > 0;

  return (
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

        <div className="profile-list profile-favorites-v2">
          <div className="profile-list-header">
            <h3>⭐ {t.favoriteTeams}</h3>
            <span>{favoriteTeams.length}</span>
          </div>

          {!telegramUser && <p>{t.favoriteIdentityRequired}</p>}
          {telegramUser && favoriteStatus === "loading" && <p>{t.favoriteLoading}</p>}
          {telegramUser && favoriteStatus === "migration" && (
            <p className="profile-favorite-error">{t.favoriteMigrationRequired}</p>
          )}
          {telegramUser && favoriteStatus === "provider" && (
            <p className="profile-favorite-error">{t.favoriteProviderError}</p>
          )}
          {telegramUser && favoriteStatus === "error" && (
            <p className="profile-favorite-error">{t.favoriteLoadError}</p>
          )}
          {favoriteMessage && <p className="status-message">{favoriteMessage}</p>}
          {showResolutionNotice && (
            <p className="profile-favorite-notice">{t.favoriteResolutionNotice}</p>
          )}
          {favoriteStatus === "ready" && favoriteTeams.length === 0 && <p>{t.noFavorites}</p>}

          {clubFavorites.length > 0 && (
            <FavoriteGroup
              favorites={clubFavorites}
              isPending={isPending}
              lang={lang}
              onRemove={onRemoveFavorite}
              t={t}
              title={t.favoriteClubTeams}
            />
          )}
          {nationalFavorites.length > 0 && (
            <FavoriteGroup
              favorites={nationalFavorites}
              isPending={isPending}
              lang={lang}
              onRemove={onRemoveFavorite}
              t={t}
              title={t.favoriteNationalTeams}
            />
          )}
          {otherFavorites.length > 0 && (
            <FavoriteGroup
              favorites={otherFavorites}
              isPending={isPending}
              lang={lang}
              onRemove={onRemoveFavorite}
              t={t}
              title={t.favoriteOtherTeams}
            />
          )}
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
                {canRemoveReminders && (
                  <button
                    className="chip-btn profile-remove-btn"
                    onClick={() => onRemoveReminder(match.id)}
                    type="button"
                  >
                    {t.cancelReminder}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </article>
    </section>
  );
}
