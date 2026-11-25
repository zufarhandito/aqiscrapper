#!/bin/sh
set -eu
# Sync organized dataset folders to Google Drive:
#   01_pm25_observed/   -> VPS observed PM2.5 CSVs (*_new.csv)
#   02_weather_forecast/ -> Partitioned Open-Meteo (daily) & BMKG (monthly) CSVs
#   03_metadata/        -> Station metadata & data dictionary
# Existing 00_archive_pi/ files are never touched.
DATA_DIR="/home/iqair/iqair-collector/data"
CFG_DIR="/home/iqair/iqair-collector/config"
REMOTE="iqairdrive:IQAir-Yogyakarta"

for station in bmkg_sleman amaranta_prambanan dteti_ugm; do
  src="${DATA_DIR}/${station}.csv"
  if [ -f "$src" ]; then
    /usr/bin/rclone copyto "$src" "${REMOTE}/01_pm25_observed/${station}_new.csv" \
      --retries 2 --low-level-retries 2 \
      --contimeout 15s --timeout 60s --stats 0 --log-level NOTICE
  fi
done

if [ -d "${DATA_DIR}/weather_forecast" ]; then
  /usr/bin/rclone copy "${DATA_DIR}/weather_forecast" "${REMOTE}/02_weather_forecast" \
    --include '*.csv' \
    --transfers 2 --checkers 2 --retries 2 --low-level-retries 2 \
    --contimeout 15s --timeout 60s --stats 0 --log-level NOTICE
fi

if [ -f "${CFG_DIR}/weather_stations.json" ]; then
  /usr/bin/rclone copyto "${CFG_DIR}/weather_stations.json" "${REMOTE}/03_metadata/stations_metadata.json" \
    --retries 2 --low-level-retries 2 \
    --contimeout 15s --timeout 60s --stats 0 --log-level NOTICE
fi

if [ -f "${CFG_DIR}/data_dictionary.md" ]; then
  /usr/bin/rclone copyto "${CFG_DIR}/data_dictionary.md" "${REMOTE}/03_metadata/data_dictionary.md" \
    --retries 2 --low-level-retries 2 \
    --contimeout 15s --timeout 60s --stats 0 --log-level NOTICE
fi
