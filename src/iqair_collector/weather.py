"""Open-Meteo (hourly) and BMKG (3-hourly) future weather forecast collector.

Stores operational snapshots in an isolated SQLite file (`weather.sqlite3`) and
exports partitioned CSVs suitable for anti-leakage ML pipelines and rclone sync.
"""
from contextlib import closing
import csv
from datetime import datetime, timedelta, timezone, UTC
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid

from .outputs import DAYS, MONTHS, WIB

OPEN_METEO_ENDPOINT = 'https://api.open-meteo.com/v1/forecast'
BMKG_ENDPOINT = 'https://api.bmkg.go.id/publik/prakiraan-cuaca'
OPEN_METEO_HOURLY_VARS = (
    'temperature_2m',
    'relative_humidity_2m',
    'precipitation',
    'rain',
    'precipitation_probability',
    'wind_speed_10m',
    'wind_direction_10m',
    'surface_pressure',
    'cloud_cover',
    'weather_code',
)
USER_AGENT = 'iqair-yogyakarta-research-weather/0.1'

WEATHER_SCHEMA = """
CREATE TABLE IF NOT EXISTS weather_runs (
    run_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    station_id TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    completed_at_utc TEXT,
    status TEXT NOT NULL,
    error_code TEXT,
    error_detail TEXT,
    rows_written INTEGER DEFAULT 0,
    snapshot_hash TEXT
);

CREATE TABLE IF NOT EXISTS weather_snapshots (
    hash TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    payload_gzip BLOB NOT NULL,
    raw_bytes INTEGER NOT NULL,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS open_meteo_forecasts (
    station_id TEXT NOT NULL,
    issue_hour_utc TEXT NOT NULL,
    forecast_valid_utc TEXT NOT NULL,
    forecast_issued_at_utc TEXT NOT NULL,
    ditangkap_pada_wib TEXT NOT NULL,
    issue_date_wib TEXT NOT NULL,
    forecast_valid_wib TEXT NOT NULL,
    lead_time_hours INTEGER NOT NULL,
    req_latitude REAL NOT NULL,
    req_longitude REAL NOT NULL,
    grid_latitude REAL,
    grid_longitude REAL,
    elevation_m REAL,
    temperature_2m_c REAL,
    relative_humidity_2m_pct REAL,
    precipitation_mm REAL,
    rain_mm REAL,
    precipitation_probability_pct REAL,
    wind_speed_10m_ms REAL,
    wind_direction_10m_deg REAL,
    surface_pressure_hpa REAL,
    cloud_cover_pct REAL,
    weather_code INTEGER,
    raw_snapshot_hash TEXT NOT NULL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (station_id, issue_hour_utc, forecast_valid_utc)
);

CREATE INDEX IF NOT EXISTS idx_om_issue_date ON open_meteo_forecasts(issue_date_wib, station_id, issue_hour_utc);

CREATE TABLE IF NOT EXISTS bmkg_forecasts (
    station_id TEXT NOT NULL,
    analysis_date_utc TEXT NOT NULL,
    forecast_valid_utc TEXT NOT NULL,
    adm4 TEXT NOT NULL,
    desa TEXT,
    kecamatan TEXT,
    adm4_latitude REAL,
    adm4_longitude REAL,
    first_seen_at_utc TEXT NOT NULL,
    last_seen_at_utc TEXT NOT NULL,
    ditangkap_pada_wib TEXT NOT NULL,
    analysis_month_wib TEXT NOT NULL,
    forecast_valid_wib TEXT NOT NULL,
    lead_time_from_analysis_hours REAL,
    lead_time_from_first_seen_hours REAL,
    temperature_c REAL,
    relative_humidity_pct REAL,
    precipitation_mm REAL,
    wind_speed_kmh REAL,
    wind_speed_ms REAL,
    wind_direction_deg REAL,
    wind_direction_cardinal TEXT,
    wind_direction_to TEXT,
    cloud_cover_pct REAL,
    weather_code INTEGER,
    weather_desc TEXT,
    weather_desc_en TEXT,
    visibility_m REAL,
    visibility_text TEXT,
    time_index TEXT,
    raw_snapshot_hash TEXT NOT NULL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (station_id, analysis_date_utc, forecast_valid_utc)
);

CREATE INDEX IF NOT EXISTS idx_bmkg_month ON bmkg_forecasts(analysis_month_wib, station_id, analysis_date_utc);
"""

