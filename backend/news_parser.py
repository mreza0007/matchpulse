"""Metadata-only RSS/Atom and JSON adapters. Never ingest article bodies."""
from datetime import timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
import xml.etree.ElementTree as ET

from news_http import MAX_BYTES
from news_sources import parse_utc, safe_url, utc_text


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value, limit):
    parser = PlainText()
    parser.feed(str(value or ""))
    return " ".join(" ".join(parser.parts).split())[:limit]


def parse_feed(source, body, now):
    if len(body) > MAX_BYTES:
        raise ValueError("Feed too large")
    text = body.decode("utf-8-sig")
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("Unsafe XML")
    if source.format == "json":
        document = json.loads(text)
        items = document.get("items")
        if not isinstance(items, list):
            raise ValueError("Invalid metadata JSON")
    else:
        root = ET.fromstring(text)
        if root.tag.rsplit("}", 1)[-1] not in {"rss", "feed", "RDF"}:
            raise ValueError("Unsupported feed document")
        def depth(node, level=0):
            if level > 32:
                raise ValueError("Feed too deep")
            for child in node:
                depth(child, level + 1)
        depth(root)
        items = []
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
                continue
            fields, team_ids = {}, []
            for child in node:
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "category" and child.get("domain", child.get("scheme")) == source.team_domain:
                    team_ids.append(child.get("term") or child.text or "")
                if tag == "link" and child.get("rel", "alternate") == "alternate":
                    fields["url"] = child.get("href") or child.text
                elif tag in {"title", "guid", "id", "pubDate", "published", "description", "summary"}:
                    fields[tag] = child.text
                elif tag == "enclosure" and child.get("type", "").startswith("image/"):
                    fields["image"] = child.get("url")
            items.append({"id": fields.get("guid") or fields.get("id"), "url": fields.get("url"),
                          "title": fields.get("title"), "date_published": fields.get("pubDate") or fields.get("published"),
                          "summary": fields.get("summary") or fields.get("description"),
                          "image": fields.get("image"), "team_ids": team_ids})
    if len(items) > 200:
        raise ValueError("Too many feed entries")
    mappings = {mapping.publisher_id: mapping.targets for mapping in source.team_mappings}
    result = []
    for item in items:
        try:
            if not isinstance(item, dict):
                continue
            url = safe_url(item.get("url"), source.article_hosts, canonical=True)
            original = item["url"]
            headline = plain(item.get("title"), 500)
            guid = item.get("id") or ""
            if not isinstance(guid, (str, int)) or isinstance(guid, bool) or len(str(guid)) > 1024:
                continue
            date = item.get("date_published")
            try:
                published = parse_utc(date)
            except (ValueError, TypeError):
                published = parsedate_to_datetime(date)
                if published.tzinfo is None:
                    raise ValueError("Timezone required")
            if not headline or published > now + timedelta(minutes=5):
                continue
            team_ids = item.get("team_ids", [])
            if not isinstance(team_ids, list) or any(not isinstance(key, str) for key in team_ids):
                raise ValueError("Invalid publisher teams")
            teams = sorted({target for key in team_ids for target in mappings.get(key, ())})
            image = None
            if source.image_approved and item.get("image"):
                image = safe_url(item["image"], source.image_hosts, canonical=True)
            result.append({"guid": str(guid), "original_url": original,
                           "canonical_url": url, "headline": headline, "published_at": utc_text(published),
                           "summary": plain(item.get("summary"), 500) if source.summary_approved else None,
                           "image_url": image, "teams": teams})
        except (ValueError, TypeError, OverflowError, AttributeError):
            continue
    return result
