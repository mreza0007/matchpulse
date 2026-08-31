import FavoriteTeamItem from "../components/profile/FavoriteTeamItem.jsx";
import TeamFlag from "../components/teams/TeamFlag.jsx";
import { groupActiveCompetitionFavorites } from "../utils/competitionCapabilities.js";
import { formatTehranMatchDateTime } from "../utils/dates.js";
import { reminderIdentityKeyFromRecord } from "../utils/reminders.js";
import { getLocalizedTeamName } from "../utils/teams.js";

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
  reminderMessage,
  reminderPendingKeys,
  t,
  telegramUser,
}) {
  const profileName = telegramUser
    ? `${telegramUser.first_name || ""} ${telegramUser.last_name || ""}`.trim()
    : t.profileTitle;
  const profileUsername = telegramUser?.username ? `@${telegramUser.username}` : t.noUsername;
  const favoriteGroups = groupActiveCompetitionFavorites(favoriteTeams, lang);
  const activeFavoriteCount = favoriteGroups.reduce(
    (count, group) => count + group.favorites.length, 0,
  );
  const isPending = (favorite) => favoritePendingKeys.has(
    `${favorite.competition_key}:${String(favorite.team_id)}`,
  );
  const hasActiveUnresolvedFavorite = favoriteGroups.some((group) => (
    group.favorites.some((favorite) => favorite.resolved === false)
  ));
  const showResolutionNotice = hasActiveUnresolvedFavorite && (
    favoriteMeta.resolutionErrors > 0 || favoriteMeta.unresolvedCount > 0
  );

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
            <span>{activeFavoriteCount}</span>
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
          {favoriteStatus === "ready" && activeFavoriteCount === 0 && <p>{t.noFavorites}</p>}

          {favoriteGroups.map((group) => (
            <FavoriteGroup
              favorites={group.favorites}
              isPending={isPending}
              key={group.competitionKey}
              lang={lang}
              onRemove={onRemoveFavorite}
              t={t}
              title={group.title}
            />
          ))}
        </div>

        <div className="profile-list">
          <div className="profile-list-header">
            <h3>🔔 {t.activeReminders}</h3>
            <span>{reminders.length}</span>
          </div>
          {reminders.length === 0 && <p>{t.noReminders}</p>}
          {reminderMessage && <p className="status-message">{reminderMessage}</p>}
          {reminders.map((match, index) => {
            const reminderDateTime = formatTehranMatchDateTime(match, lang);
            const identityKey = reminderIdentityKeyFromRecord(match);
            const reminderKey = identityKey || `malformed-reminder:${index}`;
            const isReminderPending = Boolean(identityKey && reminderPendingKeys.has(identityKey));
            const homeName = getLocalizedTeamName(match, "home", lang);
            const awayName = getLocalizedTeamName(match, "away", lang);
            const competitionContext = [
              String(match?.competition_key || "").replaceAll("_", " "),
              match?.season_key,
            ].filter(Boolean).join(" · ");
            return (
              <div className="profile-item reminder-item" key={reminderKey}>
                <TeamFlag flagEmoji={match?.home_flag} teamName={homeName} />
                <div className="profile-item-text">
                  <strong>
                    <span className="profile-reminder-match">
                      {homeName}
                      <span>{t.vs}</span>
                      <TeamFlag flagEmoji={match?.away_flag} teamName={awayName} />
                      {awayName}
                    </span>
                  </strong>
                  <small>{competitionContext}</small>
                  <small>{reminderDateTime.compact}</small>
                </div>
                {canRemoveReminders && (
                  <button
                    className="chip-btn profile-remove-btn"
                    disabled={!identityKey || isReminderPending}
                    onClick={() => onRemoveReminder(match)}
                    type="button"
                  >
                    {isReminderPending ? t.reminderSaving : t.cancelReminder}
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