OPEN_METEO_CSV_FIELDS = [
    'station_id', 'issue_hour_utc', 'forecast_issued_at_utc', 'ditangkap_pada_wib',
    'forecast_valid_utc', 'forecast_valid_wib', 'lead_time_hours',
    'req_latitude', 'req_longitude', 'grid_latitude', 'grid_longitude', 'elevation_m',
    'temperature_2m_c', 'relative_humidity_2m_pct', 'precipitation_mm', 'rain_mm',
    'precipitation_probability_pct', 'wind_speed_10m_ms', 'wind_direction_10m_deg',
    'surface_pressure_hpa', 'cloud_cover_pct', 'weather_code', 'raw_snapshot_hash',
]

BMKG_CSV_FIELDS = [
    'station_id', 'adm4', 'desa', 'kecamatan', 'adm4_latitude', 'adm4_longitude',
    'analysis_date_utc', 'first_seen_at_utc', 'last_seen_at_utc', 'ditangkap_pada_wib',
    'forecast_valid_utc', 'forecast_valid_wib',
    'lead_time_from_analysis_hours', 'lead_time_from_first_seen_hours',
    'temperature_c', 'relative_humidity_pct', 'precipitation_mm',
    'wind_speed_kmh', 'wind_speed_ms', 'wind_direction_deg',
    'wind_direction_cardinal', 'wind_direction_to', 'cloud_cover_pct',
    'weather_code', 'weather_desc', 'weather_desc_en',
    'visibility_m', 'visibility_text', 'time_index', 'raw_snapshot_hash',
]


def format_wib_readable(dt_utc: datetime) -> str:
    local = dt_utc.astimezone(WIB)
    return f'{DAYS[local.weekday()]}, {local.day} {MONTHS[local.month - 1]} {local.year} ({local:%H:%M}) WIB'


