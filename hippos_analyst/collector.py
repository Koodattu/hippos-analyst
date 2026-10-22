"""Bounded, single-worker collection with persistent rate limits and stops."""

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from . import api, store


@contextmanager
def worker_lock(database):
    """OS lock is released even if a process crashes; the file may remain."""
    path = Path(database).with_suffix(".collector.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Another collector is using this database") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def retry_after(headers, now):
    value = (headers or {}).get("retry-after", "")
    try:
        return now + max(0, int(value))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(now, parsed.timestamp())
        except (ValueError, TypeError, OverflowError):
            return now


def pause(db, reason, until=0):
    db.execute("UPDATE control SET paused_reason=?,paused_until=? WHERE id=1", (reason, until))


def run(db, *, max_requests=25, delay=15, daily_budget=500,
        fetch=api.fetch, clock=time.time, sleep=time.sleep, emit=print):
    if not 1 <= max_requests <= 500 or not 1 <= daily_budget <= 500 or not 10 <= delay <= 3600:
        raise ValueError("Use 1–500 requests/budget and a 10–3600 second delay")
    completed = 0
    for _ in range(max_requests):
        control = db.execute("SELECT * FROM control WHERE id=1").fetchone()
        if control["paused_reason"]:
            emit(f"Paused: {control['paused_reason']}")
            return "paused"
        now = clock()
        if control['paused_until'] > now:
            emit('Service cooldown has not elapsed; no request sent.')
            return 'retry'
        job = db.execute("SELECT * FROM jobs WHERE status='pending' AND next_attempt<=? "
                         "ORDER BY priority,date(json_extract(context,'$.date')) DESC,path LIMIT 1", (now,)).fetchone()
        if job is None:
            emit(f"No jobs due; completed {completed} requests in this run.")
            return "idle"
        wait = control["last_request_at"] + delay - now
        # Check for a manual stop frequently while waiting.
        while wait > 0:
            sleep(min(wait, 1))
            if db.execute("SELECT paused_reason FROM control WHERE id=1").fetchone()[0]:
                emit("Paused by operator")
                return "paused"
            wait = control["last_request_at"] + delay - clock()
        now = clock()
        midnight = datetime.fromtimestamp(now, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        with db:
            used = db.execute("SELECT count(*) FROM requests WHERE started_at>=?", (midnight,)).fetchone()[0]
            if used >= daily_budget:
                emit(f"UTC daily budget reached ({used}/{daily_budget}); no request sent.")
                return "budget"
            if db.execute("SELECT paused_reason FROM control WHERE id=1").fetchone()[0]:
                return "paused"
            request_id = db.execute("INSERT INTO requests(path,started_at) VALUES(?,?)", (job["path"], now)).lastrowid
            db.execute("UPDATE jobs SET attempts=attempts+1 WHERE path=?", (job["path"],))
            db.execute("UPDATE control SET last_request_at=? WHERE id=1", (now,))
        emit(f"GET {job['path']} ({used + 1}/{daily_budget} today)")
        try:
            response = fetch(job["path"])
            with db:
                db.execute("UPDATE requests SET status=?,finished_at=? WHERE id=?", (response.status, clock(), request_id))
            if response.status == 200:
                records = api.normalize(job["kind"], response.json(), json.loads(job["context"]))
                with db:
                    store.save_response(db, job, records, request_id, clock())
                completed += 1
                emit(f"Saved {len(records)} {job['kind']} records")
                continue
            now = clock()
            with db:
                db.execute("UPDATE requests SET outcome='http_error' WHERE id=?", (request_id,))
                db.execute("UPDATE jobs SET last_error=? WHERE path=?", (f"HTTP {response.status}", job["path"]))
                if response.status in (401, 403, 429) or 300 <= response.status < 400:
                    pause(db, f"HTTP {response.status}: investigate before resuming", retry_after(response.headers, now))
                    emit(f"Stopped and persistently paused on HTTP {response.status}.")
                    return "paused"
                if response.status in (404, 410):
                    db.execute("UPDATE jobs SET status='failed' WHERE path=?", (job["path"],))
                    emit(f"Missing endpoint ({response.status}); job recorded as failed.")
                    return "failed"
                if response.status == 0 or response.status >= 500 or response.status == 408:
                    failures = db.execute("SELECT consecutive_failures FROM control").fetchone()[0] + 1
                    next_attempt = max(now + min(3600, 60 * 2 ** min(failures - 1, 6)), retry_after(response.headers, now))
                    db.execute("UPDATE jobs SET next_attempt=? WHERE path=?", (next_attempt, job["path"]))
                    db.execute("UPDATE control SET consecutive_failures=?,paused_until=max(paused_until,?) WHERE id=1",
                               (failures, next_attempt))
                    if failures >= 5:
                        pause(db, "Five consecutive transient failures; investigate before resuming", next_attempt)
                    emit("Transient failure; retry recorded for a later run. No further requests this run.")
                    return "retry"
                pause(db, f"Unexpected HTTP {response.status}; investigate before resuming")
                return "paused"
        except (api.SchemaError, ValueError) as exc:
            # Error text is ours; response bodies (including error pages) stay out of logs.
            with db:
                db.execute("UPDATE requests SET outcome='schema_error',finished_at=? WHERE id=?", (clock(), request_id))
                db.execute("UPDATE jobs SET status='failed',last_error=? WHERE path=?", (str(exc), job["path"]))
                pause(db, "Unexpected response schema; inspect failed job before resuming")
            emit(f"Stopped on schema change: {exc}")
            return "paused"
    emit(f"Run limit reached; completed {completed} requests. Remaining work is saved.")
    return "limit"
