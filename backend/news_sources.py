"""Reviewed deployment configuration. Public RSS availability is not a licence.

Keep local and VPS configuration identical. Never put test fixtures or credentials
in NEWS_SOURCES. Approval must cover commercial metadata redistribution, even
while MatchPulse itself is free. No publisher is enabled by default.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, unquote


def utc_text(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timezone required")
    return parsed.astimezone(timezone.utc)


def safe_url(value, hosts, *, canonical=False):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in unquote(value)):
        raise ValueError("Invalid news URL")
    parts = urlsplit(value.strip())
    host = (parts.hostname or "").lower()
    if (parts.scheme != "https" or not host or host not in hosts or parts.username
            or parts.password or parts.port not in (None, 443)):
        raise ValueError("News URL is outside its approved hosts")
    if not canonical and parts.fragment:
        raise ValueError("Feed URLs cannot have fragments")
    query = parts.query
    if canonical:
        query = urlencode([(key, val) for key, val in parse_qsl(query, keep_blank_values=True)
                           if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}])
    return urlunsplit(("https", host, parts.path or "/", query, ""))


@dataclass(frozen=True)
class TeamMapping:
    publisher_id: str
    # One reviewed publisher team can have explicit identities in several competitions.
    targets: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class NewsSource:
    key: str
    name: str
    feed_url: str
    feed_hosts: tuple[str, ...]
    article_hosts: tuple[str, ...]
    format: str = "rss"  # RSS/Atom, or the metadata-only JSON adapter contract.
    category: str = "world"
    language: str = "en"
    enabled: bool = False
    commercial_metadata_approved: bool = False
    approval_reference: str = ""
    reviewed_by: str = ""
    approval_expires_at: str = ""
    summary_approved: bool = False
    image_approved: bool = False
    image_hosts: tuple[str, ...] = ()
    interval_seconds: int = 900
    team_domain: str = ""
    mapping_review_reference: str = ""
    team_mappings: tuple[TeamMapping, ...] = ()

    @property
    def source_key(self):
        key = self.key.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", key):
            raise ValueError("Invalid source identity")
        return key

    def approved(self, now=None):
        current = now or datetime.now(timezone.utc)
        if not (self.enabled and self.commercial_metadata_approved and self.approval_reference.strip()
                and self.reviewed_by.strip() and self.approval_expires_at):
            return False
        try:
            return parse_utc(self.approval_expires_at) > current
        except ValueError:
            return False

    def validate(self):
        from competition_service import get_competition
        from news_service import VALID_NEWS_CATEGORIES
        self.source_key
        safe_url(self.feed_url, self.feed_hosts)
        if (self.format not in {"rss", "json"} or self.category not in VALID_NEWS_CATEGORIES
                or not re.fullmatch(r"[a-z]{2}(?:-[A-Za-z]{2})?", self.language)
                or not 60 <= self.interval_seconds <= 86400 or not self.article_hosts):
            raise ValueError("Invalid source configuration")
        if self.team_mappings and (not self.team_domain or not self.mapping_review_reference):
            raise ValueError("Team mapping requires an explicit namespace and review")
        seen = set()
        for mapping in self.team_mappings:
            if not mapping.publisher_id or mapping.publisher_id in seen or not mapping.targets:
                raise ValueError("Ambiguous publisher team mapping")
            seen.add(mapping.publisher_id)
            for competition_key, team_id in mapping.targets:
                legacy = competition_key == "worldcup2026" and isinstance(team_id, str) and team_id.isascii() and team_id.isdigit()
                if (not get_competition(competition_key) or not isinstance(team_id, str)
                        or not (re.fullmatch(r"mp_team_[A-Za-z0-9_-]+", team_id) or legacy)):
                    raise ValueError("Mapping must use reviewed canonical team identities")
        return self

    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


NEWS_SOURCES: tuple[NewsSource, ...] = ()


def approved_sources(now=None):
    result = {}
    seen = set()
    for source in NEWS_SOURCES:
        source.validate()
        if source.source_key in seen:
            raise ValueError("Duplicate normalized source identity")
        seen.add(source.source_key)
        if source.approved(now):
            result[source.source_key] = source
    return result