def parse_utc_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def connect_weather(data_dir: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(Path(data_dir) / 'weather.sqlite3', timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_weather_store(data_dir: Path) -> None:
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    with closing(connect_weather(data_dir)) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript(WEATHER_SCHEMA)
        conn.commit()


def load_weather_stations(config_path: Path = Path('config/weather_stations.json')) -> list[dict]:
    doc = json.loads(Path(config_path).read_text(encoding='utf-8'))
    return list(doc['stations'])


def _http_get_bytes(url: str, timeout: int = 20, retries: int = 2) -> bytes:
    last_exc = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
            with urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise HTTPError(url, resp.status, f'HTTP {resp.status}', resp.headers, None)
                return resp.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if isinstance(exc, HTTPError) and exc.code in (400, 401, 403, 404):
                raise
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise last_exc


def fetch_open_meteo(latitude: float, longitude: float, horizon_hours: int = 72, timeout: int = 20) -> bytes:
    params = {
        'latitude': f'{latitude:.6f}',
        'longitude': f'{longitude:.6f}',
        'hourly': ','.join(OPEN_METEO_HOURLY_VARS),
        'wind_speed_unit': 'ms',
        'precipitation_unit': 'mm',
        'temperature_unit': 'celsius',
        'timezone': 'UTC',
        'forecast_hours': str(horizon_hours + 2),
        'past_hours': '0',
    }
    url = f'{OPEN_METEO_ENDPOINT}?{urlencode(params)}'
    return _http_get_bytes(url, timeout=timeout)


def fetch_bmkg(adm4: str, timeout: int = 20) -> bytes:
    url = f'{BMKG_ENDPOINT}?{urlencode({"adm4": adm4})}'
    return _http_get_bytes(url, timeout=timeout)


def save_weather_snapshot(conn: sqlite3.Connection, provider: str, payload: bytes, now_utc: datetime) -> str:
    digest = sha256(payload).hexdigest()
    compressed = gzip.compress(payload, compresslevel=6)
    conn.execute(
        'INSERT OR IGNORE INTO weather_snapshots(hash, provider, payload_gzip, raw_bytes, created_at_utc) VALUES (?,?,?,?,?)',
        (digest, provider, compressed, len(payload), now_utc.astimezone(UTC).isoformat()),
    )
    return digest


def parse_open_meteo(payload: bytes, station: dict, fetched_at_utc: datetime, horizon_hours: int = 72) -> list[dict]:
    doc = json.loads(payload.decode('utf-8'))
    hourly = doc.get('hourly') or {}
    times = hourly.get('time') or []
    if not times:
        raise ValueError('Open-Meteo payload missing hourly.time')

    fetched_utc = fetched_at_utc.astimezone(UTC)
    issue_hour = fetched_utc.replace(minute=0, second=0, microsecond=0)
    issue_date_wib = fetched_utc.astimezone(WIB).strftime('%Y-%m-%d')
    wib_label = format_wib_readable(fetched_utc)
    digest = sha256(payload).hexdigest()

    def _val(key: str, idx: int):
        arr = hourly.get(key)
        if not isinstance(arr, list) or idx >= len(arr):
            return None
        return arr[idx]

    rows = []
    for idx, ts_raw in enumerate(times):
        valid_utc = parse_utc_timestamp(ts_raw)
        lead_hours = int(round((valid_utc - issue_hour).total_seconds() / 3600))
        if not (0 <= lead_hours <= horizon_hours):
            continue
        rows.append({
            'station_id': station['station_id'],
            'issue_hour_utc': issue_hour.isoformat(),
            'forecast_valid_utc': valid_utc.isoformat(),
            'forecast_issued_at_utc': fetched_utc.isoformat(),
            'ditangkap_pada_wib': wib_label,
            'issue_date_wib': issue_date_wib,
            'forecast_valid_wib': valid_utc.astimezone(WIB).isoformat(),
            'lead_time_hours': lead_hours,
            'req_latitude': float(station['latitude']),
            'req_longitude': float(station['longitude']),
            'grid_latitude': doc.get('latitude'),
            'grid_longitude': doc.get('longitude'),
            'elevation_m': doc.get('elevation'),
            'temperature_2m_c': _val('temperature_2m', idx),
            'relative_humidity_2m_pct': _val('relative_humidity_2m', idx),
            'precipitation_mm': _val('precipitation', idx),
            'rain_mm': _val('rain', idx),
            'precipitation_probability_pct': _val('precipitation_probability', idx),
            'wind_speed_10m_ms': _val('wind_speed_10m', idx),
            'wind_direction_10m_deg': _val('wind_direction_10m', idx),
            'surface_pressure_hpa': _val('surface_pressure', idx),
            'cloud_cover_pct': _val('cloud_cover', idx),
            'weather_code': _val('weather_code', idx),
            'raw_snapshot_hash': digest,
        })
    if not rows:
        raise ValueError('Open-Meteo payload yielded zero rows in requested horizon')
    return rows


def parse_bmkg(payload: bytes, station: dict, fetched_at_utc: datetime) -> list[dict]:
    doc = json.loads(payload.decode('utf-8'))
    loc = doc.get('lokasi') or {}
    data_list = doc.get('data') or []
    if not data_list:
        raise ValueError('BMKG payload missing data[]')
    cuaca_groups = data_list[0].get('cuaca') or []
    items = [item for group in cuaca_groups if isinstance(group, list) for item in group if isinstance(item, dict)]
    if not items:
        raise ValueError('BMKG payload missing cuaca entries')

    fetched_utc = fetched_at_utc.astimezone(UTC)
    wib_label = format_wib_readable(fetched_utc)
    digest = sha256(payload).hexdigest()

    rows = []
    for item in items:
        valid_raw = item.get('datetime') or item.get('utc_datetime')
        analysis_raw = item.get('analysis_date')
        if not valid_raw or not analysis_raw:
            continue
        valid_utc = parse_utc_timestamp(valid_raw)
        analysis_utc = parse_utc_timestamp(analysis_raw)
        ws_kmh = item.get('ws')
        ws_ms = round(float(ws_kmh) / 3.6, 3) if ws_kmh is not None else None
        rows.append({
            'station_id': station['station_id'],
            'analysis_date_utc': analysis_utc.isoformat(),
            'forecast_valid_utc': valid_utc.isoformat(),
            'adm4': str(loc.get('adm4') or station['bmkg_adm4']),
            'desa': loc.get('desa') or station.get('bmkg_desa'),
            'kecamatan': loc.get('kecamatan') or station.get('bmkg_kecamatan'),
            'adm4_latitude': loc.get('lat'),
            'adm4_longitude': loc.get('lon'),
            'first_seen_at_utc': fetched_utc.isoformat(),
            'last_seen_at_utc': fetched_utc.isoformat(),
            'ditangkap_pada_wib': wib_label,
            'analysis_month_wib': analysis_utc.astimezone(WIB).strftime('%Y-%m'),
            'forecast_valid_wib': valid_utc.astimezone(WIB).isoformat(),
            'lead_time_from_analysis_hours': round((valid_utc - analysis_utc).total_seconds() / 3600, 2),
            'lead_time_from_first_seen_hours': round((valid_utc - fetched_utc).total_seconds() / 3600, 2),
            'temperature_c': item.get('t'),
            'relative_humidity_pct': item.get('hu'),
            'precipitation_mm': item.get('tp'),
            'wind_speed_kmh': ws_kmh,
            'wind_speed_ms': ws_ms,
            'wind_direction_deg': item.get('wd_deg'),
            'wind_direction_cardinal': item.get('wd'),
            'wind_direction_to': item.get('wd_to'),
            'cloud_cover_pct': item.get('tcc'),
            'weather_code': item.get('weather'),
            'weather_desc': item.get('weather_desc'),
            'weather_desc_en': item.get('weather_desc_en'),
            'visibility_m': item.get('vs'),
            'visibility_text': item.get('vs_text'),
            'time_index': item.get('time_index'),
            'raw_snapshot_hash': digest,
        })
    if not rows:
        raise ValueError('BMKG payload yielded zero valid forecast rows')
    return rows


def _atomic_write_csv(output_path: Path, fieldnames: list[str], rows: list[sqlite3.Row]) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', newline='', encoding='utf-8-sig',
            dir=output_path.parent, prefix='.weather-', suffix='.tmp', delete=False
        ) as stream:
            temp = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, output_path)
        return len(rows)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def export_open_meteo_dates(data_dir: Path, issue_dates_wib: set[str] | None = None) -> dict[str, int]:
    init_weather_store(data_dir)
    exported: dict[str, int] = {}
    with closing(connect_weather(data_dir)) as conn:
        if issue_dates_wib is None:
            dates = [r[0] for r in conn.execute('SELECT DISTINCT issue_date_wib FROM open_meteo_forecasts ORDER BY issue_date_wib').fetchall()]
        else:
            dates = sorted(issue_dates_wib)
        for day in dates:
            rows = conn.execute(
                """SELECT * FROM open_meteo_forecasts
                   WHERE issue_date_wib = ?
                   ORDER BY issue_hour_utc, station_id, lead_time_hours""",
                (day,),
            ).fetchall()
            if not rows:
                continue
            month_dir = day[:7]
            target = Path(data_dir) / 'weather_forecast' / 'open_meteo' / month_dir / f'open_meteo_{day}.csv'
            exported[str(target)] = _atomic_write_csv(target, OPEN_METEO_CSV_FIELDS, rows)
    return exported


