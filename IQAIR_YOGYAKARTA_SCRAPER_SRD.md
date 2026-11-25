# IQAir Yogyakarta Station-Level Data Collector

> **Additional user-approved scope, 19 November 2026:** collect a third individual
> station, Smart Censor DTETI Lt. 4 / Sensor IQAir DTETI (`dteti_ugm`). Include its
> own CSV and Drive copy in `--all`, preserving the original collection end date.
> See `reports/dteti_discovery.md` for observed identity and limitations. Original
> two-station scope text below is retained as historical context.

> **Amendment, 19 November 2026 — user-approved storage change:** PostgreSQL and
> Docker are no longer required. Deliver one local CSV per station for manual
> transfer, backed by a local SQLite bookkeeping file (Python standard library,
> no database server) to retain deduplication, revisions, quarantine and provenance.
> This explicit user direction supersedes PostgreSQL/Docker requirements below;
> the original specification is retained as historical context. Browser collection
> remains current-only; Raspberry Pi 3 performance is not yet validated.
## Technical Specification & Software Requirements Document (SRD)

**Version:** 1.0  
**Tanggal:** 18 November 2026  
**Status:** Ready for AI-agent discovery and proof of concept (PoC); **belum** siap dinyatakan production-ready  
**Pemilik proyek:** Penelitian tesis S2  
**Tesis:** *Spatio-Temporal Air Quality Prediction and Health-Aware Recommendation using Graph Learning*  
**Bahasa implementasi yang direkomendasikan:** Python 3.12+  
**Zona waktu operasional:** `Asia/Jakarta` (UTC+07:00)

> **Instruksi untuk AI Agent:** Baca seluruh dokumen sebelum menulis kode. Bedakan `VERIFIED`, `ASSUMPTION`, dan `TO_BE_VERIFIED`. Jangan mengarang endpoint, selector, station ID, koordinat, data historis, atau hasil scraping. Fase pertama adalah *station identity verification* dan *technical discovery*, bukan langsung menjalankan scraper produksi.

---

## 1. Executive Summary

Bangun **data collector** kualitas udara untuk **dua stasiun tertentu di wilayah DI Yogyakarta** yang informasinya ditampilkan pada IQAir:

1. **BMKG Sleman** — nama stasiun pada IQAir: **SLEMAN**; kontributor: *Indonesian Meteorology, Climatology, and Geophysics Council*.
2. **Hotel Amaranta Prambanan** — nama stasiun pada IQAir: **Amaranta Prambanan**; kontributor: *Hotel Amaranta Prambanan*.

Collector ditargetkan mengambil **konsentrasi PM2.5 aktual (µg/m³)** dengan **resolusi per jam** selama **90 hari**. Dataset ini adalah **dataset pendamping / studi kasus lokal**, **bukan** dataset utama tesis. Dataset utama tesis tetap **Beijing Multi-Site Air Quality Data**.

Tujuan sistem: menghasilkan rekaman data yang **berasal dari stasiun yang tepat**, **timestamp-nya dapat diaudit**, **tidak bercampur dengan prakiraan atau agregasi kota**, **idempotent**, dan **siap diekspor untuk pipeline machine learning**.

**Batasan kritis:** keberadaan nilai PM2.5 pada halaman publik **tidak membuktikan** adanya endpoint data terstruktur yang stabil. Dokumentasi IQAir menyebut grafik historis hourly 48 jam, tetapi **belum diverifikasi** bahwa grafik stasiun yang ditarget menyediakan seluruh titik PM2.5 konsentrasi dalam format yang dapat diekstrak otomatis. Hal ini merupakan **go/no-go pertama**.

**Status akses:** Dokumen ini mengevaluasi dan merancang kemampuan teknis. Sebelum pengambilan otomatis berkala, pastikan penggunaan yang direncanakan telah memperoleh otorisasi yang sesuai. Tidak ada persyaratan untuk melewati CAPTCHA, blokir akses, atau kontrol keamanan.

---

## 2. Konteks Penelitian & Batas Scope

### 2.1 Konteks akademik

- **Dataset utama:** Beijing Multi-Site — digunakan untuk training, eksperimen, dan evaluasi metodologi spatio-temporal graph learning.
- **Dataset Yogyakarta:** data lokal tambahan untuk studi kasus terbatas / uji transferabilitas dan demonstrasi alur rekomendasi berbasis kualitas udara.
- **Target polutan lokal utama:** **PM2.5** dengan unit **µg/m³**.
- **Dataset Yogyakarta tidak boleh diklaim setara dengan benchmark Beijing** tanpa pemeriksaan quality control, kesesuaian sensor, gap, dan metadata.

### 2.2 In scope

- Mendeteksi dan memverifikasi halaman **stasiun individual**.
- Mengambil nilai PM2.5 **observed**, bukan AQI/forecast.
- Menginspeksi apakah histori 48 jam memuat konsentrasi PM2.5 per jam.
- Menjadwalkan koleksi per jam setelah PoC lolos.
- *Backfill* dari histori yang benar-benar tersedia (jika terbukti bisa diekstrak).
- Menormalisasi timestamp dan unit; memvalidasi data; menyimpan provenance.
- Menyimpan data ke PostgreSQL dan mengekspor CSV/Parquet.
- Monitoring: missing, stale, failures, perubahan struktur halaman.
- Menyediakan unit, integration, dan smoke tests.

### 2.3 Out of scope

- Training atau tuning model GNN, LSTM, atau model forecasting lain.
- Membangun frontend/dashboard pengguna (boleh ditambahkan belakangan).
- Mengumpulkan data dari puluhan kota/stasiun.
- Menebak PM2.5 dari AQI sebagai pengganti pengukuran konsentrasi.
- Menganggap forecast sebagai observation.
- Bypass CAPTCHA, stealth fingerprinting, proxy rotation untuk menghindari blokir, atau unauthorized reverse engineering.
- Mengklaim kualitas instrumen ataupun lisensi penggunaan tanpa bukti.

