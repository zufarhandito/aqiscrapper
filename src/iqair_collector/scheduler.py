from datetime import datetime, timedelta, UTC


def next_run(now, minute=15):
    if now.tzinfo is None or not 0 <= minute <= 59:
        raise ValueError('Aware time and minute 0..59 required')
    now = now.astimezone(UTC)
    slot = now.replace(minute=minute, second=0, microsecond=0)
    return slot if slot > now else slot + timedelta(hours=1)


def serve(job, start, duration_days=90, minute=15, stop=None):
    """One scheduler. Polling clock permits graceful Ctrl+C; no overlapping jobs."""
    from threading import Event
    stop = stop or Event()
    if not 1 <= duration_days <= 90:
        raise ValueError('Duration must be 1..90 days')
    if start.tzinfo is None or start > datetime.now(UTC):
        raise ValueError('COLLECTION_START_UTC must be an aware timestamp at or before now')
    end = start + timedelta(days=duration_days)
    print(f'collection_window_utc={start.isoformat()}..{end.isoformat()}', flush=True)
    while not stop.is_set():
        due = next_run(datetime.now(UTC), minute)
        if due >= end:
            print('collection_window_complete', flush=True)
            return
        print(f'next_run_utc={due.isoformat()}', flush=True)
        while datetime.now(UTC) < due:
            if stop.wait(min(30, max(0, (due-datetime.now(UTC)).total_seconds()))):
                return
        job()