def export_bmkg_months(data_dir: Path, months_wib: set[str] | None = None) -> dict[str, int]:
    init_weather_store(data_dir)
    exported: dict[str, int] = {}
    with closing(connect_weather(data_dir)) as conn:
        if months_wib is None:
            months = [r[0] for r in conn.execute('SELECT DISTINCT analysis_month_wib FROM bmkg_forecasts ORDER BY analysis_month_wib').fetchall()]
        else:
            months = sorted(months_wib)
        for month in months:
            rows = conn.execute(
                """SELECT * FROM bmkg_forecasts
                   WHERE analysis_month_wib = ?
                   ORDER BY analysis_date_utc, station_id, forecast_valid_utc""",
                (month,),
            ).fetchall()
            if not rows:
                continue
            target = Path(data_dir) / 'weather_forecast' / 'bmkg' / f'bmkg_{month}.csv'
            exported[str(target)] = _atomic_write_csv(target, BMKG_CSV_FIELDS, rows)
    return exported


def collect_weather(
    data_dir: Path,
    config_path: Path = Path('config/weather_stations.json'),
    providers: tuple[str, ...] = ('open_meteo', 'bmkg'),
    horizon_hours: int = 72,
    open_meteo_fetcher=None,
    bmkg_fetcher=None,
    now_utc: datetime | None = None,
) -> list[dict]:
    init_weather_store(data_dir)
    stations = load_weather_stations(config_path)
    om_fetch = open_meteo_fetcher or (lambda st: fetch_open_meteo(st['latitude'], st['longitude'], horizon_hours=horizon_hours))
    bmkg_fetch = bmkg_fetcher or (lambda st: fetch_bmkg(st['bmkg_adm4']))

    results: list[dict] = []
    touched_om_dates: set[str] = set()
    touched_bmkg_months: set[str] = set()

    for provider in providers:
        for station in stations:
            run_id = str(uuid.uuid4())
            started = (now_utc or datetime.now(UTC)).astimezone(UTC)
            with closing(connect_weather(data_dir)) as conn:
                conn.execute(
                    'INSERT INTO weather_runs(run_id, provider, station_id, started_at_utc, status) VALUES (?,?,?,?,?)',
                    (run_id, provider, station['station_id'], started.isoformat(), 'running'),
                )
                conn.commit()
                try:
                    if provider == 'open_meteo':
                        payload = om_fetch(station)
                        fetched_at = (now_utc or datetime.now(UTC)).astimezone(UTC)
                        digest = save_weather_snapshot(conn, provider, payload, fetched_at)
                        rows = parse_open_meteo(payload, station, fetched_at, horizon_hours=horizon_hours)
                        for r in rows:
                            r['run_id'] = run_id
                            touched_om_dates.add(r['issue_date_wib'])
                        cols = list(rows[0].keys())
                        placeholders = ','.join('?' for _ in cols)
                        update_cols = [c for c in cols if c not in ('station_id', 'issue_hour_utc', 'forecast_valid_utc')]
                        update_sql = ','.join(f'{c}=excluded.{c}' for c in update_cols)
                        conn.executemany(
                            f'INSERT INTO open_meteo_forecasts({",".join(cols)}) VALUES ({placeholders}) '
                            f'ON CONFLICT(station_id, issue_hour_utc, forecast_valid_utc) DO UPDATE SET {update_sql}',
                            [[r[c] for c in cols] for r in rows],
                        )
                    elif provider == 'bmkg':
                        payload = bmkg_fetch(station)
                        fetched_at = (now_utc or datetime.now(UTC)).astimezone(UTC)
                        digest = save_weather_snapshot(conn, provider, payload, fetched_at)
                        rows = parse_bmkg(payload, station, fetched_at)
                        for r in rows:
                            r['run_id'] = run_id
                            touched_bmkg_months.add(r['analysis_month_wib'])
                        cols = list(rows[0].keys())
                        placeholders = ','.join('?' for _ in cols)
                        # Preserve first_seen_at_utc, ditangkap_pada_wib, lead_time_from_first_seen_hours
                        # so operational availability timestamp is never overwritten by later polls.
                        preserve = {'station_id', 'analysis_date_utc', 'forecast_valid_utc',
                                    'first_seen_at_utc', 'ditangkap_pada_wib', 'lead_time_from_first_seen_hours'}
                        update_cols = [c for c in cols if c not in preserve]
                        update_sql = ','.join(f'{c}=excluded.{c}' for c in update_cols)
                        conn.executemany(
                            f'INSERT INTO bmkg_forecasts({",".join(cols)}) VALUES ({placeholders}) '
                            f'ON CONFLICT(station_id, analysis_date_utc, forecast_valid_utc) DO UPDATE SET {update_sql}',
                            [[r[c] for c in cols] for r in rows],
                        )
                    else:
                        raise ValueError(f'Unknown weather provider: {provider}')

                    completed = (now_utc or datetime.now(UTC)).astimezone(UTC)
                    conn.execute(
                        'UPDATE weather_runs SET completed_at_utc=?, status=?, rows_written=?, snapshot_hash=? WHERE run_id=?',
                        (completed.isoformat(), 'ok', len(rows), digest, run_id),
                    )
                    conn.commit()
                    results.append({
                        'provider': provider,
                        'station_id': station['station_id'],
                        'status': 'ok',
                        'rows_written': len(rows),
                    })
                except Exception as exc:
                    completed = (now_utc or datetime.now(UTC)).astimezone(UTC)
                    conn.execute(
                        'UPDATE weather_runs SET completed_at_utc=?, status=?, error_code=?, error_detail=? WHERE run_id=?',
                        (completed.isoformat(), 'failed', type(exc).__name__, str(exc)[:300], run_id),
                    )
                    conn.commit()
                    results.append({
                        'provider': provider,
                        'station_id': station['station_id'],
                        'status': 'failed',
                        'error_code': type(exc).__name__,
                    })

    if touched_om_dates:
        export_open_meteo_dates(data_dir, touched_om_dates)
    if touched_bmkg_months:
        export_bmkg_months(data_dir, touched_bmkg_months)
    return results