---

## 3. Daftar Stasiun Target (Source Registry)

| `station_id` internal | Nama yang dicari | Contributor yang diharapkan | Referensi halaman terverifikasi | Status |
|---|---|---|---|---|
| `bmkg_sleman` | SLEMAN | Indonesian Meteorology, Climatology, and Geophysics Council (BMKG) | `https://www.iqair.com/id/air-quality/indonesia/yogyakarta/sleman/sleman` | **VERIFIED:** individual station page dan nilai PM2.5 terlihat |
| `amaranta_prambanan` | Amaranta Prambanan | Hotel Amaranta Prambanan | `https://www.iqair.com/id/air-quality/indonesia/yogyakarta/yogyakarta` (referensi **halaman kota**, bukan station URL) | **VERIFIED:** stasiun terdaftar; **TO_BE_VERIFIED:** halaman/identifier stasiun individual |

### 3.1 Kewajiban identifikasi

1. Untuk **BMKG**, cocokkan **nama stasiun + kontributor**; jangan hanya mengandalkan path URL yang berakhiran `/sleman`.
2. Untuk **Amaranta**, temukan tautan/identifier station individual secara manual melalui antarmuka IQAir, profil kontributor, atau peta stasiun yang sah diakses. Jika belum ditemukan, **jangan diam-diam mengganti target menjadi halaman kota**.
3. Halaman Kota Yogyakarta saat diperiksa menyatakan kontribusi satu stasiun Amaranta; situasi ini **bisa berubah**. Satu stasiun pada saat tertentu tidak menjamin agregasi kota identik dengan data stasiun pada semua jam.
4. Simpan koordinat perangkat **hanya setelah** diverifikasi dari sumber metadata terpercaya. Lokasi hotel atau kantor BMKG tidak otomatis merupakan koordinat sensor.
5. Station ID internal harus stabil; perubahan slug IQAir tidak boleh membuat identitas stasiun baru.
6. Kontributor BMKG pada IQAir tidak dengan sendirinya membuktikan jenis alat, metode kalibrasi, atau kesetaraan dengan instrumen lain milik BMKG.

### 3.2 Contoh konfigurasi awal (bukan bukti identitas)

```yaml
stations:
  - id: bmkg_sleman
    display_name: "SLEMAN (BMKG)"
    provider: iqair
    expected_contributor: "Indonesian Meteorology, Climatology, and Geophysics Council"
    candidate_url: "https://www.iqair.com/id/air-quality/indonesia/yogyakarta/sleman/sleman"
    identity_status: verified_page
    latitude: null
    longitude: null

  - id: amaranta_prambanan
    display_name: "Amaranta Prambanan"
    provider: iqair
    expected_contributor: "Hotel Amaranta Prambanan"
    candidate_url: null
    discovery_reference_url: "https://www.iqair.com/id/air-quality/indonesia/yogyakarta/yogyakarta"
    identity_status: needs_station_url
    latitude: null
    longitude: null
```

---

## 4. Fakta Terverifikasi vs Hipotesis Teknis

### 4.1 Verified (per 18 November 2026)

- **SLEMAN** merupakan halaman station-level dengan kontributor BMKG, dan menampilkan PM2.5 dalam µg/m³.
- **Amaranta Prambanan** tercatat sebagai stasiun pada peta/halaman Yogyakarta; halaman kota menampilkan PM2.5 µg/m³.
- IQAir mendokumentasikan **grafik histori 48 jam hourly**, **30 hari daily**, dan kemampuan mengganti parameter pada grafik lokasi.
- IQAir menyatakan publikasi data station/city berupa agregasi per jam dengan timestamp retrospektif: contoh, label pukul 11:00 merepresentasikan pengukuran selama 10:00–10:59.
- Halaman juga menampilkan **hourly forecast**; forecast ini **bukan data observed** dan tidak boleh masuk tabel observasi.

### 4.2 To be verified by AI Agent

- URL dan identifier unik stasiun Amaranta.
- Apakah **setiap** stasiun menampilkan histori 48 jam (bukan hanya grafik kota).
- Apakah nilai grafik historis adalah **konsentrasi PM2.5 µg/m³**, bukan AQI+ atau indeks lain.
- Apakah data grafik ada pada HTML awal, state terstruktur yang terlihat, respons jaringan terotorisasi, atau hanya tersedia lewat visualisasi.
- Apakah waktu pada data terstruktur/tooltip adalah **akhir interval**, **awal interval**, atau **waktu penerbitan**; selesaikan secara empiris dan dokumentasikan.
- Apakah seri hourly terisi konsisten dan diperbarui setiap jam.
- Apakah PM2.5 yang ditampilkan merupakan angka asli atau angka hasil koreksi oleh platform; sumber instrumentasi/correction metadata.

### 4.3 Keputusan bila hipotesis gagal

- Jika data station-level tidak dapat dibuktikan: status `BLOCKED_STATION_IDENTITY`.
- Jika PM2.5 tersedia hanya sebagai AQI: status `BLOCKED_NO_PM25_CONCENTRATION`.
- Jika hanya nilai terkini tersedia: `CURRENT_ONLY`; hourly polling tetap bisa dipertimbangkan setelah otorisasi, **tanpa klaim dapat backfill 48 jam**.
- Jika tampilan hanya grafik historis AQI: backfill PM2.5 konsentrasi **gagal**; jangan melakukan konversi AQI→PM2.5 sebagai solusi diam-diam.
- Jika akses menolak automatisasi: `BLOCKED_ACCESS`; jangan implementasikan metode penghindaran pembatasan.

