import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  buildCompetitionMatchScopes,
  normalizeCompetitionRound,
  selectRelevantRound,
  scopeLabel,
} from "../src/utils/competitionRounds.js";

const testDirectory = fileURLToPath(new URL(".", import.meta.url));
const source = (relativePath) => readFileSync(
  new URL(relativePath, `file:///${testDirectory.replaceAll("\\", "/")}`),
  "utf8",
);
const NOW = Date.parse("2026-09-23T12:00:00Z");
const kickoff = (offsetHours) => (NOW + offsetHours * 60 * 60 * 1000) / 1000;
const match = (round, status, offsetHours, extra = {}) => ({
  id: `${round}:${status}:${offsetHours}`,
  kickoff_ts: offsetHours === null ? undefined : kickoff(offsetHours),
  round,
  status,
  ...extra,
});
const league = { competition_key: "la_liga", format: "league", supports_standings: true };
const tournament = { competition_key: "champions_league", format: "league", supports_standings: false };

test("round normalization handles numeric, English, Persian, and missing metadata", () => {
  assert.equal(normalizeCompetitionRound({ round: 6 }, { league: true }).roundNumber, 6);
  assert.equal(normalizeCompetitionRound({ round: "Round 7" }, { league: true }).roundKey, "round:7");
  assert.equal(normalizeCompetitionRound({ round: "Week 8" }, { league: true }).roundNumber, 8);
  assert.equal(normalizeCompetitionRound({ round: "Matchweek 9" }, { league: true }).roundNumber, 9);
  assert.equal(normalizeCompetitionRound({ round: "هفته ۱۰" }, { league: true }).roundNumber, 10);
  assert.equal(normalizeCompetitionRound({}, { league: true }), null);
});

test("round labels are bilingual and tournaments retain stage semantics", () => {
  const leagueRound = normalizeCompetitionRound({ round: "Week 6" }, { league: true });
  assert.equal(scopeLabel(leagueRound, "fa"), "هفته ۶");
  assert.equal(scopeLabel(leagueRound, "en"), "MW 6");

  const quarterFinal = normalizeCompetitionRound({ stage: "Quarter-finals" });
  assert.equal(quarterFinal.roundType, "stage");
  assert.equal(quarterFinal.stageKey, "quarter_finals");
  assert.equal(scopeLabel(quarterFinal, "fa"), "یک‌چهارم نهایی");
  assert.equal(scopeLabel(quarterFinal, "en"), "Quarter-finals");
  assert.equal(normalizeCompetitionRound({ stage: "۱/۸ نهایی" }).stageKey, "round_of_16");
});

test("league scope grouping is numeric and tournament grouping is stage-aware", () => {
  const leagueModel = buildCompetitionMatchScopes([
    match("Week 2", "upcoming", 48),
    match("Week 1", "finished", -48),
    match("Week 2", "upcoming", 50),
  ], league);
  assert.equal(leagueModel.mode, "round");
  assert.deepEqual(leagueModel.scopes.map((scope) => scope.key), ["round:1", "round:2"]);
  assert.equal(leagueModel.scopes[1].matches.length, 2);

  const tournamentModel = buildCompetitionMatchScopes([
    match("League Phase", "finished", -72),
    match("Round of 16", "upcoming", 72),
    match("Quarter-finals", "upcoming", 240),
  ], tournament);
  assert.equal(tournamentModel.mode, "stage");
  assert.deepEqual(tournamentModel.scopes.map((scope) => scope.stageKey), [
    "league_phase", "round_of_16", "quarter_finals",
  ]);
});

test("partial or missing round metadata keeps the progressive date fallback", () => {
  const model = buildCompetitionMatchScopes([
    match("Week 1", "finished", -48),
    match(null, "upcoming", 48),
  ], league);
  assert.equal(model.mode, "fallback");
  assert.deepEqual(model.scopes, []);

  const unknownModel = buildCompetitionMatchScopes([
    match("current", "upcoming", 48),
  ], league);
  assert.equal(unknownModel.mode, "fallback");
});

test("smart selection prioritizes a currently live round", () => {
  const model = buildCompetitionMatchScopes([
    match(4, "finished", -72),
    match(5, "live", -1, { is_live: true }),
    match(6, "upcoming", 72),
  ], league);
  assert.deepEqual(selectRelevantRound(model.scopes, NOW), { scopeKey: "round:5", reason: "live" });
});

test("smart selection keeps an already-begun round with unfinished fixtures", () => {
  const model = buildCompetitionMatchScopes([
    match(5, "finished", -24),
    match(5, "upcoming", 2),
    match(6, "upcoming", 72),
  ], league);
  assert.deepEqual(selectRelevantRound(model.scopes, NOW), { scopeKey: "round:5", reason: "active" });
});

test("an early-played later round does not skip a nearer active round", () => {
  const model = buildCompetitionMatchScopes([
    match(6, "finished", -24),
    match(6, "upcoming", 24),
    match(10, "finished", -48),
    match(10, "upcoming", 30 * 24),
  ], league);
  assert.deepEqual(selectRelevantRound(model.scopes, NOW), { scopeKey: "round:6", reason: "active" });
});

test("FIFA-break selection advances from a completed round to the next future round", () => {
  const model = buildCompetitionMatchScopes([
    match(5, "finished", -120),
    match(6, "upcoming", 10 * 24),
    match(7, "upcoming", 17 * 24),
  ], league);
  assert.deepEqual(selectRelevantRound(model.scopes, NOW), { scopeKey: "round:6", reason: "upcoming" });
});

