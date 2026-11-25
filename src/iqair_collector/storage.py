"""Local SQLite bookkeeping + per-station CSV; no server required."""
from contextlib import contextmanager, closing
from dataclasses import asdict
from datetime import datetime, UTC
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY, station_id TEXT NOT NULL, started_at TEXT NOT NULL,
 completed_at TEXT, status TEXT NOT NULL, error_code TEXT, outcome TEXT, snapshot_hash TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (hash TEXT PRIMARY KEY, payload BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS observations (
 station_id TEXT NOT NULL, interval_start_utc TEXT NOT NULL, interval_end_utc TEXT NOT NULL,
 pm25_ugm3 TEXT NOT NULL, reading TEXT NOT NULL, first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL, run_id TEXT NOT NULL,
 PRIMARY KEY(station_id,interval_start_utc)
);
CREATE TABLE IF NOT EXISTS revisions (
 id INTEGER PRIMARY KEY, station_id TEXT NOT NULL, interval_start_utc TEXT NOT NULL,
 old_reading TEXT NOT NULL, new_reading TEXT NOT NULL, run_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantine (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, reason_code TEXT NOT NULL, snapshot_hash TEXT
);
"""


def connect(data_dir):
    return sqlite3.connect(Path(data_dir) / 'state.sqlite3', isolation_level=None, timeout=10)


def init_store(data_dir):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    with closing(connect(data_dir)) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript(SCHEMA)


@contextmanager
def station_lock(conn, station_id):
    # One writer across all stations: also prevents overlapping browser jobs.
    conn.execute('PRAGMA busy_timeout=0')
    try:
        conn.execute('BEGIN IMMEDIATE')
    except sqlite3.OperationalError as exc:
        if 'locked' not in str(exc).lower() and 'busy' not in str(exc).lower():
            raise
        yield False
        return
    try:
        yield True
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def start_run(conn, station_id):
    run_id = str(uuid.uuid4())
    conn.execute('INSERT INTO runs(run_id,station_id,started_at,status) VALUES (?,?,?,?)',
                 (run_id,station_id,datetime.now(UTC).isoformat(),'running'))
    return run_id


def save_snapshot(conn, payload):
    digest = sha256(payload).hexdigest()
    conn.execute('INSERT OR IGNORE INTO snapshots(hash,payload) VALUES (?,?)',(digest,payload))
    return digest


def accept(conn, run_id, reading):
    from decimal import Decimal
    document = json.dumps(asdict(reading), default=str)
    key = (reading.station_id, reading.interval_start_utc.isoformat())
    old = conn.execute('SELECT pm25_ugm3,reading FROM observations WHERE station_id=? AND interval_start_utc=?',key).fetchone()
    outcome = 'inserted' if old is None else ('unchanged' if Decimal(old[0])==reading.pm25_ugm3 else 'revised')
    if outcome=='revised':
        conn.execute('INSERT INTO revisions(station_id,interval_start_utc,old_reading,new_reading,run_id) VALUES (?,?,?,?,?)',(*key,old[1],document,run_id))
    seen = reading.fetched_at_utc.isoformat()
    conn.execute("""INSERT INTO observations
      (station_id,interval_start_utc,interval_end_utc,pm25_ugm3,reading,first_seen_at,last_seen_at,run_id)
      VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(station_id,interval_start_utc) DO UPDATE SET
      pm25_ugm3=excluded.pm25_ugm3,reading=excluded.reading,
      first_seen_at=min(observations.first_seen_at,excluded.first_seen_at),
      last_seen_at=max(observations.last_seen_at,excluded.last_seen_at),run_id=excluded.run_id""",
      (*key,reading.interval_end_utc.isoformat(),str(reading.pm25_ugm3),document,seen,seen,run_id))
    conn.execute("UPDATE runs SET completed_at=?,status='accepted',outcome=?,snapshot_hash=? WHERE run_id=?",
      (datetime.now(UTC).isoformat(),outcome,reading.raw_snapshot_hash,run_id))
    return outcome


def reject(conn, run_id, code, payload=None):
    digest=save_snapshot(conn,payload) if payload is not None else None
    conn.execute('INSERT INTO quarantine(run_id,reason_code,snapshot_hash) VALUES (?,?,?)',(run_id,code,digest))
    conn.execute("UPDATE runs SET completed_at=?,status='failed',error_code=?,snapshot_hash=? WHERE run_id=?",
      (datetime.now(UTC).isoformat(),code,digest,run_id))