def weather_report(data_dir: Path) -> dict:
    init_weather_store(data_dir)
    with closing(connect_weather(data_dir)) as conn:
        om_rows = [
            dict(r) for r in conn.execute(
                """SELECT station_id,
                          COUNT(DISTINCT issue_hour_utc) AS issue_hours,
                          COUNT(*) AS total_rows,
                          MAX(issue_hour_utc) AS latest_issue_hour_utc
                   FROM open_meteo_forecasts
                   GROUP BY station_id ORDER BY station_id"""
            ).fetchall()
        ]
        bmkg_rows = [
            dict(r) for r in conn.execute(
                """SELECT station_id, adm4,
                          COUNT(DISTINCT analysis_date_utc) AS analysis_runs,
                          COUNT(*) AS total_rows,
                          MAX(analysis_date_utc) AS latest_analysis_date_utc,
                          MAX(first_seen_at_utc) AS latest_first_seen_utc
                   FROM bmkg_forecasts
                   GROUP BY station_id, adm4 ORDER BY station_id"""
            ).fetchall()
        ]
        failed = [
            dict(r) for r in conn.execute(
                """SELECT provider, station_id, COUNT(*) AS failed_runs
                   FROM weather_runs WHERE status='failed'
                   GROUP BY provider, station_id ORDER BY provider, station_id"""
            ).fetchall()
        ]
        snapshots = conn.execute(
            'SELECT COUNT(*) AS count, COALESCE(SUM(LENGTH(payload_gzip)), 0) AS gzip_bytes FROM weather_snapshots'
        ).fetchone()
    return {
        'open_meteo': om_rows,
        'bmkg': bmkg_rows,
        'failed_runs': failed,
        'snapshots': dict(snapshots),
    }


