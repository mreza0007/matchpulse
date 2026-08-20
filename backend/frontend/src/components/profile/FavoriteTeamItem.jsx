function favoriteName(team, lang) {
  if (lang === "fa") {
    return team.team_name_fa || team.name_fa || team.team_name || team.team_name_en || team.name_en || "";
  }
  return team.team_name_en || team.name_en || team.team_name || team.team_name_fa || team.name_fa || "";
}

export default function FavoriteTeamItem({ favorite, isRemoving, lang, onRemove, t }) {
  const name = favoriteName(favorite, lang);
  const logo = favorite.team_logo || favorite.logo || "";
  const flag = favorite.team_flag || favorite.flag || favorite.emoji || "";
  const showImage = typeof logo === "string" && logo.length > 0;
  const showFlag = !showImage && typeof flag === "string" && flag.length > 0 && !flag.startsWith("http");

  return (
    <div className={`profile-favorite-item ${favorite.resolved === false ? "unresolved" : ""}`}>
      <div className="profile-favorite-media" aria-hidden="true">
        {showImage && <img src={logo} alt="" />}
        {showFlag && <span>{flag}</span>}
      </div>
      <div className="profile-item-text">
        {favorite.resolved === false || !name ? (
          <strong>{t.favoriteUnavailableTeam}</strong>
        ) : (
          <strong>{name}</strong>
        )}
        {favorite.resolved === false && <small>{t.favoriteUnresolvedHint}</small>}
      </div>
      <button
        className="chip-btn profile-remove-btn"
        disabled={isRemoving}
        onClick={() => onRemove(favorite)}
        type="button"
      >
        {isRemoving ? t.favoriteRemoving : t.removeFavorite}
      </button>
    </div>
  );
}
