# IQAir collector ? penyimpanan lokal

PM2.5 observed hourly untuk SLEMAN BMKG, Amaranta Prambanan, dan DTETI UGM
(nama sumber: Smart Censor DTETI Lt. 4; kontributor Sensor IQAir DTETI). Python dan
Playwright berjalan langsung; **tidak memerlukan PostgreSQL atau Docker**.
Perubahan ini mengikuti arahan pengguna untuk menyimpan file lokal dan memindahkan
hasilnya secara manual, menggantikan pilihan storage PostgreSQL dalam SRD awal.

## File hasil

```text
data/
  bmkg_sleman.csv
  amaranta_prambanan.csv
  dteti_ugm.csv
  state.sqlite3
```

CSV otomatis dibuat/diperbarui setelah pengambilan berhasil, satu file per stasiun.
`collect-once --all` dan `schedule --all` mencakup ketiga stasiun. Pemilihan khusus
DTETI menggunakan `--station dteti_ugm`. Bukti: `reports/dteti_discovery.md`.
Bisa dibuka di Excel atau disalin manual. Timestamp mencakup UTC dan awal interval
WIB, nilai PM2.5, unit, identitas, provenance dan quality flags. File hanya muncul
jika stasiun itu sudah memiliki observasi.

`state.sqlite3` adalah file pencatatan lokal dari library bawaan Python, **bukan
server database**. Ia mempertahankan deduplikasi, nilai lama saat revisi, payload
publik beserta hash, dan kegagalan/quarantine. Jangan menghapusnya jika koleksi
akan dilanjutkan. File SQLite tidak perlu dikirim untuk sekadar melihat CSV.

CSV ditulis melalui temporary file dan atomic rename. SQLite adalah sumber utama;
kalau proses mati setelah commit tetapi sebelum CSV diperbarui, `report` membuat
ulang CSV. Jika Excel mengunci file di Windows, tutup file itu lalu jalankan
`report` untuk memulihkannya. Jangan mengedit CSV sumber secara manual karena
akan ditulis ulang; edit salinannya. Untuk backup seluruh folder termasuk SQLite,
hentikan collector dulu dan salin seluruh folder `data` (termasuk sidecar jika ada).

## Setup Windows

```powershell
cd D:\projects\iqairsrapper
python -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[dev]'
.\.venv\Scripts\python -m playwright install chromium
# Hanya jika .env belum ada:
Copy-Item .env.example .env
```

Pada instalasi yang sudah ada, jangan timpa `.env`. Tambahkan `DATA_DIR=data`.
Variabel lama `DATABASE_URL` dan `POSTGRES_PASSWORD` tidak dipakai collector lokal.
`init-db` masih tersedia sebagai alias kompatibilitas untuk membuat storage lokal,
tetapi tidak diperlukan: folder dan file pencatatan dibuat otomatis.

## Pemakaian

Pengaturan akses live yang sudah ada tetap berlaku. Default
`IQAIR_AUTOMATION_AUTHORIZED=false` dan `SCHEDULED_COLLECTION_ENABLED=false`;
flag pertama membuka pengaman lokal, bukan memberi izin dari penyedia data.
Tidak ada CAPTCHA bypass, stealth, transfer cookie atau rotasi proxy.

Setelah pengaturan akses sesuai:

```powershell
.\.venv\Scripts\python -m iqair_collector collect-once --all
.\.venv\Scripts\python -m iqair_collector report
```

Tidak perlu `--headed` untuk operasi biasa. Browser dibuka hanya saat mengambil
data, lalu ditutup. Tiga stasiun dibaca bergantian. Seluruh writer lokal dikunci
agar job tidak tumpang tindih. 401/403/429 menghentikan batch dan scheduler.

Untuk per jam, isi `COLLECTION_START_UTC` dengan waktu mulai riil ISO 8601 UTC,
pertahankan nilainya saat restart, dan aktifkan `SCHEDULED_COLLECTION_ENABLED`.

```powershell
.\.venv\Scripts\python -m iqair_collector schedule --all
```

