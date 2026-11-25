"""Offline tests for Open-Meteo & BMKG future weather forecast collector."""
import csv
from datetime import datetime, timedelta, UTC
import gzip
import json
from pathlib import Path
import sqlite3

from iqair_collector.weather import (
    backup_sqlite_databases,
    collect_weather,
    export_bmkg_months,
    export_open_meteo_dates,
    weather_report,
)

ROOT = Path(__file__).resolve().parents[1]
WEATHER_CFG = ROOT / 'config' / 'weather_stations.json'


def sample_open_meteo_bytes(base_utc: datetime, hours: int = 75) -> bytes:
    times = [(base_utc + timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M') for i in range(-1, hours)]
    n = len(times)
    payload = {
        'latitude': -7.6977,
        'longitude': 110.3745,
        'elevation': 179.0,
        'hourly': {
            'time': times,
            'temperature_2m': [27.0 + (i % 5) * 0.5 for i in range(n)],
            'relative_humidity_2m': [80.0] * n,
            'precipitation': [0.2 if i % 4 == 0 else 0.0 for i in range(n)],
            'rain': [0.2 if i % 4 == 0 else 0.0 for i in range(n)],
            'precipitation_probability': [40] * n,
            'wind_speed_10m': [2.5] * n,
            'wind_direction_10m': [185] * n,
            'surface_pressure': [1010.2] * n,
            'cloud_cover': [65] * n,
            'weather_code': [3] * n,
        },
    }
    return json.dumps(payload).encode('utf-8')


def sample_bmkg_bytes(station: dict, analysis_utc: str = '2026-11-25T00:00:00') -> bytes:
    payload = {
        'lokasi': {
            'adm4': station['bmkg_adm4'],
            'desa': station['bmkg_desa'],
            'kecamatan': station['bmkg_kecamatan'],
            'lat': station['latitude'],
            'lon': station['longitude'],
        },
        'data': [{
            'cuaca': [[
                {
                    'datetime': '2026-11-25T06:00:00Z',
                    't': 31, 'tcc': 90, 'tp': 3.3, 'weather': 61,
                    'weather_desc': 'Hujan Ringan', 'weather_desc_en': 'Light Rain',
                    'wd_deg': 192, 'wd': 'S', 'wd_to': 'N', 'ws': 7.2, 'hu': 79,
                    'vs': None, 'vs_text': None, 'time_index': '5-6',
                    'analysis_date': analysis_utc,
                },
                {
                    'datetime': '2026-11-25T09:00:00Z',
                    't': 29, 'tcc': 85, 'tp': 0.8, 'weather': 61,
                    'weather_desc': 'Hujan Ringan', 'weather_desc_en': 'Light Rain',
                    'wd_deg': 200, 'wd': 'S', 'wd_to': 'N', 'ws': 5.4, 'hu': 84,
                    'vs': 10000, 'vs_text': '> 10 km', 'time_index': '8-9',
                    'analysis_date': analysis_utc,
                },
            ]]
        }],
    }
    return json.dumps(payload).encode('utf-8')


def test_open_meteo_and_bmkg_collection_and_partitioned_csv(tmp_path):
    t1 = datetime(2026, 11, 25, 4, 2, 10, tzinfo=UTC)  # 11:02 WIB
    base = datetime(2026, 11, 25, 4, 0, 0, tzinfo=UTC)
    om_payload = sample_open_meteo_bytes(base)

    res = collect_weather(
        tmp_path,
        config_path=WEATHER_CFG,
        providers=('open_meteo', 'bmkg'),
        horizon_hours=72,
        open_meteo_fetcher=lambda st: om_payload,
        bmkg_fetcher=lambda st: sample_bmkg_bytes(st),
        now_utc=t1,
    )
    assert len(res) == 6
    assert all(r['status'] == 'ok' for r in res)

    om_csv = tmp_path / 'weather_forecast' / 'open_meteo' / '2026-11' / 'open_meteo_2026-11-25.csv'
    bmkg_csv = tmp_path / 'weather_forecast' / 'bmkg' / 'bmkg_2026-11.csv'
    assert om_csv.exists()
    assert bmkg_csv.exists()

    with om_csv.open(encoding='utf-8-sig') as f:
        om_rows = list(csv.DictReader(f))
    # 3 stations * 73 steps (lead_time_hours 0..72)
    assert len(om_rows) == 3 * 73
    assert om_rows[0]['ditangkap_pada_wib'] == 'Rabu, 25 November 2026 (11:02) WIB'
    assert om_rows[0]['lead_time_hours'] == '0'
    assert om_rows[-1]['lead_time_hours'] == '72'

    with bmkg_csv.open(encoding='utf-8-sig') as f:
        bmkg_rows = list(csv.DictReader(f))
    assert len(bmkg_rows) == 3 * 2
    assert bmkg_rows[0]['precipitation_mm'] == '3.3'
    assert bmkg_rows[0]['wind_speed_ms'] == '2.0'
    assert bmkg_rows[0]['first_seen_at_utc'] == t1.isoformat()

    # Poll again 1 hour later with same BMKG analysis_date: must dedup & preserve first_seen_at_utc
    t2 = datetime(2026, 11, 25, 5, 2, 10, tzinfo=UTC)
    collect_weather(
        tmp_path,
        config_path=WEATHER_CFG,
        providers=('bmkg',),
        bmkg_fetcher=lambda st: sample_bmkg_bytes(st),
        now_utc=t2,
    )
    with bmkg_csv.open(encoding='utf-8-sig') as f:
        bmkg_rows_after = list(csv.DictReader(f))
    assert len(bmkg_rows_after) == 6
    assert bmkg_rows_after[0]['first_seen_at_utc'] == t1.isoformat()
    assert bmkg_rows_after[0]['last_seen_at_utc'] == t2.isoformat()
    assert bmkg_rows_after[0]['ditangkap_pada_wib'] == 'Rabu, 25 November 2026 (11:02) WIB'

    rep = weather_report(tmp_path)
    assert len(rep['open_meteo']) == 3
    assert len(rep['bmkg']) == 3
    assert rep['failed_runs'] == []


def test_partial_provider_failure_isolated_and_logged(tmp_path):
    t1 = datetime(2026, 11, 25, 4, 2, 0, tzinfo=UTC)

    def flaky_bmkg(st):
        if st['station_id'] == 'dteti_ugm':
            raise TimeoutError('simulated timeout')
        return sample_bmkg_bytes(st)

    res = collect_weather(
        tmp_path,
        config_path=WEATHER_CFG,
        providers=('bmkg',),
        bmkg_fetcher=flaky_bmkg,
        now_utc=t1,
    )
    statuses = {r['station_id']: r['status'] for r in res}
    assert statuses == {'bmkg_sleman': 'ok', 'dteti_ugm': 'failed', 'amaranta_prambanan': 'ok'}
    rep = weather_report(tmp_path)
    assert len(rep['failed_runs']) == 1
    assert rep['failed_runs'][0]['station_id'] == 'dteti_ugm'


def test_sqlite_backup_and_full_export(tmp_path):
    t1 = datetime(2026, 11, 25, 4, 2, 0, tzinfo=UTC)
    base = datetime(2026, 11, 25, 4, 0, 0, tzinfo=UTC)
    collect_weather(
        tmp_path,
        config_path=WEATHER_CFG,
        providers=('open_meteo', 'bmkg'),
        horizon_hours=6,
        open_meteo_fetcher=lambda st: sample_open_meteo_bytes(base, hours=10),
        bmkg_fetcher=lambda st: sample_bmkg_bytes(st),
        now_utc=t1,
    )
    out = backup_sqlite_databases(tmp_path, tmp_path / 'sqlite_backup')
    assert len(out) == 1
    assert out[0]['database'] == 'weather.sqlite3'
    gz_path = Path(out[0]['backup_file'])
    assert gz_path.exists()

    restored = tmp_path / 'restored.sqlite3'
    restored.write_bytes(gzip.decompress(gz_path.read_bytes()))
    conn = sqlite3.connect(restored)
    try:
        cnt = conn.execute('SELECT COUNT(*) FROM open_meteo_forecasts').fetchone()[0]
        assert cnt == 3 * 7
    finally:
        conn.close()

    assert len(export_open_meteo_dates(tmp_path)) == 1
    assert len(export_bmkg_months(tmp_path)) == 1