---

## 5. Target Kinerja dan Perhitungan Kapasitas

- Durasi nominal: **90 × 24 = 2.160 jam per stasiun**.
- Dua stasiun: **4.320 station-hour observations** ideal tanpa gap.
- Ditambah satu stasiun kampus yang dimiliki peneliti: **6.480 station-hour observations** ideal pada dataset gabungan (penggabungan bukan scope collector ini).
- Jika hanya satu fetch per stasiun per jam: **4.320 fetches** selama 90 hari, **belum** menghitung retry, verifikasi awal, dan backfill.
- Target produksi: nominal **1 observasi per stasiun per interval satu jam**, bukan satu record setiap fetch.
- Periode mulai koleksi: tanggal/jam pertama deployment yang berhasil; gunakan **90 hari penuh dihitung dari `COLLECTION_START_UTC`**, bukan tanggal yang di-hardcode dalam source.
- Laporan akhir harus menyebut tanggal mulai-akhir riil, jumlah expected slots, observed slots, missing slots, revised slots, serta presentase completeness.

**Peringatan:** 4.320 adalah jumlah potensial, **bukan estimasi baris yang dijamin terkumpul**.

---

## 6. Strategi Akuisisi Data (Discovery-First)

Prioritas metode (hanya pada akses yang diizinkan):

1. **Data resmi/terstruktur yang terdokumentasi** untuk stasiun, apabila tersedia melalui mekanisme resmi.
2. **Pembacaan respons data yang digunakan UI** setelah memastikan semantik serta otorisasi; jangan mengarang nama/endpoint.
3. **Ekstraksi structured state/HTML** jika data PM2.5, unit, station identity, dan timestamp tersedia jelas.
4. **Browser automation Playwright sebagai fallback** untuk mengobservasi tampilan/tooltip apabila tidak ada sumber terstruktur yang cocok.
5. **Tidak menggunakan OCR/screenshot sebagai extractor utama.** Screenshot boleh untuk bukti/diagnostik ketika diperlukan.

### 6.1 Discovery workflow

1. Buka halaman target secara manual; pastikan station page dan contributor.
2. Identifikasi blok: current measurement, parameter/units, observed historical chart, forecast chart, timestamp.
3. Catat selector atau sumber data yang stabil **berdasarkan hasil pengamatan, bukan tebakan**.
4. Simpan satu fixture mentah yang boleh disimpan untuk test dan satu contoh hasil parsing yang dianonimkan bila perlu.
5. Bandingkan 3–5 sampel hasil parsing dengan angka dan timestamp yang terlihat pada UI.
6. Uji pergantian bahasa/locale dan pembaruan data; parser tidak boleh bergantung pada teks kategori AQI berbahasa Indonesia/Inggris.
7. Catat apakah parser membutuhkan JS rendering dan berapa lama response-nya.
8. Dokumentasikan bahwa histori adalah observed; beri screenshot/metadata bukti untuk pemisahan dari forecast.

### 6.2 Contract modul extractor

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

@dataclass(frozen=True)
class StationPM25Reading:
    station_id: str
    source_station_name: str
    source_contributor: str
    source_url: str
    source_label_timestamp: datetime   # timezone-aware
    interval_start_utc: datetime      # timezone-aware UTC
    interval_end_utc: datetime        # timezone-aware UTC
    pm25_ugm3: Decimal
    observed: bool                    # always True for stored observations
    extraction_method: str           # structured | html | browser
    fetched_at_utc: datetime
    quality_flags: tuple[str, ...]
    raw_snapshot_hash: str | None
```

`interval_start_utc` and `interval_end_utc` are **required** to make source time semantics explicit. Jika website tidak memberikan cukup informasi untuk menetapkannya secara defensible, record masuk quarantine, bukan langsung ke tabel final.

---

## 7. Arsitektur Sistem

```text
             Authorized IQAir Station Sources
                           |
         +-----------------+------------------+
         |                                    |
  BMKG Sleman extractor              Amaranta extractor
         |                                    |
         +-----------------+------------------+
                           v
                  Station Identity Gate
                           v
                 Timestamp + Unit Parser
                           v
              Validation / QC / Quarantine
                           v
               Idempotent DB Upsert Layer
                           v
                       PostgreSQL
                           |
                   +-------+--------+
                   |                |
              Monitoring       CSV / Parquet
                                    |
                          Thesis ML Data Pipeline
