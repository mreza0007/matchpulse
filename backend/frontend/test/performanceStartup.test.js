import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const testDirectory = fileURLToPath(new URL(".", import.meta.url));
const source = (relativePath) => readFileSync(
  new URL(relativePath, `file:///${testDirectory.replaceAll("\\", "/")}`),
  "utf8",
);

const effectContaining = (app, marker) => {
  const markerIndex = app.indexOf(marker);
  assert.notEqual(markerIndex, -1, `missing marker: ${marker}`);
  const effectStart = app.lastIndexOf("useEffect(() => {", markerIndex);
  const effectEnd = app.indexOf("\n  }, [", markerIndex);
  assert.notEqual(effectStart, -1, `missing effect start for: ${marker}`);
  assert.notEqual(effectEnd, -1, `missing effect end for: ${marker}`);
  return app.slice(effectStart, effectEnd);
};

test("current navigation excludes legacy match tabs from startup", () => {
  const app = source("../src/App.jsx");
  const bottomNav = source("../src/components/layout/BottomNav.jsx");
  const matchEffect = effectContaining(app, "fetchCompetitionMatches(selectedCompetition");

  assert.match(app, /const LEGACY_MATCH_TABS = new Set\(\["upcoming", "past"\]\)/);
  assert.match(app, /const shouldLoadLegacyMatches = LEGACY_MATCH_TABS\.has\(activeTab\)/);
  assert.match(matchEffect, /if \(!shouldLoadLegacyMatches\) return undefined/);
  assert.ok(
    matchEffect.indexOf("if (!shouldLoadLegacyMatches)")
      < matchEffect.indexOf("fetchCompetitionMatches(selectedCompetition"),
  );
  assert.match(matchEffect, /window\.setInterval\(loadMatches, 30000\)/);
  assert.doesNotMatch(bottomNav, /"upcoming"|"past"|"worldcup"/);
  for (const tab of ["home", "live", "competitions", "news", "predictions"]) {
    assert.match(bottomNav, new RegExp(`key: "${tab}"`));
  }
});

test("legacy teams are gated with the legacy match compatibility flow", () => {
  const app = source("../src/App.jsx");
  const teamEffect = effectContaining(app, "fetchCompetitionTeams(selectedCompetition");

  assert.match(app, /const shouldLoadLegacyTeams = shouldLoadLegacyMatches/);
  assert.match(teamEffect, /if \(!shouldLoadLegacyTeams\) return undefined/);
  assert.ok(
    teamEffect.indexOf("if (!shouldLoadLegacyTeams)")
      < teamEffect.indexOf("fetchCompetitionTeams(selectedCompetition"),
  );
});

test("Competitions uses only CompetitionPage scoped match and team flows", () => {
  const app = source("../src/App.jsx");
  const competitionsPage = source("../src/pages/CompetitionsPage.jsx");
  const competitionPage = source("../src/pages/CompetitionPage.jsx");

  assert.match(app, /activeTab === "competitions" && \(\s*<CompetitionsPage/);
  assert.doesNotMatch(competitionsPage, /fetchCompetitionMatches|fetchCompetitionTeams/);
  assert.match(competitionPage, /fetchCompetitionSeasonMatches\(/);
  assert.match(competitionPage, /if \(!teamsRequested\) return undefined/);
  assert.match(competitionPage, /fetchCompetitionSeasonTeams\(/);
});

test("World Cup summary is lazy in both archive compatibility paths", () => {
  const app = source("../src/App.jsx");
  const archivePage = source("../src/pages/ArchivedCompetitionPage.jsx");
  const summaryEffect = effectContaining(app, "fetchWorldCupSummary({ signal: controller.signal })");

  assert.match(app, /const shouldLoadLegacyWorldCupSummary = activeTab === "worldcup"/);
  assert.match(summaryEffect, /if \(!shouldLoadLegacyWorldCupSummary\) return undefined/);
  assert.ok(
    summaryEffect.indexOf("if (!shouldLoadLegacyWorldCupSummary)")
      < summaryEffect.indexOf("fetchWorldCupSummary"),
  );
  assert.match(summaryEffect, /return \(\) => controller\.abort\(\)/);
  assert.match(archivePage, /fetchWorldCupSummary\(\{ signal: controller\.signal \}\)/);
});

test("prediction stats have one startup path and retain result-driven refresh", () => {
  const app = source("../src/App.jsx");
  const userLoadEffect = effectContaining(app, "fetchPredictions(telegramId)");
  const resultRefreshEffect = effectContaining(app, "Prediction stats refresh failed");

  assert.doesNotMatch(userLoadEffect, /fetchPredictionStats/);
  assert.match(resultRefreshEffect, /fetchPredictionStats\(telegramId\)/);
  assert.match(resultRefreshEffect, /predictionResultsVersion/);
});

test("visible standings preview deliberately keeps league overview loading", () => {
  const competitionPage = source("../src/pages/CompetitionPage.jsx");

  assert.match(competitionPage, /const \[standingsRequested, setStandingsRequested\] = useState\(isLeague\)/);
  assert.match(competitionPage, /renderStandingsPreview\(\)/);
  assert.match(competitionPage, /<StandingsTable lang=\{lang\} preview rows=\{standings\.items\.slice\(0, 5\)\}/);
});
