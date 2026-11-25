#!/bin/sh
set -eu
# Copy only registered station CSVs. No local database, configuration or secrets.
exec /usr/bin/rclone copy /home/pi/iqair-collector/data iqairdrive:IQAir-Yogyakarta \
  --filter '+ /bmkg_sleman.csv' --filter '+ /amaranta_prambanan.csv' \
  --filter '+ /dteti_ugm.csv' --filter '- **' \
  --transfers 1 --checkers 1 --retries 2 --low-level-retries 2 \
  --contimeout 15s --timeout 60s --stats 0 --log-level NOTICE
