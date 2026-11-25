# VPS Migration & Setup — 24 November 2026

Replaced the offline/damaged Raspberry Pi 3 with a Jakarta KVM VPS (`allo`, Ubuntu 24.04.5 LTS x86_64, 1 vCPU, 2 GB RAM, 25 GB NVMe).

## Provisioned environment

- **Host / SSH:** `<VPS_IP>:<SSH_PORT>`, SSH key auth (`id_ed25519`), dedicated non-root user `iqair`.
- **Swap & timezone:** 2 GB `/swapfile` (`vm.swappiness=10`), system timezone `Asia/Jakarta` (WIB).
- **Runtime:** `/home/iqair/iqair-collector`, Python 3.12.3 `.venv`, Playwright bundled Chromium + OS deps, `rclone` 1.60.1.
- **Codebase deployed:** includes the 22 November 2026 extended CSV update (61 columns including `ditangkap_pada_wib`, AQI, weather, coordinates, extra pollutants, and JSON detail columns).

## Verification

- Offline parser and headless Playwright Chromium smoke test passed.
- Live `collect-once --all` succeeded for all 3 stations (`bmkg_sleman`, `amaranta_prambanan`, `dteti_ugm`) with 0 failures and 61 CSV columns; RAM available ~1.56 GB, 0 swap used, 18 GB disk free.
- `iqair-pilot.service` enabled and active (`COLLECTION_START_UTC=2026-11-19T07:42:03Z`, 90-day window through `2027-02-17T07:42:03Z`, hourly at `:15` WIB).

## Google Drive sync (`_new` suffix)

- Authorized `iqairdrive:` remote via SSH localhost tunnel (`tools/connect_drive.py`) into `/home/iqair/.config/rclone/rclone.conf` (mode `0600`), using the same Google Cloud OAuth project (`IQAir Collector`, scope `drive.file`).
- Confirmed target folder `IQAir-Yogyakarta` (`1z5V-2wfz-k7F71XPQ_lvuKX8sMDXnfEU`).
- `deploy/vps/sync-drive.sh` uploads via `rclone copyto` with `_new` suffix so existing Pi CSVs (19–21 Nov) remain untouched:
  - `bmkg_sleman_new.csv`
  - `amaranta_prambanan_new.csv`
  - `dteti_ugm_new.csv`
- First manual sync succeeded and `iqair-drive-sync.timer` is enabled (`:05/:20/:35/:50` WIB).

## Weather forecast & organized Drive update — 25 November 2026

- Added isolated weather forecast module (`src/iqair_collector/weather.py`) with dedicated SQLite store (`data/weather.sqlite3`) and partitioned CSV output:
  - **Open-Meteo (primary, hourly, `h=0..72`):** `temperature_2m`, `relative_humidity_2m`, `precipitation`, `rain`, `precipitation_probability`, `wind_speed_10m` (`m/s`), `wind_direction_10m`, `surface_pressure`, `cloud_cover`, `weather_code`. Partitioned daily (`open_meteo/YYYY-MM/open_meteo_YYYY-MM-DD.csv`).
  - **BMKG (secondary local official, 3-hourly, `adm4`):** `34.04.06.2002` (Sendangadi, `bmkg_sleman`), `34.04.06.2001` (Sinduadi, `dteti_ugm`), `34.04.09.2004` (Sambirejo, `amaranta_prambanan`), including numeric `tp` (`precipitation_mm`), `wd_deg`, `analysis_date_utc`, and operational `first_seen_at_utc`. Partitioned monthly (`bmkg/bmkg_YYYY-MM.csv`).
- Reorganized Google Drive `IQAir-Yogyakarta/`:
  - `00_archive_pi/` (3 legacy Pi CSVs moved safely)
  - `01_pm25_observed/` (3 active VPS `*_new.csv` files)
  - `02_weather_forecast/open_meteo/` and `02_weather_forecast/bmkg/`
  - `03_metadata/` (`stations_metadata.json`, `data_dictionary.md`)
  - `99_sqlite_backup/` (`state.sqlite3.gz`, `weather.sqlite3.gz`)
- Activated systemd timers:
  - `iqair-weather.timer` (`*:02:00` WIB hourly)
  - `iqair-drive-sync.timer` (`*:05,20,35,50:00` WIB)
  - `iqair-sqlite-backup.timer` (`03:30:00` WIB daily)
- Verified locally (`60 passed`) and live on VPS (first run took 4s for all 6 endpoints, 0 failures, RAM available 1,578 MB, 0 swap used).

## Quick operational commands

```bash
ssh -p <SSH_PORT> root@<VPS_IP> "systemctl status iqair-pilot.service --no-pager && systemctl list-timers 'iqair-*' --no-pager"
ssh -p <SSH_PORT> root@<VPS_IP> "journalctl -u iqair-pilot.service -u iqair-weather.service -n 20 --no-pager"
ssh -p <SSH_PORT> iqair@<VPS_IP> "cd ~/iqair-collector && .venv/bin/python -m iqair_collector report && .venv/bin/python -m iqair_collector weather-report"
```