def backup_sqlite_databases(data_dir: Path, backup_dir: Path) -> list[dict]:
    """Create consistent gzipped backups of SQLite files using the SQLite backup API."""
    data_dir = Path(data_dir)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for db_name in ('state.sqlite3', 'weather.sqlite3'):
        src_path = data_dir / db_name
        if not src_path.exists():
            continue
        tmp_db = backup_dir / f'.{db_name}.bak.tmp'
        tmp_gz = backup_dir / f'.{db_name}.gz.tmp'
        final_gz = backup_dir / f'{db_name}.gz'
        try:
            with closing(sqlite3.connect(src_path, timeout=15)) as src, \
                 closing(sqlite3.connect(tmp_db)) as dst:
                src.backup(dst)
            with tmp_db.open('rb') as raw_in, gzip.open(tmp_gz, 'wb', compresslevel=6) as gz_out:
                while True:
                    chunk = raw_in.read(65536)
                    if not chunk:
                        break
                    gz_out.write(chunk)
            os.replace(tmp_gz, final_gz)
            outputs.append({
                'database': db_name,
                'backup_file': str(final_gz),
                'raw_bytes': tmp_db.stat().st_size,
                'gzip_bytes': final_gz.stat().st_size,
            })
        finally:
            tmp_db.unlink(missing_ok=True)
            tmp_gz.unlink(missing_ok=True)
    return outputs
