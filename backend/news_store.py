"""Explicitly migrated news storage; runtime access never creates a database."""
import hashlib
from pathlib import Path
import sqlite3

from news_schema import news_schema_state


class NewsStorageError(RuntimeError):
    pass


def connect(path=None, readonly=False):
    if path is None:
        from db_service import DB_PATH
        path = DB_PATH
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise NewsStorageError("News migration required")
    conn = sqlite3.connect(resolved.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        state = news_schema_state(conn)
        if state != "v1":
            raise NewsStorageError("News migration required" if state == "missing" else "Inconsistent news schema")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    except Exception:
        conn.close()
        raise


def save_articles(conn, source, articles, now):
    for item in articles:
        keys = [("*", "url", item["canonical_url"])]
        if item["guid"]:
            keys.append((source.source_key, "guid", item["guid"]))
        existing = {row[0] for key in keys for row in conn.execute(
            "SELECT article_id FROM news_article_keys WHERE source_key=? AND identity_type=? AND identity_value=?", key)}
        if len(existing) > 1:
            raise ValueError("Conflicting article identities")
        article_id = next(iter(existing), "news_" + hashlib.sha256(
            (source.source_key + "\x00" + (item["guid"] or item["canonical_url"])).encode()).hexdigest()[:32])
        row = conn.execute("SELECT source_key FROM news_articles WHERE id=?", (article_id,)).fetchone()
        values = (item["original_url"], item["canonical_url"], item["headline"], item["summary"],
                  item["image_url"], item["published_at"], source.category, source.language)
        if row is None:
            conn.execute("""INSERT INTO news_articles
                (id,source_key,ingested_at,original_url,canonical_url,headline,summary,image_url,published_at,category,language)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (article_id, source.source_key, now, *values))
        elif row[0] == source.source_key:
            conn.execute("""UPDATE news_articles SET original_url=?,canonical_url=?,headline=?,summary=?,image_url=?,
                published_at=?,category=?,language=? WHERE id=?""", (*values, article_id))
        if row is None or row[0] == source.source_key:
            conn.execute("DELETE FROM news_article_teams WHERE article_id=?", (article_id,))
            conn.executemany("INSERT INTO news_article_teams VALUES (?,?,?)",
                             [(article_id, competition, team) for competition, team in item["teams"]])
        for key in keys:
            conn.execute("INSERT OR IGNORE INTO news_article_keys VALUES (?,?,?,?)", (*key, article_id))


def read_articles(sources, *, category=None, competition_key=None, team_id=None,
                  favorites=None, limit=50, offset=0, path=None):
    conn = connect(path, readonly=True)
    try:
        placeholders = ",".join("?" for _ in sources)
        base = f"a.source_key IN ({placeholders})"
        args = list(sources)
        available = conn.execute(f"SELECT 1 FROM news_articles a WHERE {base} LIMIT 1", args).fetchone()
        if not available:
            return None
        conditions = [base]
        if category:
            conditions.append("a.category=?")
            args.append(category)
        if competition_key:
            expression = "t.competition_key=?"
            args.append(competition_key)
            if team_id is not None:
                expression += " AND t.team_id=?"
                args.append(str(team_id))
            conditions.append("EXISTS (SELECT 1 FROM news_article_teams t WHERE t.article_id=a.id AND " + expression + ")")
        if favorites is not None:
            pairs = sorted({(item["competition_key"], str(item["team_id"])) for item in favorites})
            if not pairs:
                return []
            # Favorites are persisted server-side, not arbitrary client-supplied SQL.
            if len(pairs) > 500:
                raise NewsStorageError("Too many favorite filters")
            conditions.append("EXISTS (SELECT 1 FROM news_article_teams t WHERE t.article_id=a.id AND (" +
                              " OR ".join("(t.competition_key=? AND t.team_id=?)" for _ in pairs) + "))")
            args.extend(value for pair in pairs for value in pair)
        rows = conn.execute("SELECT a.* FROM news_articles a WHERE " + " AND ".join(conditions) +
                            " ORDER BY a.published_at DESC,a.id ASC LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            source = sources[item["source_key"]]
            teams = [dict(team) for team in conn.execute(
                "SELECT competition_key,team_id FROM news_article_teams WHERE article_id=? ORDER BY competition_key,team_id", (item["id"],))]
            item.update(origin="publisher", source=source.name, original_headline=item["headline"],
                        image_permitted=bool(source.image_approved),
                        title_fa=item["headline"] if item["language"] == "fa" else "",
                        title_en=item["headline"] if item["language"] != "fa" else "",
                        tags=[], related_teams=teams, related_team_ids=[team["team_id"] for team in teams],
                        related_competition_keys=sorted({team["competition_key"] for team in teams}))
            if not source.summary_approved:
                item["summary"] = None
            if not source.image_approved:
                item["image_url"] = None
            result.append(item)
        return result
    finally:
        conn.close()
