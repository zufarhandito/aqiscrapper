import argparse
import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .extractors.base import ExtractionError, SourceSnapshot, UnverifiedSourceExtractor
from .extractors.browser_capture import parse_browser_capture, TARGETS


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv(Path.cwd() / '.env')
    parser = argparse.ArgumentParser(description="IQAir current-only browser collector")
    sub = parser.add_subparsers(dest="command", required=True)
    discover = sub.add_parser("discover", help="Read saved discovery verdicts; no network request")
    discover.add_argument("--registry", type=Path, default=Path("config/stations.json"))
    discover.add_argument("--station", choices=tuple(TARGETS))
    fixture = sub.add_parser("parse-fixture", help="Fail-closed source adapter check")
    fixture.add_argument("--station", required=True, choices=tuple(TARGETS))
    fixture.add_argument("--input", type=Path, required=True)
    fixture.add_argument("--metadata", type=Path, required=True, help="Capture metadata JSON")
    for command in ('collect-once', 'schedule'):
        collect_parser = sub.add_parser(command)
        target = collect_parser.add_mutually_exclusive_group(required=True)
        target.add_argument('--station', choices=tuple(TARGETS))
        target.add_argument('--all', action='store_true')
        collect_parser.add_argument('--headed', action='store_true')
    sub.add_parser('init-db', help='Initialize local data folder (optional; auto-created)')
    sub.add_parser('report', help='Station record counts, freshness and failures')
    export = sub.add_parser('export', help='Export canonical observations as CSV')
    export.add_argument('--output', type=Path, required=True)
    capture = sub.add_parser("parse-browser-capture", help="Parse selected public station state captured via browser")
    capture.add_argument("--station", required=True, choices=tuple(TARGETS))
    capture.add_argument("--input", required=True, type=Path)
    weather_once = sub.add_parser("weather-once", help="Collect Open-Meteo and/or BMKG future weather forecasts")
    weather_once.add_argument("--provider", choices=("all", "open_meteo", "bmkg"), default="all")
    weather_once.add_argument("--horizon", type=int, default=72)
    weather_once.add_argument("--config", type=Path, default=Path("config/weather_stations.json"))
    sub.add_parser("weather-report", help="Summary of collected future weather forecasts")
    sub.add_parser("weather-export", help="Rebuild all partitioned weather forecast CSVs from weather.sqlite3")
    backup_cmd = sub.add_parser("backup-sqlite", help="Create consistent gzipped backups of local SQLite files")
    backup_cmd.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "discover":
            stations = json.loads(args.registry.read_text(encoding="utf-8"))["stations"]
            print(json.dumps([s for s in stations if not args.station or s["station_id"] == args.station], indent=2))
            return 0
        if args.command in ('collect-once', 'schedule'):
            from .collector import require_authorization, collect
            require_authorization(scheduled=args.command == 'schedule')
            data_dir = Path(os.getenv('DATA_DIR', 'data'))
            stations = list(TARGETS) if args.all else [args.station]
            def job():
                try:
                    result = collect(data_dir, stations, args.headed)
                except (sqlite3.Error, OSError) as exc:
                    print(json.dumps({'status':'LOCAL_STORAGE_ERROR','error_type':type(exc).__name__}), flush=True)
                    return False
                print(json.dumps(result), flush=True)
                if any(r.get('error_code') == 'BLOCKED_ACCESS' for r in result):
                    raise ExtractionError('BLOCKED_ACCESS', 'Source denied access; scheduler stopped')
                return not any(r['status'] == 'failed' for r in result)
            if args.command == 'collect-once':
                return 0 if job() else 2
            from .scheduler import serve
            start = datetime.fromisoformat(os.environ['COLLECTION_START_UTC'].replace('Z', '+00:00'))
            serve(job, start=start, duration_days=int(os.getenv('COLLECTION_DURATION_DAYS','90')),
                  minute=int(os.getenv('POLL_MINUTE_LOCAL','15')))
            return 0
        if args.command in ('init-db', 'report', 'export'):
            from .storage import init_store
            from .outputs import report, export_csv
            data_dir = Path(os.getenv('DATA_DIR', 'data'))
            if args.command == 'init-db':
                init_store(data_dir)
                print(json.dumps({'status':'local_storage_ready', 'data_dir':str(data_dir)}))
            elif args.command == 'report':
                print(json.dumps(report(data_dir), indent=2))
            else:
                print(json.dumps({'exported_rows':export_csv(data_dir,args.output), 'output':str(args.output)}))
            return 0
        if args.command in ('weather-once', 'weather-report', 'weather-export', 'backup-sqlite'):
            from .weather import (
                backup_sqlite_databases,
                collect_weather,
                export_bmkg_months,
                export_open_meteo_dates,
                weather_report,
            )
            data_dir = Path(os.getenv('DATA_DIR', 'data'))
            if args.command == 'weather-once':
                providers = ('open_meteo', 'bmkg') if args.provider == 'all' else (args.provider,)
                result = collect_weather(data_dir, config_path=args.config, providers=providers, horizon_hours=args.horizon)
                print(json.dumps(result), flush=True)
                return 0 if any(r['status'] == 'ok' for r in result) else 2
            if args.command == 'weather-report':
                print(json.dumps(weather_report(data_dir), indent=2))
                return 0
            if args.command == 'weather-export':
                out = {
                    'open_meteo': export_open_meteo_dates(data_dir),
                    'bmkg': export_bmkg_months(data_dir),
                }
                print(json.dumps(out, indent=2))
                return 0
            backup_dir = args.output_dir or (data_dir / 'sqlite_backup')
            print(json.dumps(backup_sqlite_databases(data_dir, backup_dir), indent=2))
            return 0
        if args.command == "parse-browser-capture":
            reading = parse_browser_capture(args.input.read_bytes(), args.station)
            print(json.dumps(asdict(reading), default=str, indent=2))
            return 0
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
        snapshot = SourceSnapshot(args.input.read_bytes(), metadata["final_url"],
                                  metadata["status"], datetime.fromisoformat(metadata["fetched_at_utc"]))
        UnverifiedSourceExtractor().parse(snapshot, args.station)
    except ExtractionError as exc:
        print(json.dumps({"status": exc.code, "detail": str(exc), "accepted_count": 0}))
        return 2
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "INVALID_INPUT", "detail": str(exc), "accepted_count": 0}))
        return 2
    except KeyboardInterrupt:
        print(json.dumps({'status':'stopped'}))
        return 130
    except Exception as exc:
        # Database exceptions can include connection credentials; expose type only.
        print(json.dumps({'status':'COLLECTOR_ERROR', 'error_type':type(exc).__name__}))
        return 2
    return 0
