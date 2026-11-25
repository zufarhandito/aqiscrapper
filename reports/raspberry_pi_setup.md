# Raspberry Pi setup — 19 November 2026

## 90-day collection extension (latest)

User explicitly confirmed the original three-month/90-day requirement. Changed
service duration from 1 to 90 days, preserving original start
2026-11-19T07:42:03Z. New end is 2027-02-17T07:42:03Z (14:42 WIB).
Saved the old 24h unit in Pi deploy directory, verified the updated unit, installed
it and restarted the service while it was waiting for the next hourly slot.
Existing data and Google Drive sync timer were retained. Publishing state of
Google OAuth still needs review for refresh-token lifetime during the full run.
Journal readback confirmed the new end timestamp and next run 16:15 WIB.
Local report retained two observations per station with zero failed runs.
Google Drive timer's first scheduled sync also completed successfully at 15:20 WIB.

First scheduled source collection at 15:15:41 WIB succeeded: Sleman 25.5 µg/m³
for label 14:00 WIB, Amaranta 16 µg/m³ for label 15:00 WIB. This establishes one
successful scheduled cycle, not complete continuous availability for 90 days.

## Pilot activation (latest)

User reported successful live captures and one CSV observation for each station.
Installed and enabled `iqair-pilot.service` on Pi as user pi, working directory
`/home/pi/iqair-collector`. Window: 2026-11-19T07:42:03Z through
2026-11-20T07:42:03Z; first scheduled run 2026-11-19T08:15:00Z (15:15 WIB).
`systemd-analyze verify` passed and service state was active/running. Journal
confirmed the fixed collection window and next-run timestamp. It is enabled at
boot, but an expired window exits without starting a new 24-hour period.

The service uses a single scheduler, sequential stations, local CSV/SQLite and
system Chromium. It does not automatically restart after failures/access denial.
The scheduler now logs its window and next run. Windows regression tests after
that change: **52 passed in 4.92s**. This verifies activation, not successful future
scheduled runs or completion of the pilot. No immediate extra IQAir fetch was made.

Temporary sudo password file was removed after installation. SSH may be closed;
Pi must remain powered and online. Follow-up: inspect service journal and station
report after scheduled runs, then evaluate completeness and freshness.

## Initial installation

SSH password authentication succeeded using the secret mechanism; credentials
were not placed in project files or process command arguments. Host identity was
checked against the SSH known_hosts entry established on the first connection.

Verified environment:

- Debian GNU/Linux 13 (trixie), aarch64, 64-bit.
- Python 3.13.5; RAM 905 MiB; swap 904 MiB; root filesystem 7.3 GB free.
- Existing desktop and Chromium installed. Desktop settings were not changed.
- Project copied to `/home/pi/iqair-collector` with a fresh Linux `.venv`.
  Windows environment, credentials, database and private `.env` were not copied.
- Installed Playwright 1.65.2 and collector 0.1.0, using system Chromium
  154.0.8037.92 via optional BROWSER_EXECUTABLE_PATH setting.

Validation:

- Successfully launched system Chromium headless, set an offline HTML document,
  read its h1, and closed the browser.
- Available RAM during this simple page: about 433 MiB. This is a single snapshot,
  not a peak-memory benchmark or evidence of full IQAir-page reliability.
- Parsed the archived Amaranta capture successfully; initialized local storage;
  report returned an empty list. No real observations were copied to Pi.
- Live source and scheduler flags remain false; no IQAir request made on Pi.
- Windows regression suite after browser executable-path support: 52 passed in 5.22s.
- Initial setup output printing hit Windows encoding limitations after the remote
  command; the follow-up UTF-8 session confirmed successful remote installation.

Next: validate one live capture on Pi, monitor memory, then test hourly scheduling
and recovery before considering unattended production. SSH password was not changed.
