#!/bin/sh
set -eu
# Create consistent gzipped SQLite backups using Python sqlite3.backup() and upload to Drive.
APP_DIR="/home/iqair/iqair-collector"
BACKUP_DIR="${APP_DIR}/data/sqlite_backup"
REMOTE="iqairdrive:IQAir-Yogyakarta/99_sqlite_backup"

"${APP_DIR}/.venv/bin/python" -m iqair_collector backup-sqlite --output-dir "${BACKUP_DIR}"

if [ -d "${BACKUP_DIR}" ]; then
  /usr/bin/rclone copy "${BACKUP_DIR}" "${REMOTE}" \
    --include '*.sqlite3.gz' \
    --transfers 1 --checkers 1 --retries 2 --low-level-retries 2 \
    --contimeout 15s --timeout 120s --stats 0 --log-level NOTICE
fi
