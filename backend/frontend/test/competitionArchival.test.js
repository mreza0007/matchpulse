import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  competitionExperience,
  filterActiveCompetitionFavorites,
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
    { competition_key: "worldcup2026", team_id: "6", team_type: "national" },
    { competition_key: "premier_league", team_id: "arsenal", team_type: "club" },
  ];

  const competitionByKey = {
    worldcup2026: { status: "archived" },
    premier_league: { status: "active" },
  };
  const activeFavorites = filterActiveCompetitionFavorites(storedFavorites, competitionByKey);

  assert.deepEqual(activeFavorites, [storedFavorites[1]]);
  assert.equal(storedFavorites.length, 2);
  assert.equal(storedFavorites[0].competition_key, "worldcup2026");
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
