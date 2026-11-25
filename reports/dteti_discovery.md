# DTETI addition — 19 November 2026

User requested DTETI UGM as a third station. Discovered the station by following
the managed-station link on the Sensor IQAir DTETI contributor profile:
https://www.iqair.com/id/profile/qydys9nr2

Canonical station URL:
https://www.iqair.com/id/air-quality/indonesia/yogyakarta/sleman/smart-censor-dteti-lt-4

## Verified public browser evidence

Capture obtained by Chromium on Pi with HTTP 200, at 2026-11-19T08:40:27.601Z.
Saved selected public state and UI fragments in
`samples/discovery/dteti_browser_current.json`.

- Internal station ID: `dteti_ugm` (UGM is the user's requested alias).
- Source name: `Smart Censor DTETI Lt. 4`.
- Source contributor: `Sensor IQAir DTETI` (Education).
- Source station ID: `69cb6499b52a87c536f30bf8`.
- Route and details type: station. Timezone: Asia/Jakarta.
- Current estimated: false. Pollutant name pm25, explicit unit µg/m³.
- PM2.5 **23 µg/m³**, separate US AQI **77**.
- Source timestamp 2026-11-19T07:00:00Z matches UI label 14.00 Nov 19 WIB.
- End-label normalization follows IQAir's documented station aggregation semantics
  and the convention previously validated on the other two stations. The DTETI
  historical dropdown interaction timed out, so no successful historical-tooltip
  or full history extraction is claimed for this station.
- Public coordinates were exposed but canonical registry coordinates remain null
  pending review of sensor-location precision. Instrument calibration and campus
  affiliation were not independently verified beyond source contributor/name.

Verdict: GO_CURRENT_ONLY, with the same fail-closed identity/unit/time validation.
Station identity must match URL + ID + name + contributor. Current-only collection
does not imply historical recovery or benchmark-equivalent instrument quality.

## Implementation

Added target tuple, registry entry and CLI station selection (now derived from
the target registry). Existing `--all` includes the third station. Local CSV is
`data/dteti_ugm.csv`. Updated Drive filters to include exactly three station CSVs.
Pi service requires restart to load its new station list; its original 90-day
start/end remain unchanged. Earlier missing DTETI hours are not invented/backfilled.

## Tests

**55 passed in 7.10s**, including actual DTETI capture parsing, intercepted browser
decoding and three-station local ingest/CSV. Negative checks reject Sleman as
DTETI and DTETI as Sleman. Live deployment and first Drive upload are checked
separately after the local tests.

## Deployment verification

Updated Pi parser, CLI, registry and Drive copy filters. One-shot collection for
`dteti_ugm` succeeded: inserted 23 µg/m³ for interval end 2026-11-19T07:00:00Z.
Pi report retained 2 records each for the previous stations and added 1 DTETI
record, with 0 failures. Restarted existing service to load all three targets;
collector and Drive timer both verified active. Original 90-day window was not
reset. Third-station collection starts now; no previous hours were fabricated.

Drive copy succeeded and `rclone check` reported **0 differences, 3 matching files**.
Remote listing confirmed dteti_ugm.csv, MIME text/csv, 543 bytes. Future hourly
three-station cycles remain subject to normal monitoring; only DTETI's one-shot
and the other two stations' earlier scheduled cycle are proven at this checkpoint.
