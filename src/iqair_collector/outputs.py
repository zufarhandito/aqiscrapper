import csv
import json
import os
import tempfile
from contextlib import closing
from datetime import datetime, UTC, timedelta, timezone
from pathlib import Path

from .storage import connect, init_store, station_lock
from .extractors.browser_capture import TARGETS

# Weather values retain page-native units until the page contract is verified.
EXTRA_FIELDS = [
    'ditangkap_pada_wib', 'fetched_at_local', 'first_seen_local',
    'source_label_local', 'source_station_id', 'source_timezone',
    'latitude', 'longitude', 'aqi', 'aqi_description', 'main_pollutant',
    'main_pollutant_concentration', 'estimated', 'temperature_source',
    'humidity_source', 'pressure_source', 'wind_speed_source',
    'wind_direction_source', 'weather_condition', 'weather_icon',
    'who_exposure_ratio_source', 'who_exposure_color_source',
] + [f'{name}_{suffix}' for name in ('pm10', 'no2', 'so2', 'co', 'o3')
     for suffix in ('concentration', 'unit', 'aqi')] + [
    'pollutants_json', 'contributors_json', 'current_json', 'source_details_json',
    'raw_snapshot_hash', 'measurement_source', 'extraction_method',
    'source_label_time_raw', 'source_label_timestamp', 'observed',
]
WIB = timezone(timedelta(hours=7))
DAYS = ('Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu')
MONTHS = ('Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
          'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember')


def local_time(value):
    return datetime.fromisoformat(value).astimezone(WIB)


def extra_columns(doc, details):
    current = details.get('current') or {}
    coordinates = details.get('coordinates') or {}
    wind = current.get('wind') or {}
    exposure = current.get('WHOExposure') or {}
    fetched = local_time(doc['fetched_at_utc'])
    result = {
        'ditangkap_pada_wib': f'{DAYS[fetched.weekday()]}, {fetched.day} {MONTHS[fetched.month-1]} {fetched.year} ({fetched:%H:%M}) WIB',
        'fetched_at_local': fetched.isoformat(),
        'first_seen_local': local_time(doc['first_seen_at_utc']).isoformat(),
        'source_label_local': local_time(doc['interval_end_utc']).isoformat(),
        'source_station_id': details.get('id'), 'source_timezone': details.get('timezone'),
        'latitude': coordinates.get('latitude'), 'longitude': coordinates.get('longitude'),
        'aqi': current.get('aqi'), 'aqi_description': current.get('aqiDescription'),
        'main_pollutant': current.get('mainPollutant'),
        'main_pollutant_concentration': current.get('concentration'),
        'estimated': current.get('estimated'),
        'temperature_source': current.get('temperature'), 'humidity_source': current.get('humidity'),
        'pressure_source': current.get('pressure'), 'wind_speed_source': wind.get('speed'),
        'wind_direction_source': wind.get('direction'), 'weather_condition': current.get('condition'),
        'weather_icon': current.get('icon'),
        'who_exposure_ratio_source': exposure.get('WHOExposure'),
        'who_exposure_color_source': exposure.get('WHOExposureColor'),
    }
    for pollutant in current.get('pollutants') or []:
        name = pollutant.get('pollutantName')
        if name in ('pm10', 'no2', 'so2', 'co', 'o3'):
            for suffix in ('concentration', 'unit', 'aqi'):
                result[f'{name}_{suffix}'] = pollutant.get(suffix)
    for key, value in (('pollutants_json', current.get('pollutants', [])),
                       ('contributors_json', details.get('contributors', [])),
                       ('current_json', current), ('source_details_json', details)):
        result[key] = json.dumps(value, ensure_ascii=False, default=str)
    return result


def observation_rows(conn, station=None):
    # Recover additional fields from the exact saved snapshot for older readings.
    query = """SELECT o.reading,o.first_seen_at,s.payload FROM observations o
               LEFT JOIN runs r ON r.run_id=o.run_id
               LEFT JOIN snapshots s ON s.hash=r.snapshot_hash"""
    if station is not None:
        return conn.execute(query + ' WHERE o.station_id=? ORDER BY o.interval_start_utc', (station,)).fetchall()
    return conn.execute(query + ' ORDER BY o.interval_start_utc,o.station_id').fetchall()


CSV_FIELDS = ['station_id','source_station_name','interval_start_utc','interval_end_utc',
              'interval_start_local','pm25_ugm3','pollutant','unit','source_url','source_contributor',
              'source_time_semantics','first_seen_at_utc','fetched_at_utc','quality_flags'] + EXTRA_FIELDS


def write_csv(output, rows):
    output = Path(output)
    if output.suffix.lower() != '.csv':
        raise ValueError('Output must have .csv extension')
    output.parent.mkdir(parents=True,exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w',newline='',encoding='utf-8-sig',
             dir=output.parent, prefix='.collector-', suffix='.tmp',delete=False) as stream:
            temp = Path(stream.name)
            writer=csv.DictWriter(stream,fieldnames=CSV_FIELDS,extrasaction='ignore')
            writer.writeheader()
            count=0
            for row in rows:
                raw, first_seen = row[:2]
                doc=json.loads(raw)
                details = doc.get('source_details') or {}
                if not details and len(row) > 2 and row[2]:
                    details = json.loads(row[2]).get('details') or {}
                start=datetime.fromisoformat(doc['interval_start_utc'])
                doc['interval_start_local']=(start+timedelta(hours=7)).strftime('%Y-%m-%dT%H:%M:%S+07:00')
                doc['first_seen_at_utc']=first_seen
                doc['quality_flags']=json.dumps(doc.get('quality_flags',[]))
                doc.update(extra_columns(doc, details))
                writer.writerow(doc)
                count+=1
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp,output)
        return count
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def export_station_files(data_dir):
    init_store(data_dir)
    with closing(connect(data_dir)) as conn, station_lock(conn,'csv_export') as acquired:
        if not acquired:
            return
        for station in TARGETS:
            rows=observation_rows(conn, station)
            if rows:
                write_csv(Path(data_dir)/f'{station}.csv',rows)


def export_csv(data_dir,output):
    init_store(data_dir)
    with closing(connect(data_dir)) as conn, station_lock(conn,'csv_export') as acquired:
        if not acquired:
            raise BlockingIOError('Collector is busy; retry export after collection finishes')
        rows=observation_rows(conn)
        return write_csv(output,rows)


def report(data_dir):
    init_store(data_dir)
    # Recover CSV projections if an earlier process stopped after committing data.
    export_station_files(data_dir)
    with closing(connect(data_dir)) as conn:
        rows=conn.execute('SELECT station_id,count(*),max(interval_end_utc) FROM observations GROUP BY station_id ORDER BY station_id').fetchall()
        failures=dict(conn.execute("SELECT station_id,count(*) FROM runs WHERE status='failed' GROUP BY station_id").fetchall())
    return [{'station_id':station,'observed_slots':count,'latest_interval_end_utc':latest,
             'staleness_hours':round((datetime.now(UTC)-datetime.fromisoformat(latest)).total_seconds()/3600,2),
             'failed_runs':failures.get(station,0),'csv_file':str(Path(data_dir)/f'{station}.csv')}
            for station,count,latest in rows]
