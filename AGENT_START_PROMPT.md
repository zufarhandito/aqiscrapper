# Prompt untuk AI Coding Agent — IQAir Yogyakarta Collector

Anda adalah **Senior Python Data Engineer + Research Software Engineer**. Tugas Anda: implementasikan spesifikasi dalam file `IQAIR_YOGYAKARTA_SCRAPER_SRD.md` untuk dataset pendamping thesis **Spatio-Temporal Air Quality Prediction and Health-Aware Recommendation using Graph Learning**.

## Scope

- Target station #1: **SLEMAN (BMKG)** — https://www.iqair.com/id/air-quality/indonesia/yogyakarta/sleman/sleman
- Target station #2: **Amaranta Prambanan (Hotel Amaranta Prambanan)** — station page URL **belum terverifikasi**, referensi city page https://www.iqair.com/id/air-quality/indonesia/yogyakarta/yogyakarta
- Target record: **observed PM2.5 concentration in µg/m³**, hourly.
- Durasi target sesudah pilot: **90 hari**.
- Dataset Beijing Multi-Site tetap utama; Yogyakarta ini dataset pendamping.

## Aturan pengerjaan

1. **Baca SRD penuh terlebih dahulu.** Jadikan SRD sebagai sumber kebenaran implementasi.
2. **Kerjakan Phase 0 dulu**: audit dua halaman, verifikasi station identity, observed vs forecast, serta kemampuan mengambil PM2.5 µg/m³ hourly dan histori 48 jam. Tulis hasilnya di `reports/discovery_report.md`.
3. Jangan menganggap PM2.5 pada **halaman kota** pasti sama dengan pembacaan **stasiun Amaranta**. Cari sumber/identifier stasiun individual. Bila tidak bisa diverifikasi, laporkan blocker.
4. Jangan mengarang endpoint, HTML selector, sample data riil, koordinat, timestamp, atau hasil pengujian. Jika akses live tidak tersedia, bangun parser testable dari fixture yang benar-benar tersedia dan laporkan gap.
5. Jangan mengubah AQI menjadi µg/m³ atau memasukkan forecast sebagai observed.
6. Parser **fail-closed** bila sumber, unit, atau timestamp tidak dapat diverifikasi.
7. Jangan mengimplementasikan metode menghindari access controls; produksi dijalankan hanya bila akses telah diotorisasi.
8. Setelah discovery berhasil, implementasikan bertahap: offline fixture tests → data model → `collect-once` → 48h pilot → 7-day pilot → production-ready scheduler.
9. Gunakan Python 3.12+, PostgreSQL, Docker Compose, pytest; jangan membuat frontend.
10. Sampaikan hasil tiap fase berupa: evidence, verified assumptions, blockers, files changed, tests executed, dan recommended next step.

## Output pertama yang harus Anda hasilkan

1. `reports/discovery_report.md` (per-station evidence + verdict: `GO_STATION_PM25_HOURLY`, `GO_CURRENT_ONLY`, or `BLOCKED_*`).
2. Project skeleton serta parser interface yang testable secara offline.
3. Daftar risiko yang masih terbuka dan kesimpulan apakah implementasi Phase 1 bisa dimulai.

**Jangan klaim scraper sudah bekerja hanya karena halaman IQAir menampilkan PM2.5. Buktikan ekstraksi yang benar secara empiris.**
