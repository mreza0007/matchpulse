export default function NewsCard({ categoryLabel, competitionLabels, item, lang }) {
  const title = lang === "fa"
    ? item.title_fa || item.title_en || ""
    : item.title_en || item.title_fa || "";
  const tag = lang === "fa"
    ? item.tag_fa || item.tag_en || ""
    : item.tag_en || item.tag_fa || "";

  return (
    <article className="structured-news-card">
      <div className="structured-news-meta">
        <span className="structured-news-category">{categoryLabel}</span>
        {tag && <span>{tag}</span>}
      </div>
      <h2>{title}</h2>
      {competitionLabels.length > 0 && (
        <div className="structured-news-relations">
          {competitionLabels.slice(0, 2).map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      )}
    </article>
  );
}
