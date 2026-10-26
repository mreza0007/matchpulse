// Invented test metadata only; these publishers are not configured sources.
export const fixtureFavorites = [
  { competition_key: "premier_league", team_id: "mp_team_shared", team_name_en: "Fixture United", team_name_fa: "تیم آزمایشی",
    competition: { name_en: "Premier League", name_fa: "لیگ برتر انگلیس" } },
  { competition_key: "la_liga", team_id: "mp_team_shared", team_name_en: "Fixture United", team_name_fa: "تیم آزمایشی",
    competition: { name_en: "La Liga", name_fa: "لالیگا" } },
];

export const fixtureArticle = {
  id: "news_fixture_1", origin: "publisher", source: "Fixture Publisher — TEST ONLY",
  original_url: "https://news.example.invalid/articles/one",
  title_fa: "خبر آزمایشی با عنوان بلند درباره فوتبال ایران و تیم‌های محبوب برای بررسی نمایش صحیح در صفحه باریک موبایل",
  title_en: "A fixture headline for international football fans with a deliberately long club announcement",
  language: "fa", published_at: "2026-10-20T09:00:00Z", category: "iran",
  summary: "This is invented, permitted test metadata, not a real publisher article.",
  image_url: "https://images.example.invalid/fixture.png", image_permitted: false,
  related_competition_keys: ["premier_league"],
  related_teams: [{ competition_key: "premier_league", team_id: "mp_team_shared" }],
};

export const fixtureArticles = Array.from({ length: 24 }, (_, index) => ({
  ...fixtureArticle, id: `news_fixture_${index}`, category: index % 2 ? "world" : "iran",
  title_en: `${index + 1}. ${fixtureArticle.title_en}`,
  related_competition_keys: [index % 2 ? "la_liga" : "premier_league"],
  related_teams: [{ competition_key: index % 2 ? "la_liga" : "premier_league", team_id: "mp_team_shared" }],
}));
