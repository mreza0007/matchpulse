# Phase 1 news engine

No real publisher is configured or enabled. RSS availability does **not** grant
redistribution or commercial rights. `news_sources.NEWS_SOURCES` is reviewed,
versioned configuration shared by local and VPS builds; there is no URL input API.

Before adding a source, record a rights-holder approval reference, reviewer,
expiry, exact HTTPS feed/article hosts, commercial metadata permission and polling
interval. Approve summaries and images separately. Images are URLs only, never
downloaded; do not enable image URLs without permission to display/hotlink them.
Re-review host and team mappings, licence changes and expiry. Disabled/expired
sources are excluded at read time; previously stored data is not destroyed.

## Operator migration (not executed by application startup)

Back up the database and verify the backup first. From backend:

    python -m migrations.news_v1 --db PATH
    python -m migrations.news_v1 --db PATH --migrate --backup-confirmed

The explicit migration adds four news tables and two lookup indexes in one
BEGIN IMMEDIATE transaction. It validates the complete schema signature and marker;
inconsistent/foreign states fail closed. Repeat execution is a no-op. Any failure
rolls back DDL and marker together. Existing application tables are untouched.
The backup flag is an operator attestation, not an automatic backup facility.
Runtime reads/writes never create a DB or migrate it. With no approved sources,
static notices work without news tables. Once sources are enabled, migration is
required; unavailable/inconsistent storage returns a sanitized 503.

## Ingestion

An independent scheduler job polls every minute only if licensed sources are
configured. Each source has persisted conditional headers, interval, exponential
backoff (60 seconds to 6 hours), bounded numeric Retry-After and a 120-second
lease. Crash recovery retries after lease expiry. One source failure is isolated.
Operator fixture/manual invocation: `python -m news_ingestion --db PATH`.

HTTPS only, exact redirect allowlist (maximum three redirects), public DNS pinned
to the validated address, verified TLS, 5-second socket timeout and 20-second
read deadline. OS DNS resolution may exceed that deadline. No credentials,
compressed feeds or arbitrary URLs. Maximum 1 MiB, 200 entries, XML depth 32;
UTF-8 only, DTD/entities rejected. RSS/Atom metadata and a JSON `items` adapter
(`id,url,title,date_published,summary,image,team_ids`) are supported. Article
content/body fields are ignored. Invalid links/timestamps/entries are skipped;
future publication times beyond five minutes are rejected. Missing dates are
not fabricated. No importance inference, scraping or news Telegram dispatch.

GUIDs are scoped by normalized source key; normalized canonical URLs are global.
Tracking parameters/fragments are removed. Old URL aliases survive updates.
Conflicting GUID/URL identities abort the entire poll transaction, not merge.
First publisher wins cross-source duplicates (including provenance/permissions).
Disabling that publisher hides its article even if another source supplied the
same URL; richer multi-source provenance is deferred. First ingestion time and
stable article ID survive refreshes. All successful poll writes are atomic.

Team associations use exact publisher identifiers and explicitly reviewed canonical
competition/team tuples only. No headline matching or ambiguous name heuristics.
The mapping review must verify IDs against authoritative competition team data;
validation checks format/competition, not provider ownership. Unknown IDs stay
unassociated. Mapping/config changes reset conditional headers to reprocess feeds.

Existing count/news envelope and filters remain. Pagination defaults to 50, max
100, offset max 10000; count is page count, not total. Sort publication DESC,
stable ID ASC. Offset pages may shift during ingestion. Static notices are labelled
`origin=static_notice`; publisher articles `origin=publisher`. Fallback is used only
with no eligible stored publisher articles, not to fill an empty filtered page.
No translation is fabricated. Approved original headlines populate their language.

## Phase 2

Secure actual commercial metadata licences; source-specific adapters/fixtures and
reviewed team mappings; frontend original-language headlines, attribution, links,
timestamps and pagination; operational monitoring/retention and editorial policy.
News notification preferences, explicit opt-in, importance review, per-user limits,
deduplication/outbox and startup stale-news suppression require a separate phase.
Do not reuse live-match send paths to broadcast news. No news preferences or
notification delivery are introduced in Phase 1.
