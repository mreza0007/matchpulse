import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  competitionNavigationKey,
  competitionTabs,
  formatSeasonLabel,
  groupCompetitionDirectory,
  isNationsLeague,
  resolveNationsLeagueDivision,
} from "../src/utils/competitionPresentation.js";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const divisions = ["a", "b", "c", "d"].map((division) => ({
  competition_key: `uefa_nations_league_${division}`,
  season_key: "2026-2027",
  format: "group_knockout",
  supports_matches: true,
  supports_standings: false,
  supports_groups: false,
  supports_knockout: false,
  supports_predictions: true,
  supports_events: true,
}));

test("directory groups A-D once, ordered A-D, without changing backend metadata", () => {
  const club = { competition_key: "la_liga", supports_standings: true };
  const archived = { competition_key: "worldcup2026", status: "archived" };
  const original = [club, divisions[2], archived, divisions[3], divisions[1], divisions[0]];
  const before = structuredClone(original);
  const grouped = groupCompetitionDirectory(original);
  assert.deepEqual(grouped.map((item) => item.competition_key), ["la_liga", "uefa_nations_league", "worldcup2026"]);
  assert.equal(grouped[0], club);
  assert.equal(grouped[2], archived);
  assert.deepEqual(grouped[1].divisions, divisions);
  assert.equal(grouped[1].name_fa, "لیگ ملت‌های اروپا");
  assert.equal(grouped[1].name_en, "UEFA Nations League");
  assert.equal(grouped[1].supports_standings, undefined);
  assert.deepEqual(original, before);
});

test("parent defaults to A and all division deep links retain the exact backend object", () => {
  assert.equal(resolveNationsLeagueDivision(divisions, "uefa_nations_league"), divisions[0]);
  assert.equal(resolveNationsLeagueDivision(divisions), divisions[0]);
  for (const division of divisions) {
    assert.equal(resolveNationsLeagueDivision(divisions, division.competition_key), division);
    assert.equal(isNationsLeague(division.competition_key), true);
    assert.equal(competitionNavigationKey({ search: `?competition=${division.competition_key}` }), division.competition_key);
    assert.equal(competitionNavigationKey({ hash: `#/competitions/${division.competition_key}` }), division.competition_key);
  }
  assert.equal(isNationsLeague("la_liga"), false);
  assert.equal(competitionNavigationKey({ search: "?competition_key=uefa_nations_league_c" }), divisions[2].competition_key);
  assert.equal(competitionNavigationKey({ search: "?competition=../../private" }), "");
});

test("partial directory uses only available authoritative division objects", () => {
  const partial = groupCompetitionDirectory([divisions[2], divisions[3]])[0];
  assert.deepEqual(partial.divisions, [divisions[2], divisions[3]]);
  assert.equal(resolveNationsLeagueDivision(partial.divisions), divisions[2]);
  assert.equal(resolveNationsLeagueDivision([], "uefa_nations_league_a"), null);
});

test("capability tabs omit unsupported standings, groups, knockout and dead statistics", () => {
  assert.deepEqual(competitionTabs(divisions[0]), ["overview", "matches", "teams"]);
  assert.deepEqual(competitionTabs({ format: "league", supports_matches: true, supports_standings: true }), ["overview", "matches", "standings", "teams"]);
  assert.deepEqual(competitionTabs({ ...divisions[0], supports_groups: true, supports_knockout: true }), ["overview", "matches", "groups", "knockout", "teams"]);
  assert.deepEqual(competitionTabs({}), ["overview", "teams"]);
});

test("unsupported group metadata prevents request, skeleton and error rendering paths", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  assert.match(page, /const isGroupKnockout = competition\.supports_groups === true/);
  assert.match(page, /const isLeague = competition\.supports_standings === true/);
  assert.match(page, /const hasKnockoutTab = competition\.supports_knockout === true/);
  assert.match(page, /if \(!isGroupKnockout \|\| !groupsRequested\) return undefined/);
  assert.match(page, /const renderGroupsPreview = \(\) => \{\s*if \(!isGroupKnockout\) return null/);
  assert.match(page, /if \(!isLeague \|\| !standingsRequested\) return undefined/);
  assert.match(page, /const tabs = competitionTabs\(competition\)/);
});

test("season display normalizes year order without modifying canonical keys", () => {
  assert.equal(formatSeasonLabel("2027-2026"), "2026-2027");
  assert.equal(formatSeasonLabel("۲۰۲۷–۲۰۲۶"), "2026-2027");
  assert.equal(formatSeasonLabel("2026-2027"), "2026-2027");
  assert.equal(formatSeasonLabel("1405-1406"), "1405-1406");
  assert.equal(formatSeasonLabel("2026"), "2026");
  assert.equal(formatSeasonLabel(undefined), "");
  for (const file of ["CompetitionPage", "CompetitionsPage", "PredictionsPage", "ArchivedCompetitionPage"]) {
    assert.match(source(`../src/pages/${file}.jsx`), /<bdi dir="ltr">\{formatSeasonLabel\(competition\.season_key\)\}<\/bdi>/);
  }
});

test("division selection uses existing page and resets scoped state without duplicated fetch logic", () => {
  const wrapper = source("../src/components/competitions/NationsLeaguePage.jsx");
  assert.match(wrapper, /dir=\{props\.lang === "fa" \? "rtl" : "ltr"\}/);
  assert.match(wrapper, /onClick=\{\(\) => setSelectedKey\(division\.competition_key\)\}/);
  assert.match(wrapper, /competition=\{competition\}/);
  assert.match(wrapper, /key=\{`\$\{competition\.competition_key\}:\$\{competition\.season_key\}`\}/);
  assert.doesNotMatch(wrapper, /fetch\(|fetchCompetition|api\//);
  const app = source("../src/App.jsx");
  assert.match(app, /competitionNavigationKey\(window\.location\)/);
  assert.match(app, /initialCompetitionKey=\{initialCompetitionKey\}/);
});

test("shared MatchCard preserves actions and replaces only decorative metadata emoji", () => {
  const card = source("../src/components/matches/MatchCard.jsx");
  assert.match(card, /onReminderToggle\?\.\(match\)/);
  assert.match(card, /onDetailsClick\?\.\(match\)/);
  assert.match(card, /showPredictions && showPrediction/);
  assert.match(card, /showReminder && !isPostponed/);
  assert.match(card, /<UiIcon name="clock"/);
  assert.match(card, /match\.stadium &&/);
  assert.match(card, /match\.city &&/);
  assert.doesNotMatch(card, /🕒|🏟|📍|🔔|🔕/);
  assert.match(card, /export default memo\(MatchCard\)/);
});

test("compact mobile styling keeps touch targets, safe area and horizontal selector containment", () => {
  const css = source("../src/App.css");
  assert.match(css, /font-size: clamp\(17px, 4\.5vw, 20px\)/);
  assert.match(css, /grid-template-columns: repeat\(4, minmax\(0, 1fr\)\)/);
  assert.match(css, /padding-bottom: calc\(88px \+ env\(safe-area-inset-bottom\)\)/);
  assert.match(css, /bottom: max\(8px, env\(safe-area-inset-bottom\)\)/);
  assert.match(css, /overscroll-behavior-inline: contain/);
  assert.match(css, /min-height: 44px/);
  assert.match(source("../src/components/layout/BottomNav.jsx"), /t\[item\.label\]/);
});
