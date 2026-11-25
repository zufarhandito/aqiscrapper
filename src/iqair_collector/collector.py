import os
from contextlib import closing

from .browser import capture_station
from .extractors.base import ExtractionError
from .extractors.browser_capture import parse_browser_capture
from .storage import accept, reject, save_snapshot, start_run, station_lock, connect, init_store


def require_authorization(scheduled=False):
    if os.environ.get('IQAIR_AUTOMATION_AUTHORIZED', '').lower() != 'true':
        raise ExtractionError('BLOCKED_ACCESS', 'Live automation disabled: IQAIR_AUTOMATION_AUTHORIZED must reflect actual source permission (SRD access gate)')
    if scheduled and os.environ.get('SCHEDULED_COLLECTION_ENABLED', '').lower() != 'true':
        raise ExtractionError('SCHEDULE_DISABLED', 'SCHEDULED_COLLECTION_ENABLED is false')


def collect(data_dir, stations, headed=False, fetcher=None):
    """Injected fetcher is for offline tests. CLI checks live permission first."""
    fetcher = fetcher or (lambda station: capture_station(station, headed))
    results = []
    init_store(data_dir)
    for station in stations:
        with closing(connect(data_dir)) as conn:
            with station_lock(conn, station) as acquired:
                if not acquired:
                    results.append({'station_id': station, 'status': 'locked'})
                    continue
                run_id = start_run(conn, station)
                payload = None
                try:
                    payload = fetcher(station)
                    reading = parse_browser_capture(payload, station)
                    save_snapshot(conn, payload)
                    outcome = accept(conn, run_id, reading)
                    results.append({'station_id': station, 'status': outcome, 'pm25_ugm3': str(reading.pm25_ugm3),
                                    'interval_end_utc': reading.interval_end_utc.isoformat(), 'quality_flags': reading.quality_flags})
                except ExtractionError as exc:
                    reject(conn, run_id, exc.code, payload)
                    results.append({'station_id': station, 'status': 'failed', 'error_code': exc.code})
                    if exc.code == 'BLOCKED_ACCESS':
                        break  # Host denial: stop this batch; scheduler also stops.
    from .outputs import export_station_files
    export_station_files(data_dir)
    return results