```

### 7.1 Komponen wajib

- **Station registry:** konfigurasi dan metadata stasiun.
- **Fetcher:** mengambil respons halaman/data yang terotorisasi dengan timeout dan rate control.
- **Parser:** menganalisis current readings dan optional historical readings; dapat ditest dari fixture offline.
- **Station identity guard:** memastikan nama/kontributor sumber sebelum menyimpan.
- **Normalizer:** mapping PM2.5 µg/m³, timezone, interval waktu.
- **Validator & quarantine:** menolak data tidak jelas, menyimpan alasan untuk ditinjau.
- **Storage:** immutable provenance + tabel observasi terkini dengan unique key.
- **Scheduler:** menjalankan dua stasiun satu kali setiap jam setelah data diterbitkan.
- **Backfill:** mengambil ulang jendela terakhir jika sudah diverifikasi tersedia.
- **Metrics/reporting:** freshness, completeness, failures, revisi data, dan ekspor.

### 7.2 Rekomendasi stack

| Layer | Pilihan |
|---|---|
| Runtime | Python 3.12+ |
| HTTP client | `httpx` |
| HTML parsing | `BeautifulSoup4` atau `selectolax` |
| Browser inspection/fallback | `playwright` |
| Validation | `pydantic` + `decimal` |
| Database | PostgreSQL 16+ dengan `psycopg` atau SQLAlchemy |
| Job scheduler | `cron` **atau** APScheduler (pilih satu, jangan double-run) |
| Test | `pytest`, fixture offline, mock HTTP |
| Dev/deploy | Docker + Docker Compose |
| Data export | `pandas` + `pyarrow` |

**Tidak diperlukan frontend, Redis, Kafka, Kubernetes, atau microservices** untuk dua stasiun.

---

## 8. Functional Requirements (FR)

| ID | Requirement | Priority | Definisi selesai |
|---|---|---|---|
| FR-01 | Registry dua stasiun target | MUST | Kedua target terdaftar dengan ID stabil dan expected contributor |
| FR-02 | Identity check stasiun sebelum insert | MUST | Station/city mismatch menyebabkan gagal, bukan data tertukar |
| FR-03 | Ekstraksi PM2.5 **observed** µg/m³ | MUST | PM2.5 tidak dikonversi dari AQI; parameter dan unit eksplisit |
| FR-04 | Parsing timestamp dan interval hourly | MUST | UTC dan Asia/Jakarta, tidak menggunakan fetch-time sebagai observation-time |
| FR-05 | Deduplikasi by station + pollutant + interval | MUST | Job yang diulang tidak menggandakan observasi |
| FR-06 | Audit raw data provenance | MUST | Source URL, fetched_at, extract_method, hash, run_id dapat ditelusuri |
| FR-07 | Validasi range/unit/identitas dan quarantine | MUST | Nilai tidak valid/ambigu tidak masuk final observations |
| FR-08 | CLI `discover`, `collect-once`, `export`, `report` | MUST | Perintah dapat dijalankan dengan README |
| FR-09 | Scheduler per jam | MUST AFTER POC | Trigger per jam dengan lock dan configurable lag |
| FR-10 | Extract histori 48 jam dan backfill | SHOULD IF VERIFIED | Restore gap yang benar-benar ada di source, tanpa imajinasi |
| FR-11 | Toleransi retry terbatas dan transient errors | MUST | Backoff terkontrol; tidak spin-loop |
| FR-12 | Metrics availability/completeness | MUST | Laporan per station/day dan failed runs |
| FR-13 | CSV dan Parquet export | MUST | Schema tetap dengan unit dan timestamps jelas |
| FR-14 | Mendeteksi stale measurement | MUST | Fetch sukses tetapi timestamp sama tidak dihitung sebagai data baru |
| FR-15 | Menyimpan revisi nilai periode yang sama | SHOULD | Revisions auditable; latest view konsisten |
| FR-16 | Mampu ingest ulang dari fixture (offline) | MUST | Parser diuji tanpa request ke IQAir |
| FR-17 | Konfigurasi melalui env/YAML | MUST | Tidak ada secrets maupun hardcoded tanggal di source |

---

## 9. Non-Functional Requirements (NFR)

- **Reliability:** error pada BMKG tidak menghentikan ingestion Amaranta (isolated station jobs).
- **Idempotency:** `collect-once` dua kali dengan fixture sama menghasilkan jumlah observation sama.
- **Atomicity:** batch/interval diproses menggunakan transaction; validasi sebelum upsert.
- **Timeliness:** collector default berjalan pada **HH:15 WIB** untuk memberi ruang publikasi hourly; posisi jam merupakan **asumsi awal** dan dievaluasi saat pilot.
- **Timeout:** default 15–30 detik per request; dapat dikonfigurasi.
- **Retry:** maksimal 2 retry untuk transient network errors dengan exponential backoff + jitter; hormati status rate-limit/denial dan hentikan bila perlu.
- **Concurrency:** maksimal satu job aktif per stasiun; tidak menggunakan concurrent high-rate requests.
- **Resource usage:** cukup berjalan pada satu mesin/VPS ringan.
- **Observability:** structured logs untuk run_id, station_id, status, fetch latency, count parsed, count accepted, count quarantined.
- **Recovery:** job restart tidak menimbulkan duplikat; backfill hanya jika memang terbukti bisa diakses.
- **Testability:** parser dapat menerima bytes/JSON/HTML fixture tanpa browser dan tanpa koneksi jaringan.
- **Security:** `.env` tidak masuk Git; credentials tidak muncul di log; jangan mencoba bypass access controls.

---

## 10. Aturan Timestamp (SANGAT PENTING)

**Jangan pernah gunakan jam scraping sebagai jam pengukuran.**

IQAir menjelaskan bahwa nilai station yang diberi label pukul 11:00 dapat merepresentasikan rerata pembacaan pukul **10:00–10:59**. Ini artinya informasi label perlu ditransformasikan menjadi periode pengukuran — **hanya setelah label pada source target benar-benar divalidasi**.

Contoh konseptual untuk waktu lokal **Asia/Jakarta**:

```text
Source label local:     2026-11-18 11:00:00 +07:00
Observed interval:      2026-11-18 10:00:00 .. 10:59:59.999 +07:00
Canonical start UTC:    2026-11-18 03:00:00 +00:00
Canonical end UTC:      2026-11-18 04:00:00 +00:00   (exclusive)
Fetched_at UTC:         independent, e.g. 2026-11-18 04:15:00 +00:00
```

**Required time fields:**

- `source_label_time_raw`: string timestamp asli yang terlihat.
- `source_label_timezone`: jika diketahui, `Asia/Jakarta` atau offset sumber.
- `interval_start_utc`: canonical time bucket (inclusive).
- `interval_end_utc`: end exclusive.
- `fetched_at_utc`: saat collector mengambil data.
- `source_time_semantics`: `interval_end_labeled`, `interval_start_labeled`, atau `unknown`.
- `is_forecast`: wajib `false` untuk tabel observasi.

Jika `source_time_semantics == unknown`, taruh dalam quarantine sampai diklarifikasi. Jangan mengisi timestamp secara *best guess*.

---

## 11. Data Validation & Quality Control

### 11.1 Hard validation (gagal = quarantine)

- Station identity dan contributor tidak cocok.
- Parameter bukan PM2.5 atau unit bukan konsentrasi µg/m³.
- Timestamp null, tidak timezone-aware, atau semantiknya tidak diketahui.
- `interval_end_utc - interval_start_utc != 1 hour`.
- Nilai PM2.5 null, NaN, bukan numerik, atau `< 0`.
- Label `forecast`/`predicted`/estimated city/model instead of station observation.
- Source timestamp menunjukkan data masa depan untuk observed (beri toleransi kecil untuk clock mismatch, bukan jam-jaman).
- Tidak dapat membuktikan bahwa angka berasal dari stasiun individual.

### 11.2 Soft flags (boleh disimpan, ditandai)

- `stale`: timestamp stasiun tidak berubah setelah beberapa kali fetch.
- `extreme_value`: nilai sangat tinggi (mis. > 1000 µg/m³) memerlukan review, **jangan otomatis menghapus kejadian ekstrem**.
- `large_jump`: perubahan tajam dibanding jam sebelumnya.
- `long_gap`: gap >= 3 jam.
- `high_humidity_risk`: ketika data RH ada dan metode alat sensitif kelembapan.
- `revised_value`: nilai untuk interval sama berbeda dari nilai tersimpan.
- `source_metadata_changed`: provider, station name, atau unit berubah.

### 11.3 Completeness vs collection success

Pisahkan metrik berikut:

```text
expected_slots     = jumlah interval jam di window × jumlah stasiun
observed_slots     = jumlah unique station-hour observed PM2.5 yang valid
coverage_pct       = 100 × observed_slots / expected_slots
successful_runs    = jumlah eksekusi job yang selesai tanpa collector error
job_success_pct    = 100 × successful_runs / scheduled_runs
staleness_hours    = now - last_valid_observation_interval_end
```

Coverage tidak sama dengan job success: scraper boleh berhasil membaca laman yang menampilkan **data lama**.

### 11.4 Data modeling untuk thesis

- Simpan **PM2.5 konsentrasi** sebagai target ML, bukan US AQI+.
- Simpan `measurement_source = iqair_published_station_aggregate`; bukan mengaku sebagai *raw reference instrument value*.
- Catat perbedaan platform/kalibrasi dibanding sensor kampus (sumber ketiga).
- Jangan melakukan interpolasi di layer ingestion. Jika perlu, imputasi dilakukan terpisah dalam ML preprocessing dan dicatat agar tidak terjadi data leakage.
- Historical backfill/revisions juga perlu mempertahankan **waktu data pertama kali tersedia** untuk audit serta evaluasi causal forecasting.

---

## 12. Database Schema (PostgreSQL, baseline)

Berikut rancangan baseline. Boleh diubah oleh agent asalkan memenuhi ketentuan uniqueness, provenance, revision, dan quarantine.

```sql
CREATE TABLE stations (
    station_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    expected_contributor TEXT NOT NULL,
    page_url TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    identity_status TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE ingestion_runs (
    run_id UUID PRIMARY KEY,
    station_id TEXT NOT NULL REFERENCES stations(station_id),
    started_at_utc TIMESTAMPTZ NOT NULL,
    completed_at_utc TIMESTAMPTZ,
    status TEXT NOT NULL,
    fetch_status_code INTEGER,
    parsed_count INTEGER NOT NULL DEFAULT 0,
    accepted_count INTEGER NOT NULL DEFAULT 0,
    quarantined_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_detail TEXT
);

CREATE TABLE pm25_observations (
    station_id TEXT NOT NULL REFERENCES stations(station_id),
    interval_start_utc TIMESTAMPTZ NOT NULL,
    interval_end_utc TIMESTAMPTZ NOT NULL,
    pollutant TEXT NOT NULL DEFAULT 'PM2.5',
    pm25_ugm3 NUMERIC(10,3) NOT NULL CHECK (pm25_ugm3 >= 0),
    source_label_time_raw TEXT NOT NULL,
    source_time_semantics TEXT NOT NULL,
    source_url TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    fetched_at_utc TIMESTAMPTZ NOT NULL,
    first_seen_at_utc TIMESTAMPTZ NOT NULL,
    last_seen_at_utc TIMESTAMPTZ NOT NULL,
    quality_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_snapshot_hash TEXT,
    last_run_id UUID REFERENCES ingestion_runs(run_id),
    PRIMARY KEY (station_id, pollutant, interval_start_utc),
    CHECK (interval_end_utc = interval_start_utc + INTERVAL '1 hour')
);

CREATE TABLE observation_revisions (
    revision_id BIGSERIAL PRIMARY KEY,
    station_id TEXT NOT NULL,
    interval_start_utc TIMESTAMPTZ NOT NULL,
    old_pm25_ugm3 NUMERIC(10,3),
    new_pm25_ugm3 NUMERIC(10,3) NOT NULL,
    changed_at_utc TIMESTAMPTZ NOT NULL,
    source_url TEXT NOT NULL,
    raw_snapshot_hash TEXT,
    run_id UUID REFERENCES ingestion_runs(run_id)
);

CREATE TABLE quarantined_readings (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID REFERENCES ingestion_runs(run_id),
    station_id TEXT,
    received_at_utc TIMESTAMPTZ NOT NULL,
    reason_code TEXT NOT NULL,
    source_url TEXT,
    raw_excerpt TEXT,
    raw_snapshot_hash TEXT
);

CREATE INDEX idx_pm25_interval ON pm25_observations (interval_start_utc);
CREATE INDEX idx_pm25_fetched ON pm25_observations (fetched_at_utc);
```

**Revision policy:** Jika pasangan `station_id + interval_start_utc` sudah ada dan nilainya sama, perbarui `last_seen_at_utc`; jika berubah, catat pada `observation_revisions` dahulu, lalu upsert nilai latest dalam transaksi yang sama. Jangan menghapus nilai lama tanpa jejak. `raw_snapshot_hash` adalah SHA-256 dari sumber payload/fragmen yang disimpan dengan aman.

---

## 13. Collection Scheduler, Retry, Backfill

### 13.1 Default polling (sesudah PoC)

- Cron pada **setiap jam menit 15 WIB**; contoh `15 * * * *` dengan timezone `Asia/Jakarta`.
- Dua station jobs sequential atau concurrency rendah; hindari overlap run.
- Default retry max 2 untuk gangguan sementara, dengan jeda dan batas waktu.
- Error pada satu stasiun tidak menghentikan stasiun lainnya.
- Tandai fetch berhasil tetapi data usang sebagai stale, bukan `new observation`.
- Perubahan tanggal akibat zona waktu ditangani dengan conversion timezone-aware.

### 13.2 Backfill plan (conditional)

IQAir menginformasikan jendela histori **48 jam hourly**. Jika dan hanya jika PoC membuktikan histori itu dapat diekstrak sebagai **PM2.5 station-level observed**:

- Pada setiap run, ambil titik dalam 48 jam terakhir yang benar-benar tersedia di sumber, lalu upsert.
- Ini menutup gap akibat restart collector dalam window pendek.
- Jika sumber tidak punya titik untuk jam tertentu, pertahankan sebagai missing.
- **Jangan mengarang data di luar window 48 jam**, dan jangan menganggap 48 jam selalu lengkap.
- Hindari pengambilan berlebihan; jika data historis membutuhkan request tambahan, jadwalkan backfill berkala sesuai kebutuhan akses.

### 13.3 No backfill fallback

Jika histori tidak tersedia sebagai concentration observed, implementasikan **poll-current-only** sesuai sumber terverifikasi. Catat bahwa recovery hanya mungkin untuk data yang tetap tersedia di halaman; tidak ada jaminan pemulihan outage. Status ini harus muncul jelas pada report.

---

## 14. Dataset Output & Contracts

### 14.1 Canonical CSV/Parquet columns

```text
station_id
station_display_name
latitude
longitude
interval_start_utc
interval_end_utc
interval_start_local
pm25_ugm3
pollutant
unit
source_provider
source_url
source_contributor
source_time_semantics
first_seen_at_utc
fetched_at_utc
quality_flags
```

**Catatan:** `latitude`/`longitude` boleh null sebelum koordinat sensor terverifikasi; jangan mengisi dari perkiraan hotel/kantor. Rekaman dengan koordinat null belum siap untuk pembangunan graph spasial.

### 14.2 Output tambahan

- `reports/daily_coverage.csv`: daily expected vs observed per station.
- `reports/station_status.json`: latest timestamp, staleness, error count.
- `reports/discovery_report.md`: bukti akses stasiun dan hasil keputusan go/no-go.
- `samples/`: fixture data yang aman dan dapat dipakai untuk unit tests.
- `exports/yogyakarta_iqair_pm25_YYYYMMDD_YYYYMMDD.parquet`.
- `exports/README_dataset.md`: deskripsi unit, sumber, periode, kriteria QA, missing-data policy, batasan penggunaan akademik.

### 14.3 Contoh record (SINTETIS; BUKAN DATA IQAIR)

```json
{
  "station_id": "bmkg_sleman",
  "interval_start_utc": "2026-11-18T03:00:00+00:00",
  "interval_end_utc": "2026-11-18T04:00:00+00:00",
  "pm25_ugm3": 26.6,
  "pollutant": "PM2.5",
  "unit": "ug/m3",
  "source_provider": "iqair",
  "source_time_semantics": "interval_end_labeled",
  "is_forecast": false,
  "quality_flags": []
}
```

---

## 15. Repository Structure & CLI

Rekomendasi struktur:

```text
iqair-yogyakarta-collector/
├── README.md
├── pyproject.toml
├── .env.example
├── compose.yaml
├── Dockerfile
├── config/
│   └── stations.yaml
├── migrations/
├── src/iqair_collector/
│   ├── __init__.py
│   ├── cli.py
│   ├── settings.py
│   ├── registry.py
│   ├── fetcher.py
│   ├── extractors/
│   │   ├── base.py
│   │   ├── structured.py
│   │   ├── html.py
│   │   └── browser.py
│   ├── normalization.py
│   ├── quality.py
│   ├── persistence.py
│   ├── scheduler.py
│   ├── backfill.py
│   ├── reporting.py
│   └── export.py
├── tests/
│   ├── fixtures/
│   ├── test_station_identity.py
│   ├── test_timestamp_semantics.py
│   ├── test_pm25_parser.py
│   ├── test_forecast_exclusion.py
│   ├── test_idempotency.py
│   └── test_quality_checks.py
├── reports/
├── samples/
└── exports/
```

Expected CLI (agent boleh memakai `python -m iqair_collector` atau executable `iqair-collector`, asalkan didokumentasikan):

```bash
# Analyze sources without enabling ongoing scheduled collection
iqair-collector discover --station bmkg_sleman
iqair-collector discover --station amaranta_prambanan

# Parse offline fixtures (must work without network)
iqair-collector parse-fixture --station bmkg_sleman --input tests/fixtures/bmkg.html

# Authorized one-shot collection, after identity check
iqair-collector collect-once --station bmkg_sleman
iqair-collector collect-once --all

# Export and report
iqair-collector report --period last-7-days
iqair-collector export --format parquet --from 2026-11-18 --to 2026-11-25
```

Example `.env.example`:

```dotenv
DATABASE_URL=postgresql://collector:change_me@localhost:5432/air_quality
LOCAL_TIMEZONE=Asia/Jakarta
POLL_MINUTE_LOCAL=15
HTTP_TIMEOUT_SECONDS=20
MAX_RETRIES=2
REQUESTS_CONCURRENCY=1
HISTORICAL_BACKFILL_ENABLED=false
SCHEDULED_COLLECTION_ENABLED=false
COLLECTION_START_UTC=
COLLECTION_DURATION_DAYS=90
LOG_LEVEL=INFO
```

`SCHEDULED_COLLECTION_ENABLED=false` by default prevents an unreviewed PoC from accidentally becoming a 90-day crawler.

---

## 16. Phases, Deliverables & Go/No-Go Gates

### Phase 0 — Station verification & discovery (WAJIB)

**Deliverable:** `reports/discovery_report.md`.

Per stasiun, laporkan:

- canonical station page URL and stable station identifier (if available);
- station name, expected contributor, whether page is station/city/forecast;
- parameter, units, live timestamp, historical chart availability;
- data representation (`HTML` / `embedded structured` / `documented API` / `browser interaction`);
- real example of PM2.5 reading + matching UI evidence (not invented);
- source time semantics with examples;
- status: `GO_STATION_PM25_HOURLY`, `GO_CURRENT_ONLY`, or `BLOCKED_*`;
- technical and authorization blockers.

**Gate A:** Tidak boleh lanjut otomatis 90 hari sebelum kedua stasiun bisa diidentifikasi secara unik dan nilai observed PM2.5 station-level dapat dibuktikan.

### Phase 1 — PoC offline parser

**Deliverables:** parser, fixture, unit tests, documented extraction strategy.

- Parse beberapa fixture dua stasiun.
- Validasi name/contributor/unit/time.
- Tes kasus AQI-only, forecast, stale, malformed, changed locale, missing values.

**Gate B:** Semua fixture positif benar; semua fixture negatif gagal aman; no invented values.

### Phase 2 — End-to-end pilot 48 jam

**Deliverables:** PostgreSQL schema, `collect-once`, scheduler pilot, reporting.

- Jalan setiap jam untuk dua stasiun yang lolos Gate A.
- Buat laporan observed station-hour, missing, stale, retries, duplicate, revision.
- Amati waktu update sebenarnya; sesuaikan minute offset.
- Evaluasi apakah historis 48 jam bisa backfill dengan benar.

**Gate C:**

- Identity misclassification = **0**.
- Forecast masuk tabel observed = **0**.
- Invalid unit/timestamp yang lolos = **0**.
- Duplikasi canonical key = **0**.
- Parser vs UI mismatch pada sampel manual = **0**.
- Scheduled job success rate target **>=95%**, dievaluasi terpisah dari sensor availability.

Jika source sering tidak memperbarui nilai, tandai **DATA_SOURCE_INSUFFICIENT**, walau collector berjalan sempurna.

### Phase 3 — Pilot 7 hari & production preparation

- Target awal completeness **>=85%** valid hourly slots per stasiun (target internal, bukan jaminan; kualitas lingkungan sumber bisa memengaruhi).
- Ketersediaan observed 85% tidak membuktikan kualitas sensor; lakukan QC lanjut.
- Test restart, no network, non-200, changed DOM, database unavailable.
- Laporan go/no-go dengan evaluasi risk dan rekomendasi deployment.

### Phase 4 — Authorized production 90 hari

- Hanya aktifkan jika PoC, access approval, dan quality gate terpenuhi.
- Hasil akhir: data CSV/Parquet, QA report, source provenance, environment reproduksi, dan dokumentasi batasan.

---

## 17. Test Plan Minimum (MUST)

1. **Station identity:** halaman kota Yogyakarta ditolak jika target Amaranta membutuhkan pembuktian stasiun individual.
2. **Parameter:** US AQI 85 tidak boleh disimpan sebagai 85 µg/m³.
3. **Unit:** `26.6 µg/m³` diterima; `26.6 AQI` ditolak.
4. **Historical vs forecast:** list forecast dengan 24 jam data tidak masuk observations.
5. **Timestamp:** label akhir interval 11:00 WIB (jika verified) menghasilkan start 10:00 WIB = 03:00 UTC.
6. **Timezone aware:** timestamps naïve ditolak sampai zona waktu terbukti.
7. **Negative/non-numeric:** `-5`, `NaN`, `--` di-quarantine.
8. **Idempotent ingest:** dua runs dengan timestamp/value sama tetap satu canonical observation.
9. **Source revision:** value berubah di interval sama menghasilkan history revision.
10. **Station outage:** nilai lama terdeteksi stale, bukan observasi baru.
11. **Partial failure:** BMKG gagal, Amaranta tetap bisa dikumpulkan.
12. **HTML changes:** selector missing menghasilkan diagnostic error, bukan angka default.
13. **Backfill:** missing hour hanya dipulihkan bila interval tersebut benar-benar muncul di source.
14. **Export:** row count dan values sesuai DB, sorted timestamp, timezone consistent.
15. **Rate limit or denial:** job berhenti/retry conservatively, tidak bypass.

---

## 18. Risks & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Amaranta hanya teridentifikasi lewat city page | Bisa salah sumber | Verifikasi station URL/ID; fail closed |
| Chart 48h menampilkan AQI, bukan PM2.5 µg/m³ | Backfill concentration gagal | PoC historical extraction; fallback current-only |
| Chart forecast terbaca sebagai historical | Scientific invalidity | Separate observed and forecast; negative tests |
| Update stasiun terlambat | Stale/duplicate | Parse source timestamp, freshness report |
| Struktur halaman berubah | Parser failure | Layered extractor, fixture, alert, no silent fallback |
| BMKG & Amaranta punya metode sensor berbeda | Inconsistent data quality | Simpan contributor, metadata, flags, evaluasi sensor |
| 90 hari tidak mewakili musim lain | Terbatas untuk generalisasi | Dataset pendamping, tidak klaim generalisasi tahunan |
| Koordinat stasiun tidak diketahui | Tidak siap buat graph | Require geolocation verification before graph construction |
| Website membatasi automated access | Collection blocked | Stop, dokumentasikan, gunakan izin/API/alternatif resmi |
| Server mati >48h | Permanent gaps (jika histori pendek) | Monitoring, backup/restart, best-effort backfill |

---

## 19. Definition of Done (DoD)

**MVP DoD** terpenuhi ketika:

- [ ] Dua identitas stasiun diverifikasi; URL/ID Amaranta individual terbukti atau berstatus blocker eksplisit.
- [ ] Ekstraksi PM2.5 observed µg/m³ terbukti pada kedua stasiun, atau blockage didokumentasikan dengan bukti.
- [ ] Parser dan test offline lulus.
- [ ] Current vs historical vs forecast dipisahkan.
- [ ] PostgreSQL migrations, idempotent ingestion, revisions, quarantine bekerja.
- [ ] Job terjadwal dan stop/start tanpa duplicate bekerja pada pilot.
- [ ] Time semantics terverifikasi.
- [ ] Laporan coverage, staleness, errors, dan export bisa direproduksi.
- [ ] README jelas: `setup`, `discover`, `collect-once`, `tests`, `pilot`, `report`, `export`.
- [ ] Tidak ada klaim pencapaian 90 hari sebelum koleksi benar-benar selesai.

---

## 20. Instruksi Operasional untuk AI Agent

1. **Mulai dari Phase 0; jangan langsung coding scheduler.**
2. Buat `discovery_report.md` dan tabel *verified vs unverified* berdasarkan observasi nyata.
3. Temukan URL stasiun **Amaranta Prambanan**; jangan menganggap halaman kota sebagai station-level.
4. Identifikasi dengan bukti apakah histori hourly menyediakan PM2.5 concentration pada kedua stasiun.
5. Pilih extraction method yang paling sederhana, transparan, reproducible; Playwright hanya jika benar-benar perlu.
6. Jangan mengarang private endpoint, schema source, HTML selector, data contoh riil, atau geocoordinates.
7. Bila ada blocker, jelaskan blocker dan pilihan teknis. Jangan memalsukan keberhasilan.
8. Bila berhasil, bangun dari parser offline → DB → one-shot → pilot → scheduled collector.
9. Hindari overengineering; dua stasiun saja, tanpa frontend.
10. Di akhir setiap fase, kirim: **apa yang sudah diverifikasi**, **apa yang masih asumsi**, **file yang diubah**, **tes yang dijalankan**, dan **next action**.

---

## 21. Pertanyaan Terbuka / Asumsi Default

Pertanyaan berikut **tidak memblokir penyusunan dokumen atau Phase 0**. Gunakan asumsi default sampai pemilik proyek menjawab.

| Pertanyaan | Default untuk PoC |
|---|---|
| Di mana aplikasi akan dijalankan? | Docker Compose pada komputer lokal; deploy ke VPS setelah pilot |
| Database sudah tersedia? | PostgreSQL lokal via Docker Compose |
| Mulai kapan 90 hari berjalan? | Dari timestamp *production start* yang dicatat aplikasi; bukan saat dokumen dibuat |
| Apakah perlu PM10, RH, temperatur, cuaca? | Tidak wajib untuk MVP; prioritaskan PM2.5 dulu |
| Format ekspor akhir? | CSV + Parquet |
| Sudah ada akses resmi/izin? | Belum dikonfirmasi; Phase 0 discovery dulu, tidak aktifkan produksi |
| Apakah ada data third station kampus? | Di luar repo awal; nantinya gunakan import adapter terpisah |

---

## 22. Sumber Referensi Resmi

Sumber di bawah telah ditinjau pada 18 November 2026; halaman live dapat berubah.

1. IQAir — **SLEMAN station**: https://www.iqair.com/id/air-quality/indonesia/yogyakarta/sleman/sleman
2. IQAir — **Yogyakarta city page**, mencantumkan kontribusi Amaranta: https://www.iqair.com/id/air-quality/indonesia/yogyakarta/yogyakarta
3. IQAir — **Yogyakarta station map**, mencantumkan nama Amaranta Prambanan: https://www.iqair.com/id/air-quality-map/indonesia/yogyakarta/yogyakarta
4. IQAir Knowledge Base — **How to access historical data**: https://www.iqair.com/id/support/knowledge-base/how-can-i-access-historical-data-on-the-iqair-platform
5. IQAir — **Air Quality Data Computation**, timestamp and hourly aggregation: https://www.iqair.com/support-articles/air-quality/data-computation
6. IQAir — **Platform/API product overview**: https://www.iqair.com/id/air-quality-monitors/api
7. IQAir — **Terms of Use**, updated 3 June 2026: https://www.iqair.com/id/legal/terms-conditions

---

### Final acceptance summary for the coding agent

**Implement a reproducible, station-verified, PM2.5-concentration-only, hourly data collector for BMKG Sleman and Amaranta Prambanan, with strict identity and timestamp validation, deduplicated PostgreSQL storage, quality monitoring, and export. Treat 48-hour history and Amaranta station URL as unverified until discovery proves them. The system must fail safely rather than fabricate data or silently substitute city AQI/forecast.**
