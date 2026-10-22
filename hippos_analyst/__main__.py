"""Run from the repository with: python -m hippos_analyst --help."""

import argparse
import json
import sqlite3
import sys
import time
from datetime import date, timedelta

from . import api, collector, store


def parser():
    root = argparse.ArgumentParser(description="Private Hippos research collector and local data browser")
    root.add_argument("--db", default="data/hippos.sqlite3", help="Local SQLite path (default: data/hippos.sqlite3)")
    commands = root.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed", help="Queue daily Finnish calendars; makes no network requests")
    seed.add_argument("--from", dest="start", required=True, type=api.iso_date)
    seed.add_argument("--to", dest="end", required=True, type=api.iso_date)
    seed.add_argument("--refresh", action="store_true", help="Requeue completed calendars and their discovered descendants")
    seed.add_argument("--priority", type=int, default=100, help="Lower numbers run first; use 10 for current data")
    worker = commands.add_parser("run", help="Process a bounded number of due jobs")
    worker.add_argument("--max-requests", type=int, default=25)
    worker.add_argument("--delay", type=float, default=15)
    worker.add_argument("--daily-budget", type=int, default=500)
    commands.add_parser("status", help="Show stored counts, queue and persistent stop state")
    stop = commands.add_parser("pause", help="Persistently stop further collection")
    stop.add_argument("--reason", default="Stopped by operator")
    commands.add_parser("resume", help="Clear a stop after investigating; respects Retry-After")
    retry = commands.add_parser("retry", help="Requeue one failed path after fixing its cause")
    retry.add_argument("path")
    calendar = commands.add_parser("calendar", help="Read locally stored meetings; no network")
    calendar.add_argument("--from", dest="start", required=True, type=api.iso_date)
    calendar.add_argument("--to", dest="end", required=True, type=api.iso_date)
    race = commands.add_parser("race", help="Read a locally stored race and its participants; no network")
    race.add_argument("--date", required=True, type=api.iso_date)
    race.add_argument("--track", required=True)
    race.add_argument("--number", required=True)
    web = commands.add_parser("serve", help="Open a read-only local web UI; no upstream requests")
    web.add_argument("--port", type=int, default=8765)
    return root


def display(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv=None):
    args = parser().parse_args(argv)
    db = None
    try:
        db = store.connect(args.db)
        if args.command == "serve":
            from .server import serve
            if not 1 <= args.port <= 65535:
                raise ValueError("Port must be between 1 and 65535")
            db.close()
            db = None
            serve(args.db, args.port)
        elif args.command == "seed":
            start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
            if end < start or (end - start).days >= 366:
                raise ValueError("Queue 1–366 days at a time, with --from <= --to")
            count = 0
            with db:
                for offset in range((end - start).days + 1):
                    day = (start + timedelta(days=offset)).isoformat()
                    count += store.enqueue(db, api.calendar_path(day), "calendar", {"date": day}, args.priority, args.refresh)
            print(f"Queued {count} calendars. No requests sent.")
        elif args.command == "run":
            with collector.worker_lock(args.db):
                outcome = collector.run(db, max_requests=args.max_requests, delay=args.delay, daily_budget=args.daily_budget)
            return 2 if outcome in ("paused", "retry", "failed") else 0
        elif args.command == "status":
            display(store.status(db))
        elif args.command == "pause":
            with db:
                collector.pause(db, args.reason)
            print("Collection paused. An in-flight request may finish; no subsequent request will start.")
        elif args.command == "resume":
            state = db.execute("SELECT * FROM control").fetchone()
            if state["paused_until"] > time.time():
                raise ValueError("The server's retry/cooldown period has not elapsed")
            with db:
                db.execute("UPDATE control SET paused_reason=NULL,paused_until=0,consecutive_failures=0 WHERE id=1")
            print("Stop cleared. Failed jobs remain failed until explicitly retried.")
        elif args.command == "retry":
            with db:
                changed = db.execute("UPDATE jobs SET status='pending',next_attempt=0,last_error=NULL WHERE path=? AND status='failed'", (args.path,)).rowcount
            print(f"Requeued {changed} failed jobs. Pause state unchanged.")
        elif args.command == "calendar":
            display([dict(row) for row in db.execute("SELECT date,track,name,start_time,city,canceled,fetched_at FROM meetings WHERE date BETWEEN ? AND ? ORDER BY date,track", (args.start, args.end))])
        elif args.command == "race":
            race = db.execute("SELECT data,fetched_at FROM races WHERE date=? AND track=? AND number=?", (args.date, args.track, args.number)).fetchone()
            if race is None:
                raise ValueError("Race is not in the local database")
            entries = db.execute("SELECT data,fetched_at FROM entries WHERE date=? AND track=? AND race_number=? ORDER BY CAST(program_number AS INTEGER)", (args.date, args.track, args.number))
            display({"race": json.loads(race[0]), "fetched_at": race[1],
                     "entries": [{"data": json.loads(row[0]), "fetched_at": row[1]} for row in entries]})
        return 0
    except KeyboardInterrupt:
        message = "Local UI stopped." if args.command == "serve" else "Stopped. Queue is saved; an interrupted request will be retried on a later run."
        print(message, file=sys.stderr)
        return 130
    except (ValueError, RuntimeError, sqlite3.Error, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    # Windows pipes otherwise use the local code page, corrupting Finnish JSON.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
