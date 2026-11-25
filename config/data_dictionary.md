# Data Dictionary — IQAir Yogyakarta PM2.5 & Weather Forecast Dataset

Dokumentasi struktur folder Google Drive (`IQAir-Yogyakarta/`) dan definisi kolom untuk mendukung pemodelan spatio-temporal PM2.5 (CIST-GNN + Future Meteorological Forecast Fusion) bebas *data leakage*.

## Struktur Folder Google Drive

```text
IQAir-Yogyakarta/
├── 00_archive_pi/              # Arsip 3 CSV lama dari Raspberry Pi (19–21 Nov 2026)
├── 01_pm25_observed/           # Observasi PM2.5 & cuaca teramati per jam dari VPS (61 kolom)
├── 02_weather_forecast/
│   ├── open_meteo/YYYY-MM/     # Prakiraan cuaca per jam Open-Meteo (h=0..72 jam), partisi harian
│   └── bmkg/                   # Prakiraan cuaca per 3 jam BMKG (level adm4), partisi bulanan
├── 03_metadata/                # stations_metadata.json & data_dictionary.md
└── 99_sqlite_backup/           # Backup harian database SQLite terkompresi (.sqlite3.gz)
```

## 1. Stasiun Pemantauan & Kode Wilayah BMKG (`adm4`)

| `station_id` | Nama Sumber IQAir | Latitude | Longitude | BMKG `adm4` | Kalurahan / Kapanewon |
|---|---|---:|---:|---|---|
| `bmkg_sleman` | SLEMAN | -7.7310 | 110.3540 | `34.04.06.2002` | Sendangadi, Mlati, Sleman |
| `dteti_ugm` | Smart Censor DTETI Lt. 4 | -7.7660 | 110.3718 | `34.04.06.2001` | Sinduadi, Mlati, Sleman |
| `amaranta_prambanan` | Amaranta Prambanan | -7.7697 | 110.5053 | `34.04.09.2004` | Sambirejo, Prambanan, Sleman |

Jarak geografis (Haversine):
- `bmkg_sleman` ↔ `dteti_ugm`: **4,36 km**
- `dteti_ugm` ↔ `amaranta_prambanan`: **14,72 km**
- `bmkg_sleman` ↔ `amaranta_prambanan`: **17,22 km**

## 2. `01_pm25_observed/*_new.csv` (Target & Historis PM2.5)

- **Target utama:** `pm25_ugm3` ($\mu\text{g/m}^3$, kontinu, `observed=True`, `estimated=False`).
- **Kunci waktu:** `interval_start_utc` dan `interval_end_utc` (interval 1 jam), plus `interval_start_local`, `source_label_local`, dan `ditangkap_pada_wib`.
- **Cuaca teramati halaman IQAir:** `temperature_source`, `humidity_source`, `pressure_source`, `wind_speed_source`, `wind_direction_source`, `weather_condition`.
- **Mutu data:** `quality_flags` (mis. `["stale"]`), `estimated`, `contributors_json`, `raw_snapshot_hash`.

## 3. `02_weather_forecast/open_meteo/YYYY-MM/open_meteo_YYYY-MM-DD.csv` (Sumber Utama Future Weather)

Dikumpulkan setiap jam (menit `:02` WIB) untuk horizon `lead_time_hours = 0..72`. Dipisahkan per hari berdasarkan `issue_date_wib`.

