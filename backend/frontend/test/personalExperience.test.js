import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { favoriteControl, favoriteMatchTeam } from "../src/utils/favorites.js";
import { getNormalizedEventType, getEventTypeLabel, resolveEventTeam } from "../src/utils/events.js";
import { isActiveReminder, isReminderEligibleMatch } from "../src/utils/reminders.js";

const source = (name) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const competition = { competition_key: "premier_league", status: "active", is_active: true, supports_favorites: true };
const match = { home_team_id: "mp_team_same", away_team_id: "mp_team_away", home_fa: "خانه", home_en: "Home", home_logo: "/home.png", home_flag: "", away_en: "Away", away_flag: "🇮🇷" };

test("neutral VAR never infers a disallowed decision from review alone", () => {
  for (const description of ["VAR review", "Goal under VAR review", "گل کمک داور ویدیویی", "Possible disallowed goal?"]) {
    assert.equal(getNormalizedEventType({ type: "var", description }), "var");
  }
  assert.equal(getEventTypeLabel("var", "fa"), "VAR");
});

test("confirmed disallowed semantics and localized labels are explicit", () => {
  for (const description of ["گل مردود شده", "Goal disallowed after VAR review", "Disallowed goal"]) {
    assert.equal(getNormalizedEventType({ type: "goal", description }), "disallowed_goal");
  }
  assert.equal(getEventTypeLabel("disallowed_goal", "fa"), "گل مردود شده");
  assert.equal(getEventTypeLabel("disallowed_goal", "en"), "Disallowed goal");
  const row = source("components/matches/EventRow.jsx");
  assert.match(row, /\? getRenderedEventIcon\(type\) : event.icon/);
});

test("existing event categories remain unchanged", () => {
  for (const type of ["own_goal", "goal", "penalty_goal", "missed_penalty", "second_yellow_red", "red_card", "substitution"]) {
    assert.equal(getNormalizedEventType({ type, display_minute: "120+3" }), type);
  }
  const row = source("components/matches/EventRow.jsx");
  for (const field of ["display_minute", "assist", "player_in_name", "player_out_name"]) assert.ok(row.includes(field));
});

test("match favorite selection uses canonical IDs only, never names/provider IDs", () => {
  assert.equal(favoriteMatchTeam(match, "home").id, "mp_team_same");
  assert.equal(favoriteMatchTeam(match, "away").id, "mp_team_away");
  assert.equal(favoriteMatchTeam({ home_team_id: "481", home_en: "Home" }, "home"), null);
  assert.equal(favoriteMatchTeam({ external_team_id: "mp_team_same" }, "home"), null);
  assert.equal(favoriteMatchTeam(match, "home").logo, "/home.png");
});

test("favorite active/pending state is competition-scoped and backend-gated", () => {
  const team = favoriteMatchTeam(match, "home");
  const keys = new Set(["premier_league:mp_team_same"]);
  const pending = new Set(keys);
  assert.deepEqual(favoriteControl(competition, team, keys, pending), { active: true, pending: true, visible: true });
  assert.equal(favoriteControl({ ...competition, competition_key: "la_liga" }, team, keys, pending).active, false);
  assert.equal(favoriteControl({ ...competition, supports_favorites: false }, team, new Set(), pending).visible, false);
  assert.equal(favoriteControl({ ...competition, status: "archived", is_active: false }, team, new Set(), pending).visible, false);
});

test("club/national favorite teams preserve names and flag/logo fallback", () => {
  assert.equal(resolveEventTeam({ side: "home" }, match, "en").logo, "/home.png");
  assert.equal(resolveEventTeam({ side: "away" }, match, "fa").flag, "🇮🇷");
  const card = source("components/matches/MatchCard.jsx");
  assert.match(card, /aria-pressed=\{Boolean\(isFavorite\)\}/);
  assert.match(card, /disabled=\{favoritesDisabled \|\| control.pending\}/);
  assert.match(card, /event.stopPropagation\(\)/);
});

test("active reminders require unsent upcoming state and a future trigger", () => {
  const now = Date.parse("2030-01-01T00:00:00Z");
  const reminder = { competition_key: "premier_league", status: "upcoming", kickoff_utc: "2030-01-01T02:00:00Z" };
  assert.equal(isActiveReminder(reminder, now), true);
  for (const status of ["live", "finished", "postponed", "cancelled"]) assert.equal(isActiveReminder({ ...reminder, status }, now), false);
  for (const extra of [{ notified: true }, { reminder_state: "retired" }, { kickoff_utc: null }, { competition_key: "worldcup2026" }]) assert.equal(isActiveReminder({ ...reminder, ...extra }, now), false);
  assert.equal(isReminderEligibleMatch({ ...reminder, kickoff_utc: "2030-01-01T01:00:00Z" }, now), false);
});

test("Profile excludes competition hero and guides favorite discovery without changing deep links", () => {
  const app = source("App.jsx");
  const profile = source("pages/ProfilePage.jsx");
  assert.match(app, /'predictions', 'profile'\].includes\(activeTab\)/);
  assert.match(app, /onChooseFavorites=\{\(\) => setActiveTab\("competitions"\)\}/);
  assert.doesNotMatch(profile, /competition-selector|CompetitionPage|overview-panel/);
  assert.match(profile, /t.chooseFavoriteTeams/);
  assert.match(source("api/user.js"), /\?view=active/);
  assert.match(app, /clearInterval\(timer\)/);
});
