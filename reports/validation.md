# Foundation validation — 18 November 2026

## Third-station addition — 19 November 2026 (latest)

Added Smart Censor DTETI Lt. 4 / Sensor IQAir DTETI (`dteti_ugm`), using observed
public station ID, URL, concentration unit and full UTC label from a Pi capture.
**55 passed in 7.10s**. New checks cover actual capture parsing, intercepted
browser decoding, three-station CSV output and rejection of identity swaps.
Live one-shot inserted 23 µg/m³; all three Drive CSVs matched local via checksum.
Collector and Drive timer active after deployment; collection end unchanged.
See `reports/dteti_discovery.md` for evidence and historical/time-comparison limits.

## Local CSV change — 19 November 2026 (latest)

- User requested local station files and removal of the Docker/PostgreSQL requirement.
- Runtime now uses standard-library SQLite bookkeeping and automatically generated
  CSV per station; no PostgreSQL driver import, database server, or Docker is needed.
- **52 passed in 5.83s**, no skips, without PostgreSQL test infrastructure. Tests
  cover two-station local ingest, dedup/revisions, quarantine/partial failure,
  denial stopping the batch, overlapping writer rejection, CSV correctness and
  recovery after an atomic CSV replacement fails (e.g. Excel file lock), alongside
  the existing parser/browser/scheduler tests.
- Read-only migration copied **1 real observation** from the user's old PostgreSQL
  store. Source data and Docker volume were retained. Re-running migration imported
  0 observations, confirming no duplicate. The local report shows 1 slot and its CSV.
  The old PostgreSQL container was stopped after verification. Historical results below
  describe the previous implementation; that test backend has been removed.
- No new IQAir request, scheduler run, or Raspberry Pi benchmark was performed.
  Browser binaries remain necessary; Chromium is still the dominant resource risk.

## Automation implementation — 19 November 2026 (latest)

- Installed project dependencies: Playwright 1.65.2, psycopg/psycopg-binary 3.3.9,
  python-dotenv 1.2.4. Installed Chromium and browser dependencies on Windows.
- Started Docker Desktop, then an ephemeral PostgreSQL 16 container bound only
  to `127.0.0.1:55432`, with trust authentication for this isolated local test.
  No production database was used; each integration test used its own UUID schema.
- Full suite with `TEST_DATABASE_URL`: **50 passed in 17.89s**, no skips.
- Browser tests: actual Chromium execution with all requests intercepted;
  synthetic React Router reference-table HTML built from original decoded
  station captures, 401/403/429/500 rejection with one navigation only,
  changed-page rejection, no unrelated customer field persisted.
- Scheduler tests: UTC/hour rollover, expired 90-day window does not restart,
  access denial propagates a stop condition through the CLI.
- PostgreSQL integration: two-station insert, identical repeats deduplicated,
  revised value retains old reading, invalid payload quarantined while the other
  station continues, host denial stops batch, overlapping job skipped, CSV values
  and row counts match canonical observations. Temporary schemas were dropped.
- `compileall` passed; Compose configuration validation passed. Initial validation
  failed because `.env` was absent; optional env-file loading fixed that while
  the database password remains required through interpolation.
- CLI help and denied-by-default `collect-once --all` smoke checks passed.
  No source request occurred in that denied smoke check.
- Database test container stopped/removed after the checks. Docker images and
  browser binaries remain installed for development. No collector daemon runs.

Limitations: no new live IQAir fetch or unattended pilot, no Linux image build,
no 48-hour series/backfill, Parquet, period coverage or VPS startup service tested.
The implementation is a current-only development tool, not a demonstrated
90-day production deployment. Live flags remain false, per SRD access requirements.

---

## Browser follow-up

- Final rerun after registry/documentation updates: **36 passed in 0.15s**.
  Installed CLI smoke checks parsed both actual browser captures successfully:
  Sleman 38.6 µg/m³ for 23:00–00:00 UTC and Amaranta 53 µg/m³ for
  00:00–01:00 UTC, using source end labels rather than capture time.

- `python -m pytest -q`: **36 passed in 0.38s** after adding the browser-capture
  parser: two real selected current captures, nine negative source cases and one
  station-swap rejection, in addition to the original 24 tests.
- Browser successfully opened both public station URLs without signing in.
  Read current PM2.5/units, full state timestamp, identity and timezone; selected
  PM2.5 on each history chart and checked displayed current interval/value.
- Initial accessibility snapshot timed out; DOM evaluation in the same browser
  succeeded. No switch to another browser or HTTP retry was needed.
- No full history series or unattended browser acquisition was implemented.
  The generic source adapter and live collect command remain blocked.

## Initial foundation validation

- Runtime: Python 3.13.14 on Windows; isolated `.venv` created.
- `python -m pip install -e '.[dev]'`: passed, pytest 9.2.0 installed.
- `.venv/Scripts/python -m pytest -q`: **24 passed in 0.65s**.
- `python -m compileall -q src tests`: passed.
- Installed CLI subprocess smoke checks: `discover` exit 0;
  real denied `parse-fixture` exit 2 (`BLOCKED_ACCESS`, accepted_count 0);
  `collect-once` exit 2 (`BLOCKED_ACCESS`, accepted_count 0).
- `docker compose --profile discovery config --quiet`: passed with a temporary
  validation password in the process environment. No secret was written to disk.

Tests cover integrity and rejection of four real HTTP 429 captures, rejection of
unverified synthetic payloads, blocked collection, timezone-aware/UTC timestamp
contract, hourly boundaries, end-label mapping, unknown time semantics, numeric
validation, unit/forecast exclusion and preserving flagged extreme values.

An initial pytest invocation occurred before pip installation finished and failed
with `No module named pytest`; after installation, the full test run above passed.

Limits: no positive real station parser tests, empirical UI comparison, live
extraction, identity adapter validation, locale handling, DB integration, migrations,
idempotent writes, revisions, scheduling, backfill, exports or pilots have passed
or been implemented. Docker configuration was validated; images were not built,
services were not started, and Python 3.12 in the image was not executed.
No 48-hour/7-day/90-day collection was run.
