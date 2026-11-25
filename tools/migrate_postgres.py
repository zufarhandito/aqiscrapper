"""One-time read-only migration of the previous PostgreSQL store. Not needed on Pi."""
from contextlib import closing
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

from iqair_collector.storage import connect, init_store, station_lock
from iqair_collector.outputs import export_station_files


def migrate():
    load_dotenv(Path.cwd()/'.env')
    data_dir=Path(os.getenv('DATA_DIR','data'))
    init_store(data_dir)
    # No source DELETE/UPDATE/DDL. Existing local intervals are not overwritten.
    with psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=10) as source:
        source.execute('SET TRANSACTION READ ONLY')
        with closing(connect(data_dir)) as target, station_lock(target,'migration') as acquired:
            if not acquired:
                raise RuntimeError('Local collector busy; stop it before migration')
            target.execute('CREATE TABLE IF NOT EXISTS legacy_imports (kind TEXT, id TEXT, PRIMARY KEY(kind,id))')
            for row in source.execute('SELECT run_id,station_id,started_at,completed_at,status,error_code,outcome,snapshot_hash FROM collector_runs'):
                values=[v.isoformat() if hasattr(v,'isoformat') else str(v) if i==0 else v for i,v in enumerate(row)]
                target.execute('INSERT OR IGNORE INTO runs(run_id,station_id,started_at,completed_at,status,error_code,outcome,snapshot_hash) VALUES (?,?,?,?,?,?,?,?)',values)
            for digest,payload in source.execute('SELECT hash,payload FROM collector_snapshots'):
                target.execute('INSERT OR IGNORE INTO snapshots(hash,payload) VALUES (?,?)',(digest,bytes(payload)))
            imported=0
            for station,start,end,value,reading,first,last,run in source.execute('SELECT station_id,interval_start_utc,interval_end_utc,pm25_ugm3,reading,first_seen_at,last_seen_at,run_id FROM collector_observations'):
                cursor=target.execute('INSERT OR IGNORE INTO observations(station_id,interval_start_utc,interval_end_utc,pm25_ugm3,reading,first_seen_at,last_seen_at,run_id) VALUES (?,?,?,?,?,?,?,?)',
                    (station,start.isoformat(),end.isoformat(),str(value),json.dumps(reading),first.isoformat(),last.isoformat(),str(run)))
                imported+=cursor.rowcount
            for identity,station,start,old,new,run in source.execute('SELECT id,station_id,interval_start_utc,old_reading,new_reading,run_id FROM collector_revisions'):
                if target.execute('INSERT OR IGNORE INTO legacy_imports VALUES (?,?)',('revision',str(identity))).rowcount:
                    target.execute('INSERT INTO revisions(station_id,interval_start_utc,old_reading,new_reading,run_id) VALUES (?,?,?,?,?)',
                        (station,start.isoformat(),json.dumps(old),json.dumps(new),str(run)))
            for identity,run,code,digest in source.execute('SELECT id,run_id,reason_code,snapshot_hash FROM collector_quarantine'):
                if target.execute('INSERT OR IGNORE INTO legacy_imports VALUES (?,?)',('quarantine',str(identity))).rowcount:
                    target.execute('INSERT INTO quarantine(run_id,reason_code,snapshot_hash) VALUES (?,?,?)',(str(run),code,digest))
    export_station_files(data_dir)
    return imported


if __name__=='__main__':
    try:
        print(json.dumps({'imported_observations':migrate(),'source':'unchanged'}))
    except Exception as exc:
        print(json.dumps({'status':'migration_failed','error_type':type(exc).__name__}))
        raise SystemExit(2)
