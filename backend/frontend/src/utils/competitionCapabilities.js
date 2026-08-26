export function isArchivedCompetition(competition) {
  return competition?.status === "archived" || competition?.is_active === false;
}

export function isActiveCompetition(competition) {
  return (
    competition?.status === "active"
    && competition?.is_active === true
    && !isArchivedCompetition(competition)
  );
}

export function competitionExperience(competition) {
  if (isArchivedCompetition(competition) && competition?.supports_archive === true) {
    return "archive";
  }
  return "active";
}

export function supportsNewCompetitionAction(competition, capability) {
  return isActiveCompetition(competition) && competition?.[capability] === true;
}

function favoriteCompetition(favorite) {
  const competition = favorite?.competition;
  if (
    !competition
    || competition.competition_key !== favorite.competition_key
  ) {
    return null;
  }
  return competition;
}

function favoriteName(favorite) {
  return (
    favorite.team_name_en
    || favorite.name_en
    || favorite.team_name
    || favorite.team_name_fa
    || favorite.name_fa
    || String(favorite.team_id)
  );
}

function competitionName(competition, lang) {
  if (lang === "fa") return competition.name_fa || competition.name_en;
  return competition.name_en || competition.name_fa;
}

export function filterActiveCompetitionFavorites(favorites) {
  return favorites.filter((favorite) => (
    isActiveCompetition(favoriteCompetition(favorite))
  ));
}

export function groupActiveCompetitionFavorites(favorites, lang) {
  const groupsByKey = new Map();

  for (const favorite of filterActiveCompetitionFavorites(favorites)) {
    const competition = favoriteCompetition(favorite);
    const key = competition.competition_key;
    if (!groupsByKey.has(key)) {
      groupsByKey.set(key, {
        competition,
        competitionKey: key,
        favorites: [],
        title: competitionName(competition, lang) || key,
      });
    }
    groupsByKey.get(key).favorites.push(favorite);
  }

  const locale = lang === "fa" ? "fa" : "en";
  for (const group of groupsByKey.values()) {
    group.favorites.sort((left, right) => (
      favoriteName(left).localeCompare(favoriteName(right), locale)
      || String(left.team_id).localeCompare(String(right.team_id))
    ));
  }

  return [...groupsByKey.values()].sort((left, right) => (
    left.title.localeCompare(right.title, locale)
    || left.competitionKey.localeCompare(right.competitionKey)
  ));
}