Default menit 15 setiap jam, maksimal 90 hari sejak timestamp mulai. Terminal
harus tetap berjalan; Ctrl+C berhenti. Kegagalan storage dilaporkan dan dijadwalkan
ulang pada jam berikut. Tidak ada backfill/histori 48 jam atau service startup
otomatis. CSV menyimpan hasil yang sudah berhasil diambil, bukan data saat Wi-Fi
putus. Parquet dan laporan coverage per periode belum tersedia.

Ekspor gabungan opsional:

```powershell
.\.venv\Scripts\python -m iqair_collector export --output exports/semua_stasiun.csv
```

## Memindahkan data lama dari PostgreSQL

Instalasi lama mungkin masih memiliki data di volume Docker. Jangan hapus volume
sebelum migrasi/backup. Helper berikut membaca database lama tanpa mengubahnya dan
menyalin observasi, first/last-seen, revisi, payload, runs dan quarantine. Interval
lokal yang sudah ada tidak ditimpa. Helper memerlukan driver psycopg dari instalasi
lama dan `DATABASE_URL` lama dalam `.env`; **tidak diperlukan di Pi atau koleksi baru**.

```powershell
.\.venv\Scripts\python tools/migrate_postgres.py
```

Setelah hasil dicek, layanan PostgreSQL lama bisa dihentikan. Dockerfile dan
Compose sudah dihapus dari proyek. Aplikasi Docker Desktop dan volume lama tidak
di-uninstall/dihapus otomatis.

## Raspberry Pi 3

Tanpa service PostgreSQL dan Docker, beban lebih ringan. Chromium tetap komponen
terberat; kelayakan Pi 3 belum diuji atau diukur. Perlu OS ARM64 yang didukung
Playwright dan Python 3.12+. Jangan menyalin `.venv` Windows ke Pi; buat ulang
venv/dependensi di sana. Periksa RAM/OS/arsitektur sebelum menentukan instalasi.
Gunakan headless, stasiun berurutan, dan pantau penggunaan memori saat pilot.

Deployment Pi yang sudah diperiksa: `/home/pi/iqair-collector`, Debian 13 ARM64,
Python 3.13.5, RAM 905 MiB. Playwright dan collector sudah terpasang di `.venv`.
`.env` Pi memakai `BROWSER_EXECUTABLE_PATH=/usr/bin/chromium` untuk browser sistem.
Biarkan kosong pada mesin yang memakai Chromium bawaan Playwright. Versi browser
sistem bisa berbeda dari versi yang dibundel Playwright; kompatibilitas live tetap
perlu diuji. Uji headless halaman offline dan parser berhasil; belum pilot live.

## Service 90 hari di Pi (aktif)

`iqair-pilot.service` menjalankan koleksi ketiga stasiun setiap menit 15, tanpa
bergantung pada sesi SSH. Atas arahan pengguna, window sudah diperpanjang dari
pilot 24 jam menjadi **90 hari**: 19 November 2026 14:42 WIB sampai
17 Februari 2027 14:42 WIB. Waktu mulai tetap saat restart; data lama dipertahankan.
Nama service tetap untuk kompatibilitas. Service selesai setelah jadwal terakhir
dalam window. Run terjadwal pertama pada 19 November 15:15 WIB berhasil untuk
kedua stasiun; ini belum membuktikan kelengkapan 90 hari.

```bash
systemctl status iqair-pilot.service --no-pager
journalctl -u iqair-pilot.service -n 20 --no-pager
# Menghentikan koleksi sekarang:
sudo systemctl stop iqair-pilot.service
# Membatalkan juga aktivasi saat boot:
sudo systemctl disable iqair-pilot.service
```

Jangan jalankan `schedule --all` manual bersamaan dengan service. Pantau jumlah
slot, stale, revisi dan failures sepanjang koleksi. Source denial menghentikan
service; tidak ada auto-restart untuk mencoba
akses berulang. Template unit disimpan di `deploy/iqair-pilot.service.template`.

## Sinkronisasi Google Drive di Pi

