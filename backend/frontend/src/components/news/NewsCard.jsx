import { useState } from "react";
import { articleDate, articleHeadline, openArticle, safeArticleUrl } from "../../utils/news.js";

export default function NewsCard({ categoryLabel, competitionLabels = [], item, lang, t }) {
  const [failedImage, setFailedImage] = useState("");
  const title = articleHeadline(item, lang);
  const url = safeArticleUrl(item.original_url);
  const image = item.image_permitted === true ? safeArticleUrl(item.image_url) : "";
  const published = articleDate(item.published_at, lang);
  const notice = item.origin === "static_notice";
  const tag = lang === "fa"
    ? item.tag_fa || item.tag_en || ""
    : item.tag_en || item.tag_fa || "";

  return (
    <article className="structured-news-card" dir={lang === "fa" ? "rtl" : "ltr"}>
      {image && failedImage !== image && (
        <img className="news-article-image" src={image} alt="" loading="lazy" decoding="async"
          referrerPolicy="no-referrer" onError={() => setFailedImage(image)} />
      )}
      <div className="structured-news-meta">
        <span className="structured-news-category">{categoryLabel}</span>
        {tag && <span>{tag}</span>}
        {notice && <span>{t.newsStaticNotice}</span>}
      </div>
      <h2 dir="auto">{title}</h2>
      {item.summary && <p className="news-article-summary" dir="auto">{item.summary}</p>}
      <div className="news-article-byline">
        <span><span>{t.newsPublisher}: </span><bdi>{item.source || t.newsUnknownPublisher}</bdi></span>
        {published && <time dateTime={published.iso}>{published.label}</time>}
        {published?.stale && <span>{t.newsOlderArticle}</span>}
      </div>
      {competitionLabels.length > 0 && (
        <div className="structured-news-relations">
          {competitionLabels.slice(0, 2).map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      )}
      {url && <a className="news-original-link" href={url} target="_blank" rel="noopener noreferrer"
        onClick={(event) => openArticle(event, url)}>{t.newsReadOriginal}<span aria-hidden="true"> ↗</span></a>}
    </article>
  );
}
