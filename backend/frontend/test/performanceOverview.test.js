import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const testDirectory = fileURLToPath(new URL(".", import.meta.url));
const source = (relativePath) => readFileSync(
  new URL(relativePath, `file:///${testDirectory.replaceAll("\\", "/")}`),
  "utf8",
);

const effectContaining = (page, marker) => {
  const markerIndex = page.indexOf(marker);
  assert.notEqual(markerIndex, -1, `missing marker: ${marker}`);
  const effectStart = page.lastIndexOf("useEffect(() => {", markerIndex);
  const effectEnd = page.indexOf("\n  }, [", markerIndex);
  assert.notEqual(effectStart, -1, `missing effect start for: ${marker}`);
  assert.notEqual(effectEnd, -1, `missing effect end for: ${marker}`);
  return page.slice(effectStart, effectEnd);
};

test("overview helper uses the lightweight scoped route", () => {
  const api = source("../src/api/football.js");
  const helperStart = api.indexOf("export function fetchCompetitionSeasonOverview");
  const helperEnd = api.indexOf("export function fetchCompetitionSeasonTeams", helperStart);
  const helper = api.slice(helperStart, helperEnd);

  assert.match(helper, /competitions\/\$\{competition\}\/seasons\/\$\{season\}\/overview/);
  assert.doesNotMatch(helper, /status=all|worldcup|provider/);
});

test("initial CompetitionPage effect fetches overview but not full season", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  const overviewEffect = effectContaining(page, "fetchCompetitionSeasonOverview(");

  assert.match(overviewEffect, /fetchCompetitionSeasonOverview\(/);
  assert.doesNotMatch(overviewEffect, /fetchCompetitionSeasonMatches\(/);
  assert.match(overviewEffect, /controller\.signal\.aborted/);
  assert.match(overviewEffect, /return \(\) => controller\.abort\(\)/);
});

test("full season is requested lazily once when Matches is opened", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  const fullEffect = effectContaining(page, "fetchCompetitionSeasonMatches(");
  const selectStart = page.indexOf("const selectTab");
  const selectEnd = page.indexOf("const retryOverviewMatches", selectStart);
  const selectTab = page.slice(selectStart, selectEnd);

  assert.match(page, /const \[fullMatchesRequested, setFullMatchesRequested\] = useState\(false\)/);
  assert.match(fullEffect, /if \(!fullMatchesRequested\) return undefined/);
  assert.ok(
    fullEffect.indexOf("if (!fullMatchesRequested)")
      < fullEffect.indexOf("fetchCompetitionSeasonMatches("),
  );
  assert.match(selectTab, /tab === "matches" && !fullMatchesRequested/);
  assert.match(selectTab, /setFullMatchesRequested\(true\)/);
  assert.doesNotMatch(selectTab, /setFullMatchesRequested\(false\)/);
});

test("overview and full schedule use isolated state and render paths", () => {
  const page = source("../src/pages/CompetitionPage.jsx");

  assert.match(page, /const \[overviewMatches, setOverviewMatches\]/);
  assert.match(page, /const \[fullMatches, setFullMatches\]/);
  assert.match(page, /overviewMatch\(overviewMatches\.items\)/);
  assert.match(page, /groupMatchesByDate\(fullMatches\.items, lang\)/);
  assert.match(page, /payload\.matches\.map\(normalizeMatchPayload\)/);
  assert.match(page, /setFullMatches\(\{ items, loading: false, loaded: true, failed: false \}\)/);
});

test("competition switches abort both requests and remount isolated state", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  const directory = source("../src/pages/CompetitionsPage.jsx");
  const overviewEffect = effectContaining(page, "fetchCompetitionSeasonOverview(");
  const fullEffect = effectContaining(page, "fetchCompetitionSeasonMatches(");

  assert.match(overviewEffect, /competition\.competition_key/);
  assert.match(overviewEffect, /competition\.season_key/);
  assert.match(fullEffect, /competition\.competition_key/);
  assert.match(fullEffect, /competition\.season_key/);
  assert.match(overviewEffect, /return \(\) => controller\.abort\(\)/);
  assert.match(fullEffect, /return \(\) => controller\.abort\(\)/);
  assert.match(directory, /key=\{`\$\{selectedCompetition\.competition_key\}:\$\{selectedCompetition\.season_key \|\| ""\}`\}/);
});

test("overview cards retain canonical reminder and event identity paths", () => {
  const page = source("../src/pages/CompetitionPage.jsx");

  assert.match(page, /const renderDisplayMatchCard/);
  assert.match(page, /reminderIdentityFromMatch\(competition, match\)/);
  assert.match(page, /competitionEventIdentity\(competition, match\)/);
  assert.match(page, /renderDisplayMatchCard\(\s*primaryMatch/);
  assert.doesNotMatch(page.slice(0, page.indexOf("const toggleMatchEvents")), /fetchCompetitionMatchEvents\(/);
});

test("World Cup archive remains outside the generic overview path", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  const archive = source("../src/pages/ArchivedCompetitionPage.jsx");

  assert.match(page, /competitionExperience\(props\.competition\) === "archive"/);
  assert.match(page, /return <ArchivedCompetitionPage/);
  assert.doesNotMatch(archive, /fetchCompetitionSeasonOverview|fetchCompetitionSeasonMatches/);
});
