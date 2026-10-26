// Optional end-to-end fixture verification using an already installed Chrome.
// Start Vite on loopback port 5179, then run: node test/newsBrowser.mjs
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const chrome = "C:/Program Files/Google/Chrome/Application/chrome.exe";
assert.ok(existsSync(chrome), "This optional Windows smoke check requires installed Chrome");
const profile = mkdtempSync(join(tmpdir(), "matchpulse-news-ui-"));
const browser = spawn(chrome, ["--headless=new", "--disable-gpu", "--no-first-run",
  "--no-default-browser-check", "--disable-background-networking", "--disable-extensions",
  "--disable-sync", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"],
{ stdio: "ignore", windowsHide: true });
let socket;
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
try {
  const portFile = join(profile, "DevToolsActivePort");
  for (let count = 0; count < 200 && !existsSync(portFile); count++) await sleep(25);
  const port = Number(readFileSync(portFile, "utf8").split("\n")[0]);
  assert.ok(Number.isInteger(port) && port > 0);
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((done, reject) => { socket.addEventListener("open", done, { once: true });
    socket.addEventListener("error", reject, { once: true }); });
  let nextId = 0;
  const pending = new Map();
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data), task = pending.get(message.id);
    if (task) { pending.delete(message.id); clearTimeout(task.timer);
      if (message.error) task.reject(Error(message.error.message)); else task.done(message.result); }
  });
  const call = (method, params = {}) => new Promise((done, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => { pending.delete(id); reject(Error(`Browser command timed out: ${method}`)); }, 10000);
    pending.set(id, { done, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
  await call("Page.enable");
  for (const width of [320, 375, 390]) {
    await call("Emulation.setDeviceMetricsOverride", { width, height: 844, deviceScaleFactor: 1, mobile: true });
    for (const lang of ["fa", "en"]) {
      await call("Page.navigate", { url: `http://127.0.0.1:5179/test/fixtures/news.html?verify=1&lang=${lang}` });
      let result = "";
      for (let count = 0; count < 300; count++) {
        const state = await call("Runtime.evaluate", {
          expression: "document.getElementById('news-smoke-result')?.textContent || ''", returnByValue: true });
        result = state.result.value;
        if (/^(PASS|FAIL)/.test(result)) break;
        await sleep(25);
      }
      assert.match(result, /^PASS /, `Fixture UI failed at ${width}px ${lang}: ${result}`);
      assert.ok(result.includes(`viewport=${width};`), `Unexpected mobile viewport: ${result}`);
      console.log(`${width}px ${lang}: ${result}`);
    }
  }
  await call("Browser.close").catch(() => {});
} finally {
  socket?.close();
  if (browser.exitCode === null) {
    const exited = new Promise((done) => browser.once("exit", done));
    browser.kill(); await Promise.race([exited, sleep(2000)]);
  }
  // Only this test's unique disposable browser profile may be removed.
  assert.ok(resolve(profile).startsWith(resolve(tmpdir()) + "\\matchpulse-news-ui-"));
  for (let attempt = 0; attempt < 10; attempt++) {
    try { rmSync(profile, { recursive: true, force: true }); break; }
    catch (error) { if (attempt === 9) throw error; await sleep(200); }
  }
}
