# Drive sync preparation — 19 November 2026

## Completed connection and first upload

- User downloaded a Desktop OAuth client JSON to Downloads. File inspected
  locally without printing its contents; client credentials placed only in Pi's
  private rclone config (mode 0600), not in project source or command arguments.
- SSH localhost tunnel handled browser OAuth on the laptop. User reported Success;
  remote rclone exited 0 with token configured. No token/password was printed.
- First copy uploaded `amaranta_prambanan.csv` (551 bytes) and `bmkg_sleman.csv`
  (555 bytes). `rclone check` returned **0 differences, 2 matching files**.
- Folder metadata readback via authenticated Google Drive API returned:
  https://drive.google.com/drive/folders/1z5V-2wfz-k7F71XPQ_lvuKX8sMDXnfEU
- Enabled `iqair-drive-sync.timer`; systemd verified next invocation
  2026-11-19 15:20 WIB. Collector pilot remained active. Subsequent timer runs
  are not yet verified at this checkpoint.
- Refined filters to ordered `--filter` rules after the installed rclone warned
  about combining include/exclude flags. Only the two CSV files are included.
- Callback tunnel logged a harmless connection-refused after OAuth completed
  (the listener had closed); helper now handles that case and shuts down its server.
- Original statements below about pending OAuth/timer describe preparation only.

OAuth publishing status is not verified. If still External/Testing, resolve the
seven-day refresh-token limitation before extending to 90 days. No sharing or
public permissions were added to the Drive folder.

## Original preparation

Installed Debian rclone package 1.60.1 on Pi. Collector pilot remained active.
Uploaded `deploy/sync-drive.sh` and systemd oneshot/timer definitions; shell syntax
and systemd unit verification passed. Timer is NOT activated, no Google account
is connected, and no Drive file has been uploaded yet.

Intended destination: `iqairdrive:IQAir-Yogyakarta` with the two CSV station files.
Uses rclone **copy**, not sync/move: no destination deletion. Includes match only
the two station filenames; database, .env and credentials are excluded. Upload
process is separate from acquisition, scheduled at :05/:20/:35/:50, with one
transfer at a time and bounded timeouts. Local CSV remains authoritative; a failed
upload is retried by a later timer invocation without blocking collection.

Pending: user-owned Google OAuth Desktop client credentials, consent using
`drive.file` scope, remote configuration, first upload/readback, and timer activation.
Rclone docs say its shared client is being retired during 2026, so do not assume
that it will work throughout a 90-day project. An External app left in Testing
normally receives a refresh token that expires after seven days for Drive scopes;
resolve publishing state before unattended long-term operation.

References:
- https://rclone.org/drive/
- https://rclone.org/remote_setup/
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- https://developers.google.com/identity/protocols/oauth2
