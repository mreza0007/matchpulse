export function isArchivedCompetition(competition) {
  return competition?.status === "archived" || competition?.is_active === false;
}

export function competitionExperience(competition) {
  if (isArchivedCompetition(competition) && competition?.supports_archive === true) {
    return "archive";
  }
  return "active";
}

export function supportsNewCompetitionAction(competition, capability) {
  return !isArchivedCompetition(competition) && competition?.[capability] === true;
}

export function filterActiveCompetitionFavorites(favorites, competitionByKey) {
  return favorites.filter((favorite) => (
    !isArchivedCompetition(competitionByKey[favorite.competition_key])
  ));
}
