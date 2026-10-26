// Invoked only by the local fixture URL's ?verify=1 switch.
export async function runNewsBrowserChecks(t) {
  const output = document.createElement("output");
  output.id = "news-smoke-result";
  document.body.append(output);
  let checks = 0;
  const assert = (condition, message) => { if (!condition) throw Error(message); ++checks; };
  const wait = async (predicate) => {
    for (let count = 0; count < 250; count++) {
      if (predicate()) return;
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
    throw Error("Timed out waiting for fixture UI");
  };
  const cards = () => [...document.querySelectorAll(".structured-news-card")];
  const button = (label) => [...document.querySelectorAll("button")].find((node) => node.textContent === label);
  const category = (key) => button(t[`newsCategory${key}`]).click();
  try {
    await wait(() => cards().length === 20);
    assert(cards()[0].textContent.includes("Fixture Publisher"), "Publisher attribution missing");
    assert(cards()[0].querySelector("time[datetime]"), "Publication time missing");
    assert(cards()[0].querySelector("a").getAttribute("rel") === "noopener noreferrer", "Unsafe original link");
    assert(!document.querySelector(".news-article-image"), "Unapproved fixture image shown");
    button(t.newsLoadMore).click();
    await wait(() => cards().length === 24);
    assert(!button(t.newsLoadMore), "Pagination did not finish");
    category("World"); await wait(() => cards().length === 12);
    category("Transfers"); await wait(() => !cards().length && document.body.textContent.includes(t.newsCategoryEmpty));
    assert(!cards().length, "Empty category retained stale cards");
    category("Favorites"); await wait(() => cards().length === 20);
    const select = document.querySelector(".news-team-filter select");
    select.value = JSON.stringify(["la_liga", "mp_team_shared"]);
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await wait(() => cards().length === 12);
    assert(cards().every((card) => card.textContent.includes(t.newsCategoryWorld)), "Exact team scope crossed competitions");
    button("Toggle favorite membership").click();
    await wait(() => select.value === "" && cards().every((card) => card.textContent.includes(t.newsCategoryIran)));
    assert(cards().length === 12, "Favorites changes did not refresh personalized feed");
    category("All"); await wait(() => cards().length === 20);
    button("Toggle API failure").click(); button(t.newsRefresh).click();
    await wait(() => document.querySelector(".structured-news-error"));
    assert(cards().length === 20, "Failed refresh removed loaded articles");
    button("Toggle API failure").click(); button(t.retry).click();
    await wait(() => !document.querySelector(".structured-news-error"));
    assert(cards().length === 20, "Retry did not recover");
    button("Switch language").click();
    await wait(() => document.querySelector(".structured-news-page").dir === (t.dir === "rtl" ? "ltr" : "rtl"));
    button("Switch language").click();
    await wait(() => document.querySelector(".structured-news-page").dir === t.dir);
    assert(cards().every((card) => card.dir === t.dir), "Card language direction mismatch");
    assert(document.documentElement.scrollWidth <= window.innerWidth, "Page horizontally overflows viewport");
    assert(cards().every((card) => {
      const bounds = card.getBoundingClientRect();
      return bounds.left >= 0 && bounds.right <= window.innerWidth + 1;
    }), "Card exceeds narrow mobile viewport");
    output.textContent = `PASS ${checks} checks; viewport=${window.innerWidth}; dir=${t.dir}`;
  } catch (error) {
    output.textContent = `FAIL ${error.message}; checks=${checks}; viewport=${window.innerWidth}`;
  }
}