Drive sudah terhubung melalui rclone dengan scope `drive.file`; kredensial berada
di `/home/pi/.config/rclone/rclone.conf`, permission 0600, bukan di repo. Folder:
[IQAir-Yogyakarta](https://drive.google.com/drive/folders/1z5V-2wfz-k7F71XPQ_lvuKX8sMDXnfEU).
File tetap berformat CSV. Buka Drive dengan akun yang dipakai saat otorisasi.

`iqair-drive-sync.timer` aktif setiap menit 05/20/35/50, terpisah dari collector.
Menggunakan copy sehingga file tujuan tidak dihapus ketika sumber hilang.
Database/config/secret tidak diunggah. CSV DTETI juga disertakan setelah penambahan
stasiun; hanya tiga nama CSV stasiun yang diizinkan. Saat jaringan gagal, data lokal tetap ada
dan timer berikutnya mencoba lagi. Dua file unggahan awal diverifikasi identik
dengan lokal melalui checksum. Hasil berikutnya perlu diperiksa dari journal.

```bash
systemctl list-timers iqair-drive-sync.timer --no-pager
journalctl -u iqair-drive-sync.service -n 20 --no-pager
# Sinkron sekali sekarang:
sudo systemctl start iqair-drive-sync.service
# Hentikan sinkronisasi berkala:
sudo systemctl disable --now iqair-drive-sync.timer
```

Collector berakhir sesuai window 90 hari; timer Drive terpisah dan tidak
memperpanjang koleksi IQAir. Jika OAuth masih Testing, refresh token untuk
Drive biasanya kedaluwarsa setelah tujuh hari. Atur publishing state sebelum
koleksi jangka panjang; jangan menyalin token/kredensial ke chat atau repo.
Helper setup laptop `tools/connect_drive.py` memerlukan paramiko dan JSON Desktop
client milik pengguna; tidak diperlukan untuk operasi rutin di Pi.

## Kolom tambahan CSV (22 November 2026)

CSV mencakup `ditangkap_pada_wib`, misalnya `Senin, 23 November 2026 (15:15) WIB`.
Ini waktu pengambilan terakhir untuk baris tersebut, bukan waktu pengukuran.
`first_seen_local` menyimpan waktu pertama baris dijumpai; `source_label_local`
adalah label waktu data IQAir. Semua kolom lokal menggunakan WIB (UTC+7).

Kolom tambahan: AQI/deskripsi, polutan utama/konsentrasi, estimated, suhu,
kelembapan, tekanan, kecepatan/arah angin, kondisi/ikon cuaca, rasio/warna paparan
WHO dari sumber, ID/timezone/koordinat stasiun, serta konsentrasi/unit/AQI PM10,
NO2, SO2, CO, O3 jika tersedia. Nilai yang tidak tersedia dikosongkan, bukan nol.
Angka cuaca menggunakan akhiran `_source`: nilai asli halaman tanpa asumsi unit
atau klaim bahwa cuaca diukur oleh sensor stasiun itu sendiri. Rasio WHO disalin
sebagai indikator sumber, tidak dihitung ulang.

`pollutants_json`, `contributors_json`, `current_json`, dan `source_details_json`
mempertahankan seluruh data pada bagian publik yang dipilih, termasuk atribut
yang belum memiliki kolom tersendiri. Angka desimal dapat disimpan sebagai string
di JSON untuk mempertahankan presisi. Data akun/cookie tidak diambil. Forecast
dan riwayat belum dikoleksi oleh pengambilan current ini.

Tidak diperlukan migrasi skema SQLite. Export/report memulihkan kolom tambahan
baris lama dari snapshot persis yang terkait dengan run-nya jika masih tersedia;
jika tidak ada snapshot, kolom tambahan tetap kosong dan PM2.5 lama tetap ada.
Dedup tetap satu baris per stasiun/jam sumber; penanda outcome `revised` tetap
merujuk perubahan PM2.5. Setiap snapshot tersimpan untuk menelusuri atribut lain.
Sinkron Drive tetap mengunggah tiga CSV yang sama dengan kolom baru.

Status deployment perubahan ini dicatat di `reports/extended_csv_update.md`.

## Tes lokal

```powershell
.\.venv\Scripts\python -m pytest -q
```

Semua tes berjalan lokal tanpa PostgreSQL, Docker, atau request ke IQAir. Tes
browser mengintersep request dengan HTML sintetis yang berisi data capture asli;
itu bukan pengujian kompatibilitas HTML IQAir terbaru. Bukti live tambahan:
pengguna melaporkan pengambilan Amaranta berhasil pada 19 November 2026.
