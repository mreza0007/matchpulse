import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { favoriteCompetitionName, favoriteDisplayName } from "../src/utils/favorites.js";
import { createFeedbackController, SUCCESS_FEEDBACK_MS, ERROR_FEEDBACK_MS } from "../src/utils/transientFeedback.js";

const source = (name) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");

function harness() {
  let clock = 0, nextId = 0;
  const timers = new Map(), changes = [];
  const controller = createFeedbackController((value) => changes.push(value), {
    setTimer(callback, delay) { const id = ++nextId; timers.set(id, { callback, at: clock + delay }); return id; },
    clearTimer(id) { timers.delete(id); },
  });
  return { controller, timers, changes, advance(ms) {
    clock += ms;
    for (const [id, timer] of [...timers]) {
      if (timer.at <= clock) { timers.delete(id); timer.callback(); }
    }
  } };
}

test("favorite names localize full text without using canonical/provider IDs", () => {
  const favorite = { team_id: "123", team_name_fa: "باشگاه فوتبال با نام بسیار طولانی", team_name_en: "Very Long Football Club Name" };
  assert.equal(favoriteDisplayName(favorite, "fa"), favorite.team_name_fa);
  assert.equal(favoriteDisplayName(favorite, "en"), favorite.team_name_en);
  assert.equal(favoriteDisplayName({ team_id: "mp_team_123", team_name: "1" }, "en"), "");
  assert.equal(favoriteDisplayName({ team_name_fa: "۱۲۳", name_en: "Valid Club" }, "fa"), "Valid Club");
  assert.equal(favoriteDisplayName({ name_en: "1860 Munich" }, "en"), "1860 Munich");
});

test("competition labels come from existing backend descriptors, not IDs", () => {
  const favorite = { competition_key: "raw_key", competition: { name_fa: "لیگ برتر", name_en: "Premier League" } };
  assert.equal(favoriteCompetitionName(favorite, "fa"), "لیگ برتر");
  assert.equal(favoriteCompetitionName(favorite, "en"), "Premier League");
  assert.equal(favoriteCompetitionName({ competition_key: "raw_key" }, "en"), "");
});

test("dedicated grid keeps text shrinkable and controls at 44px", () => {
  const css = source("App.css"), row = source("components/profile/FavoriteTeamItem.jsx");
  assert.match(css, /\.profile-favorite-item\s*\{[^}]*grid-template-columns: 36px minmax\(0, 1fr\) 44px/s);
  assert.match(css, /\.profile-favorite-text\s*\{[^}]*min-width: 0;[^}]*text-align: start;[^}]*overflow-wrap: anywhere/s);
  assert.match(css, /\.profile-favorite-remove\s*\{[^}]*min-width: 44px;[^}]*min-height: 44px/s);
  assert.doesNotMatch(row, /className="[^"\n]*profile-remove-btn|profile-item-text/);
  assert.match(row, /<bdi>\{displayName\}<\/bdi>/);
  assert.match(row, /<bdi>\{competitionName\}<\/bdi>/);
  assert.match(row, /onRemove\(favorite\)/);
  assert.match(row, /aria-busy=\{isRemoving\}/);
});

test("group counts are not rendered as stray numbers and media uses safe fallback", () => {
  const profile = source("pages/ProfilePage.jsx"), row = source("components/profile/FavoriteTeamItem.jsx");
  assert.doesNotMatch(profile, /<span>\{favorites.length\}<\/span>/);
  assert.match(row, /<TeamFlag flagEmoji=\{flag\} logoUrl=\{logo\} teamName=\{name\}/);
  assert.doesNotMatch(row, /\{favorite.team_id\}/);
});

test("success feedback disappears at three seconds", () => {
  const h = harness();
  h.controller.show("Added", "success");
  h.advance(SUCCESS_FEEDBACK_MS - 1);
  assert.equal(h.changes.at(-1).message, "Added");
  h.advance(1);
  assert.equal(h.changes.at(-1), null);
  assert.equal(h.timers.size, 0);
});

test("new feedback replaces old feedback and resets the deadline", () => {
  const h = harness();
  h.controller.show("Added", "success");
  h.advance(2000);
  h.controller.show("Removed", "success");
  assert.equal(h.timers.size, 1);
  h.advance(1000);
  assert.equal(h.changes.at(-1).message, "Removed");
  h.advance(2000);
  assert.equal(h.changes.at(-1), null);
});

test("repeating identical messages still resets the timer", () => {
  const h = harness();
  h.controller.show("Added", "success");
  h.advance(2500);
  h.controller.show("Added", "success");
  h.advance(1000);
  assert.equal(h.changes.at(-1).message, "Added");
  h.advance(2000);
  assert.equal(h.changes.at(-1), null);
});

test("stale cancelled callbacks cannot dismiss newer feedback", () => {
  const h = harness();
  h.controller.show("Old", "success");
  const stale = [...h.timers.values()][0].callback;
  h.controller.show("New", "success");
  stale();
  assert.equal(h.changes.at(-1).message, "New");
});

test("errors remain readable for eight seconds and replace success", () => {
  const h = harness();
  h.controller.show("Added", "success");
  h.controller.show("Try again", "error");
  h.advance(3000);
  assert.equal(h.changes.at(-1).kind, "error");
  h.advance(ERROR_FEEDBACK_MS - 3000);
  assert.equal(h.changes.at(-1), null);
});

test("unmount clears timers and prevents stale state updates", () => {
  const h = harness();
  h.controller.show("Added", "success");
  const stale = [...h.timers.values()][0].callback;
  h.controller.dispose();
  const count = h.changes.length;
  stale(); h.controller.show("Late response", "success"); h.advance(8000);
  assert.equal(h.timers.size, 0);
  assert.equal(h.changes.length, count);
});

test("explicit dismiss cancels timeout and strict-effect setup is safe", () => {
  const h = harness();
  h.controller.show("Added", "success");
  h.controller.dismiss();
  assert.equal(h.timers.size, 0);
  assert.equal(h.changes.at(-1), null);
  h.controller.dispose(); h.controller.activate();
  h.controller.show("New mount", "success");
  assert.equal(h.changes.at(-1).message, "New mount");
  h.advance(3000);
  assert.equal(h.changes.at(-1), null);
});

test("all favorite actions share one non-overlay accessible feedback outlet", () => {
  const app = source("App.jsx"), css = source("App.css");
  assert.match(app, /useTransientFeedback\(\)/);
  assert.equal((app.match(/className=\{`status-message favorite-feedback/g) || []).length, 1);
  assert.match(app, /t.addedFavorite\}`.trim\(\), "success"/);
  assert.match(app, /t.removedFavorite\}`.trim\(\), "success"/);
  for (const name of ["pages/ProfilePage.jsx", "pages/CompetitionPage.jsx", "pages/CompetitionsPage.jsx"]) assert.doesNotMatch(source(name), /favoriteMessage/);
  assert.match(css, /\.favorite-feedback > span\s*\{[^}]*overflow-wrap: anywhere/s);
  assert.doesNotMatch(css.match(/\.favorite-feedback\s*\{[^}]*\}/s)[0], /position: (?:fixed|absolute)/);
  assert.match(source("hooks/useTransientFeedback.js"), /return \(\) => controller.dispose\(\)/);
});
