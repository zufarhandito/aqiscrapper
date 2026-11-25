# Phase 0 — IQAir Yogyakarta discovery

## Update: automation implementation, 19 November 2026

Implemented a local Playwright/Chromium adapter for the observed public page-state
format, PostgreSQL persistence with station locks, raw selected-payload hashes,
deduplication/revision transactions and quarantine; CLI one-shot collection,
hourly scheduler, status report and CSV export are available. This supersedes
earlier statements that those modules do not exist.

The technical live evidence remains the 18 November manual browser inspection
below. New browser pipeline tests use intercepted synthetic reference-table HTML
built from the actual decoded captures; they do not establish compatibility with
current live IQAir HTML. PostgreSQL tests use isolated temporary schemas.
See the latest validation report for executed results.

No new IQAir live request or scheduled collection was performed in this change.
User confirmed no automation permission. Access flags remain false by default,
as required by the SRD. Full 48-hour history, backfill, Parquet, per-period coverage,
VPS service installation and 48-hour/7-day pilots remain pending.

## Update: successful browser inspection, 01:56–01:59 UTC

**This update supersedes the initial runtime access verdict below.** Direct HTTP
remains denied, but the shared browser successfully opened both public station
pages, showing a Log in link; no Google login or session transfer was needed.
Technical verdict for each station: **`GO_CURRENT_ONLY` (browser-capture PoC)**.
This does not claim an unattended collector, permission for recurring use, or a
passed pilot. User confirmed no access/automation authorization is available.

- SLEMAN: provider ID `7165697aab08555d97b4`; current PM2.5 38.6 µg/m³;
  current.ts `2026-11-18T00:00:00.000Z`; UI label 07.00 Nov 18;
  PM2.5 history selected in UI showed **06.00–07.00 18 Nov**, value 38.6 µg/m³.
- Amaranta: provider ID `66d95425fefa97e65599ead8`; current PM2.5 53 µg/m³;
  current.ts `2026-11-18T01:00:00.000Z`; UI label 08.00 Nov 18;
  PM2.5 history selected in UI showed **07.00–08.00 18 Nov**, value 53 µg/m³.
- Both public page states explicitly identify type `station`, timezone
  `Asia/Jakarta`, matching contributors, and current.estimated=false. Current
  timestamps match the **end** of the UI intervals. This supports end-label
  semantics for the two captured current records, with one UI comparison each.
- Provider coordinates were exposed: Sleman (-7.731, 110.354); Amaranta
  (-7.7697, 110.5053). They remain excluded from canonical registry coordinates
  until sensor location precision/metadata is reviewed.
- Both historical UI dropdowns allow PM2.5 and display µg/m³. This resolves the
  earlier question about whether the chart can show concentration. It does not
  prove extraction of all 48 hourly points. No full series, gap recovery, locale
  check, update observation, or 3–5-point UI comparison is completed yet.

### Capture method and parser scope

Inspected the public DOM and inline React Router state already delivered with
the station page. Parsed the JSON string argument to
`window.__reactRouterContext.streamController.enqueue(...)` with JSON.parse,
then decoded its indexed reference table; no script eval or private endpoint was
used. Selected only the public station route's type/details metadata/current
and matching UI fragments. Customer, environment and session fields were not saved.

`samples/discovery/*_browser_current.json` are **derived, selected captures** of
that public state, not original HTTP responses. The separate history captures
preserve UI text after switching its parameter to PM2.5. Captures record browser
capture time, which is distinct from measurement time. Source request status was
not exposed by this method and no HTTP 200 is fabricated.

`parse-browser-capture` now parses these actual current fixtures, validates
URL/type/ID/name/contributor/unit/time and rejects estimated/city/AQI/forecast-only
inputs. The generic HTML extractor still fails closed: it is not yet a standalone
browser acquisition implementation. `collect-once` remains disabled.

**Next technical step:** package this browser acquisition in a reproducible local
adapter, add full observed-history extraction and more UI comparisons. A
current-only collection path is technically supported; scheduling remains subject
to the SRD authorization gate. No bypass or login credential is needed for the
successful inspections above.

---

## Initial direct-HTTP audit (retained for provenance)

Audit: 18 November 2026. Local HTTP captures: 01:32:26–01:32:27 UTC
(08:32 WIB). Environment: Windows, Python 3.13.14, Docker CLI 28.3.0.

## Decision

**Gate A NOT PASSED.** Both targets remain `BLOCKED_ACCESS` for this runtime.
Station page identities are supported by web-reader evidence, but there is no
successful raw station fixture, verified extraction method, or hourly series.
Neither `GO_CURRENT_ONLY` nor `GO_STATION_PM25_HOURLY` is justified.

