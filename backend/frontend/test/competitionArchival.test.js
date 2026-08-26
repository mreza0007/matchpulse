import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  competitionExperience,
  filterActiveCompetitionFavorites,
  groupActiveCompetitionFavorites,
  supportsNewCompetitionAction,
} from "../src/utils/competitionCapabilities.js";

const testDirectory = fileURLToPath(new URL(".", import.meta.url));
const source = (relativePath) => readFileSync(
  new URL(relativePath, `file:///${testDirectory.replaceAll("\\", "/")}`),
  "utf8",
);

test("World Cup advertises archived state and no new mutation capabilities", () => {
  const config = source("../src/config/competitions.js");
  const worldCupStart = config.indexOf("worldcup2026:");
  const worldCupEnd = config.indexOf("premier_league:", worldCupStart);
  const worldCup = config.slice(
    worldCupStart,
    worldCupEnd,
  );

  assert.match(worldCup, /status: "archived"/);
  assert.match(worldCup, /isActive: false/);
  assert.doesNotMatch(config, /supports(?:Archive|Favorites|Reminders|Predictions):/);
});

test("archived competition selection resolves to the archive experience", () => {
  const worldCupDirectoryEntry = {
    competition_key: "worldcup2026",
    is_active: false,
    status: "archived",
    supports_archive: true,
  };

  assert.equal(competitionExperience(worldCupDirectoryEntry), "archive");
  assert.equal(
    supportsNewCompetitionAction(worldCupDirectoryEntry, "supports_predictions"),
    false,
  );
});

test("archive page renders WorldCupArchive from the summary API only", () => {
  const archivePage = source("../src/pages/ArchivedCompetitionPage.jsx");

  assert.match(archivePage, /fetchWorldCupSummary/);
  assert.match(archivePage, /<WorldCupArchive/);
  assert.doesNotMatch(archivePage, /fetchCompetitionSeason(?:Matches|Teams)/);
  assert.match(archivePage, /"\\u2192" : "\\u2190"/);
  const hasUnexpectedControlCharacter = Array.from(
    archivePage,
    (character) => character.charCodeAt(0),
  ).some((codePoint) => codePoint < 32 && ![9, 10, 13].includes(codePoint));

  assert.equal(hasUnexpectedControlCharacter, false);
});

test("archived favorites are filtered from Profile without mutating stored records", () => {
  const storedFavorites = [
    {
      competition_key: "worldcup2026",
      team_id: "6",
      competition: {
        competition_key: "worldcup2026",
        is_active: false,
        status: "archived",
      },
    },
    {
      competition_key: "premier_league",
      team_id: "arsenal",
      competition: {
        competition_key: "premier_league",
        is_active: true,
        status: "active",
      },
    },
  ];

  const activeFavorites = filterActiveCompetitionFavorites(storedFavorites);

  assert.deepEqual(activeFavorites, [storedFavorites[1]]);
  assert.equal(storedFavorites.length, 2);
  assert.equal(storedFavorites[0].competition_key, "worldcup2026");
});

test("active favorites group deterministically by authoritative competition metadata", () => {
  const favorite = (competitionKey, competitionName, teamId, teamName) => ({
    competition_key: competitionKey,
    competition: {
      competition_key: competitionKey,
      is_active: true,
      name_en: competitionName,
      status: "active",
      supports_favorites: true,
    },
    team_id: teamId,
    team_name_en: teamName,
  });
  const groups = groupActiveCompetitionFavorites([
    favorite("premier_league", "Premier League", "6", "Shared Club"),
    favorite("la_liga", "La Liga", "6", "Shared Club"),
    favorite("premier_league", "Premier League", "7", "Another Club"),
  ], "en");

  assert.deepEqual(groups.map((group) => group.competitionKey), ["la_liga", "premier_league"]);
  assert.deepEqual(groups[1].favorites.map((item) => item.team_id), ["7", "6"]);
  assert.notEqual(groups[0].favorites[0].competition_key, groups[1].favorites[1].competition_key);
});

test("favorite UI actions consume authoritative competition capability metadata", () => {
  const app = source("../src/App.jsx");
  const competitionPage = source("../src/pages/CompetitionPage.jsx");
  const profilePage = source("../src/pages/ProfilePage.jsx");

  assert.match(
    competitionPage,
    /supportsNewCompetitionAction\(\s*competition, "supports_favorites",?\s*\)/,
  );
  assert.match(competitionPage, /onFavoriteToggle\(competition, team\)/);
  assert.doesNotMatch(competitionPage, /onFavoriteToggle\(competition\.competition_key/);
  assert.match(
    app,
    /supportsNewCompetitionAction\(competition, "supports_favorites"\)/,
  );
  assert.doesNotMatch(app, /isArchivedCompetition\(COMPETITIONS\[competitionKey\]\)/);
  assert.match(profilePage, /groupActiveCompetitionFavorites\(favoriteTeams, lang\)/);
  assert.doesNotMatch(profilePage, /config\/competitions/);
  assert.doesNotMatch(profilePage, /team_type === "club"|team_type === "national"/);
});

test("active competition routing and capabilities remain unchanged", () => {
  const activeCompetition = {
    competition_key: "premier_league",
    is_active: true,
    status: "active",
    supports_archive: false,
    supports_favorites: true,
    supports_predictions: true,
  };

  assert.equal(competitionExperience(activeCompetition), "active");
  assert.equal(
    supportsNewCompetitionAction(activeCompetition, "supports_favorites"),
    true,
  );
  assert.equal(
    supportsNewCompetitionAction(activeCompetition, "supports_predictions"),
    true,
  );
});