test("smart selection chooses earliest future scope and the last scope after completion", () => {
  const futureModel = buildCompetitionMatchScopes([
    match(4, "finished", -96),
    match(5, "upcoming", 48),
    match(6, "upcoming", 24),
  ], league);
  assert.deepEqual(selectRelevantRound(futureModel.scopes, NOW), { scopeKey: "round:6", reason: "upcoming" });

  const completedModel = buildCompetitionMatchScopes([
    match(1, "finished", -96),
    match(2, "finished", -24),
  ], league);
  assert.deepEqual(selectRelevantRound(completedModel.scopes, NOW), { scopeKey: "round:2", reason: "completed" });
});

test("postponed fixtures do not falsely hold progression and missing kickoff is deterministic", () => {
  const postponedModel = buildCompetitionMatchScopes([
    match(4, "postponed", -48),
    match(5, "upcoming", 72),
  ], league);
  assert.deepEqual(selectRelevantRound(postponedModel.scopes, NOW), { scopeKey: "round:5", reason: "upcoming" });

  const unknownKickoffModel = buildCompetitionMatchScopes([
    match(3, "finished", -24),
    match(4, "upcoming", null),
  ], league);
  assert.deepEqual(selectRelevantRound(unknownKickoffModel.scopes, NOW), {
    scopeKey: "round:4",
    reason: "upcoming_unknown",
  });
});

test("league UI switches scopes client-side and bypasses redundant progressive loading", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  const selectorStart = page.indexOf("const selectMatchScope");
  const selectorEnd = page.indexOf("useEffect(() =>", selectorStart);
  const selector = page.slice(selectorStart, selectorEnd);

  assert.match(page, /selectedScope\?\.matches \|\| \[\]/);
  assert.match(page, /fullMatches\.scopeModel\.mode !== "round"/);
  assert.match(page, /<RoundSelector/);
  assert.match(selector, /setSelectedScopeKey\(scopeKey\)/);
  assert.doesNotMatch(selector, /fetchCompetitionSeasonMatches|fetch\(/);
});

test("selector supports current-round return, autoscroll guards, and explicit RTL/LTR", () => {
  const selector = source("../src/components/competitions/RoundSelector.jsx");
  assert.match(selector, /typeof selectedChip\?\.scrollIntoView !== "function"/);
  assert.match(selector, /inline: "center"/);
  assert.match(selector, /prefers-reduced-motion/);
  assert.match(selector, /dir=\{lang === "fa" \? "rtl" : "ltr"\}/);
  assert.match(selector, /selectedScopeKey !== relevantScopeKey/);
  assert.match(selector, /onSelect\(relevantScopeKey\)/);
  assert.match(selector, /mode === "stage" \? t\.returnCurrentStage : t\.returnCurrentRound/);
});

test("known competitions use local logos and the resolver retains safe fallback", () => {
  const config = source("../src/config/competitions.js");
  const logo = source("../src/components/competitions/CompetitionLogo.jsx");
  const directory = source("../src/pages/CompetitionsPage.jsx");
  const detail = source("../src/pages/CompetitionPage.jsx");

  [
    "premier-league.svg",
    "persian-gulf-pro-league.png",
    "la-liga.svg",
    "serie-a.svg",
    "bundesliga.svg",
    "ligue-1.svg",
    "champions-league.svg",
    "europa-league.svg",
    "uefa-nations-league.png",
  ].forEach((asset) => assert.match(config, new RegExp(asset.replace(".", "\\."))));
  assert.ok(config.indexOf("persian-gulf-pro-league.png") < config.indexOf('"PGPL"') + 200);
  assert.match(logo, /competition\.logo_url[\s\S]*trustedConfig\?\.logoSrc/);
  assert.match(logo, /onError=\{\(\) => setFailedSrc\(logoSrc\)\}/);
  assert.match(logo, /trustedConfig\?\.logoFallback \|\| "⚽"/);
  assert.match(directory, /<CompetitionLogo competition=\{competition\} lang=\{lang\}/);
  assert.match(detail, /<CompetitionLogo competition=\{competition\} eager lang=\{lang\}/);
});

test("Nations League uses stage-aware rounds and the national-team directory category", () => {
  const config = source("../src/config/competitions.js");
  const categories = source("../src/config/competitionCategories.js");
  const nationsLeague = {
    competition_key: "uefa_nations_league_a",
    format: "group_knockout",
    supports_standings: false,
  };
  const model = buildCompetitionMatchScopes([
    match("هفته ۳", "finished", -24),
    match("هفته ۴", "upcoming", 24),
  ], nationsLeague);

  assert.equal(model.mode, "stage");
  assert.deepEqual(model.scopes.map((scope) => scopeLabel(scope, "en")), [
    "Round 3",
    "Round 4",
  ]);
  assert.match(config, /uefa_nations_league_a:[\s\S]*uefa-nations-league\.png/);
  for (const division of ["a", "b", "c", "d"]) {
    assert.match(
      categories,
      new RegExp(`uefa_nations_league_${division}: "nationalCompetitions"`),
    );
  }
});

test("existing knockout bracket remains a separate unchanged data path", () => {
  const page = source("../src/pages/CompetitionPage.jsx");
  assert.match(page, /fetchCompetitionKnockout/);
  assert.match(page, /<KnockoutRound/);
  assert.match(page, /activeTab === "knockout"/);
});