Phase 1 can start only as a contract/interface and rejection-test foundation.
A real positive parser, successful collection, DB ingestion and pilots are pending.

## Evidence channels and limitations

1. Direct HTTP: one request per supplied station/city/documentation URL using
   Python urllib and identifying User-Agent `iqair-yogyakarta-research-discovery/0.1`.
   All four requests returned 429. Exact response bytes and metadata/hash are in
   `samples/discovery/`. Requests were not retried. The newly discovered Amaranta
   URL was not requested directly after observing host denials.
2. Web reader: independently returned readable IQAir pages, sometimes cached.
   This confirms visible page content only, not local automated availability.
   No raw successful HTML, structured state, browser tooltip comparison or network
   response was captured. Search reader results must not become measurement fixtures.

## BMKG Sleman

- URL: https://www.iqair.com/id/air-quality/indonesia/yogyakarta/sleman/sleman
- Web-reader title identifies SLEMAN station near Sleman; contributor matches
  Indonesian Meteorology, Climatology, and Geophysics Council.
- Rendered current block showed PM2.5 **38.6 µg/m³**, separately from US AQI 109;
  displayed source label **07.00, Nov 18 Waktu setempat**. This is an evidence
  observation, not an ingested record. Year/zone and exact machine timestamp
  were not extracted from a raw response.
- A separate hourly forecast section was visible. It is excluded from observed data.
- Local capture `samples/discovery/sleman.html` returned 429.
- Stable provider station ID, sensor coordinates, sensor method/correction,
  source timestamp encoding and historical PM2.5 concentration series: unverified.
- Verdict: `BLOCKED_ACCESS`; secondary `BLOCKED_UNVERIFIED_SOURCE` and
  `BLOCKED_TIMESTAMP_SEMANTICS` for extraction.

## Amaranta Prambanan

- Discovery chain: Yogyakarta city contributor link →
  https://www.iqair.com/id/profile/c4lypuefl → managed station link →
  https://www.iqair.com/id/air-quality/indonesia/yogyakarta/yogyakarta/amaranta-prambanan
- This is an individual station page. Name and Hotel Amaranta Prambanan
  contributor match. `c4lypuefl` is a contributor profile identifier, **not** a station ID.
- Web-reader station result was marked crawled last month and showed PM2.5
  **42 µg/m³**, US AQI 117, label **19.00, Okt 18 Waktu setempat**.
  It supports identity and visible concentration but does not prove current data.
- The city result showed a different value/time; it was not used as Amaranta's
  measurement. `samples/discovery/yogyakarta.html` is a denied city response.
- Direct Amaranta fetch was not attempted after host-level denials. The runtime
  access verdict reflects those denials, not a claimed 429 capture for this URL.
- Stable provider station ID, coordinates, current timestamp, correction metadata,
  and historical PM2.5 concentration series remain unverified.
- Verdict: `BLOCKED_ACCESS`; secondary `BLOCKED_UNVERIFIED_SOURCE` and
  `BLOCKED_TIMESTAMP_SEMANTICS`. Individual page URL is now discovered.

## Time and history

IQAir's official computation document explains retrospective hourly averages
and gives an 11:00 label for the preceding 10:00–10:59 interval:
https://www.iqair.com/support-articles/air-quality/data-computation
This is documentation evidence, not empirical confirmation of either target's
machine timestamps. No timestamp is inferred from fetch time or a partial label.

The provided history documentation URL was denied locally. No 48-hour station
concentration series was captured or verified. No history endpoint, selector,
unit switch, locale behavior or backfill capability is claimed. A 3–5-point
parser/UI comparison and update observation cannot yet be completed.

## Open risks and next gate

- Automated access and recurring-use authorization are unconfirmed; no bypass,
  proxy rotation, CAPTCHA handling or scheduled collection is implemented.
- Need an authorized successful raw response/HTML plus metadata for **each**
  station, including full timestamp, timezone, units, observed/forecast separation
  and station identity. Obtain it through approved access or an official data option.
- Validate source time semantics empirically, compare 3–5 parsed points against UI,
  and check hourly update behavior before assigning any GO verdict.
- Verify 48-hour observed concentration separately; otherwise explicitly use
  current-only after its own gate passes.
- Coordinates and instrumentation remain null/unverified; spatial graph use is pending.
- Then implement an actual source adapter and positive offline fixtures. Continue
  DB/idempotency/revision/quarantine work and the 48-hour pilot only after gates pass.

## Files and validation scope

Created registry, typed reading contract, extractor protocol, fail-closed placeholder,
offline CLI, real denied captures, synthetic contract tests, Python packaging and
Docker/PostgreSQL Compose skeleton. No DB schema, ingestion, scheduler, backfill,
report/export implementation or production collection is claimed at this phase.

Validation results are recorded in `reports/validation.md` after running checks.
