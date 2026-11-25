# Remote access setup — 21 November 2026

User returned to Pi's LAN and requested remote access setup. Connected via known
SSH host identity. Installed Tailscale 1.104.7 on Windows using winget (installer
hash verified) and on Pi using the official Debian trixie stable installer.
Pi tailscaled service is active. Windows client initially Logged out.

Pi setup uses hostname `iqair-pi`, accept-dns=false to preserve its existing LAN
DNS, with ordinary OpenSSH over the tailnet. No exit node, subnet route, Tailscale
SSH takeover or router port forwarding enabled. Both device login URLs generated;
user must authorize them into the same tailnet. Access and off-LAN verification
remain pending until authorization completes.

Installation connection was briefly reset while Windows networking changed.
Reconnected successfully: Pi Tailscale binary and daemon were installed, collector
still active. Stale temporary sudo file removed after reconnect. An automatic
attempt to open sign-in URLs was rejected as "blocked by policy"; user received
manual links instead. Credential contents are not stored in this report.

## Collector check

At 10:50 WIB, collector and Drive timer were active. Last scheduled source fetch
at 10:15 WIB inserted BMKG 24.3 µg/m³ for source label 09:00 WIB; accepted counts
showed 18 inserts, 1 revision, 20 unchanged runs and 0 BMKG errors.

Stored source captures demonstrate repeated timestamps. The label
2026-11-19T06:00:00Z was returned on multiple fetches, including fetches as late as
2026-11-20T04:15:00Z. Therefore the collector did receive old/repeated source state
and correctly avoided new canonical rows. This does not determine whether the
sensor, provider publication, caching or page delivery caused those old labels.
No measurements were fabricated and no scraper restart was needed for the
currently successful BMKG run. Missing hours are not recovered by this diagnosis.

## Acceptance steps after device authorization

### Verified after authorization, 21 November 2026

Both clients report Running and the same tailnet. Pi is online as `iqair-pi`,
Tailscale IPv4 `100.98.100.126`. Windows Tailscale ping succeeded (10 ms, direct
LAN path), followed by successful ordinary SSH over that Tailscale IP. SSH host
identity was checked against the existing trusted `raspberrypi.local` key; the
verified IP alias was saved to Windows known_hosts. LAN mDNS resolution failed
during this check, but access through the Tailscale IP worked.

Pi tailscaled, iqair-pilot.service and iqair-drive-sync.timer are all active and
enabled. Latest report: Amaranta 43 slots / 0 failed runs, BMKG 24 / 0, DTETI 39 / 1
(cumulative failures). Off-LAN testing remains pending; the successful overlay
test used a direct LAN path.

From Windows CMD or PowerShell, with Tailscale connected:

```text
ssh pi@100.98.100.126
```

For the remaining acceptance test, move the laptop to a mobile hotspot, keep
Tailscale connected and repeat that command. Pi must remain online at home.

1. Read each device's BackendState and its own Tailscale IP; compare tailnet identity.
2. Ping Pi's Tailscale IP from Windows.
3. SSH through that IP, pinning Pi's already-known SSH host key.
4. Verify collector and Drive services still active.
5. User moves laptop to mobile hotspot and repeats SSH to demonstrate off-LAN use.
   Same-LAN testing alone does not prove remote access from every external network.

HP use: install Tailscale under the same account and use an SSH client. Pi must
remain powered and connected. Review tailnet membership/port-22 access policy and
device-key expiration to cover the intended operating period.