| Kolom | Definisi & Satuan |
|---|---|
| `station_id` | ID stasiun (`bmkg_sleman`, `dteti_ugm`, `amaranta_prambanan`) |
| `issue_hour_utc` | Jam terbit operasional UTC (pembulatan bawah ke jam bulat, kunci join dengan waktu prediksi $t$) |
| `forecast_issued_at_utc` | Waktu tepat penerbitan/pengambilan prakiraan UTC (`forecast_issued_at <= t`, bukti anti-leakage) |
| `ditangkap_pada_wib` | Format terbaca WIB dari `forecast_issued_at_utc` |
| `forecast_valid_utc` | Waktu target berlakunya prakiraan ($t+h$) dalam UTC |
| `forecast_valid_wib` | Waktu target berlakunya prakiraan ($t+h$) dalam WIB (`+07:00`) |
| `lead_time_hours` | Jarak horizon prakiraan $h$ dalam jam (`0` = jam berjalan/nowcast, `1..72` = prakiraan masa depan) |
| `req_latitude`, `req_longitude` | Koordinat stasiun yang diminta |
| `grid_latitude`, `grid_longitude`, `elevation_m` | Titik grid NWP & elevasi (m) yang dikembalikan Open-Meteo |
| `temperature_2m_c` | Suhu udara 2 m (°C) |
| `relative_humidity_2m_pct` | Kelembapan relatif 2 m (%) |
| `precipitation_mm` | Total presipitasi 1 jam sebelumnya (mm) |
| `rain_mm` | Curah hujan cair 1 jam sebelumnya (mm) |
| `precipitation_probability_pct` | Peluang presipitasi (%) |
| `wind_speed_10m_ms` | Kecepatan angin 10 m (m/s) |
| `wind_direction_10m_deg` | Arah asal angin 10 m (derajat meteorologis, 0–360°) |
| `surface_pressure_hpa` | Tekanan udara permukaan (hPa) |
| `cloud_cover_pct` | Tutupan awan total (%) |
| `weather_code` | Kode cuaca WMO |
| `raw_snapshot_hash` | SHA-256 payload JSON mentah di `weather.sqlite3` |

## 4. `02_weather_forecast/bmkg/bmkg_YYYY-MM.csv` (Sumber Sekunder Resmi Lokal)

Dicek setiap jam; deduplikasi otomatis berdasarkan `(station_id, analysis_date_utc, forecast_valid_utc)`. Dipisahkan per bulan berdasarkan `analysis_month_wib`.

| Kolom | Definisi & Satuan |
|---|---|
| `station_id`, `adm4`, `desa`, `kecamatan` | Identitas stasiun dan wilayah administrasi tingkat IV BMKG |
| `adm4_latitude`, `adm4_longitude` | Koordinat centroid kelurahan dari respons BMKG |
| `analysis_date_utc` | Waktu produksi/inisialisasi model NWP resmi BMKG (UTC, 2× sehari) |
| `first_seen_at_utc` | Waktu pertama kali VPS menerima `analysis_date` tersebut secara operasional (bukti anti-leakage) |
| `last_seen_at_utc` | Waktu terakhir pasangan prakiraan ini terkonfirmasi dari API |
| `ditangkap_pada_wib` | Format terbaca WIB dari `first_seen_at_utc` |
| `forecast_valid_utc`, `forecast_valid_wib` | Waktu berlaku prakiraan (interval 3 jam) |
| `lead_time_from_analysis_hours` | Selisih jam antara `forecast_valid_utc` dan `analysis_date_utc` |
| `lead_time_from_first_seen_hours` | Selisih jam antara `forecast_valid_utc` dan `first_seen_at_utc` |
| `temperature_c` | Suhu udara (`t`, °C) |
| `relative_humidity_pct` | Kelembapan relatif (`hu`, %) |
| `precipitation_mm` | Total presipitasi (`tp`, mm) |
| `wind_speed_kmh`, `wind_speed_ms` | Kecepatan angin (`ws` dalam km/jam, plus konversi ke m/s) |
| `wind_direction_deg`, `wind_direction_cardinal`, `wind_direction_to` | Arah asal angin (`wd_deg` °, mata angin `wd`, arah tujuan `wd_to`) |
| `cloud_cover_pct` | Tutupan awan (`tcc`, %) |
| `weather_code`, `weather_desc`, `weather_desc_en` | Kode dan deskripsi kondisi cuaca BMKG |
| `visibility_m`, `visibility_text`, `time_index` | Jarak pandang dan indeks interval BMKG |
| `raw_snapshot_hash` | SHA-256 payload JSON mentah di `weather.sqlite3` |

## 5. Aturan Anti-Data-Leakage Saat Pelatihan & Evaluasi

Saat memprediksi $Y_{t+h}$ dari waktu prediksi $t$:
- **Open-Meteo:** pilih baris dengan `forecast_issued_at_utc <= t` (biasanya `issue_hour_utc == t`) dan `forecast_valid_utc == t + h`.
- **BMKG:** pilih baris dengan `first_seen_at_utc <= t` (dan `analysis_date_utc <= t`) yang paling mutakhir sebelum $t$, untuk `forecast_valid_utc` terdekat/sesuai $t+h$.
