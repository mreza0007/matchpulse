import TeamFlag from "../teams/TeamFlag.jsx";
import { favoriteCompetitionName, favoriteDisplayName } from "../../utils/favorites.js";

export default function FavoriteTeamItem({ favorite, isRemoving, lang, onRemove, t }) {
  const name = favoriteDisplayName(favorite, lang);
  const displayName = favorite.resolved === false || !name ? t.favoriteUnavailableTeam : name;
  const competitionName = favoriteCompetitionName(favorite, lang) || t.unavailable;
  const logo = favorite.team_logo || favorite.logo || "";
  const flag = favorite.team_flag || favorite.flag || favorite.emoji || "";

  return (
    <div className={`profile-favorite-item ${favorite.resolved === false ? "unresolved" : ""}`}>
      <div className="profile-favorite-media" aria-hidden="true">
        <TeamFlag flagEmoji={flag} logoUrl={logo} teamName={name} />
      </div>
      <div className="profile-favorite-text">
        <strong><bdi>{displayName}</bdi></strong>
        <small><bdi>{competitionName}</bdi></small>
        {favorite.resolved === false && <small>{t.favoriteUnresolvedHint}</small>}
      </div>
      <button
        className="chip-btn profile-favorite-remove"
        aria-label={`${t.removeFavorite}: ${displayName}`}
        title={`${t.removeFavorite}: ${displayName}`}
        aria-busy={isRemoving}
        disabled={isRemoving}
        onClick={() => onRemove(favorite)}
        type="button"
      >
        <span aria-hidden="true">{isRemoving ? "…" : "×"}</span>
      </button>
    </div>
  );
}
