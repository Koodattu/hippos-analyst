"""Run from the repository with: python -m hippos_analyst --help."""

import argparse
import json
import sqlite3
import sys
import time
from datetime import date, timedelta

from . import api, collector, store, toto


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
    maintain = commands.add_parser('maintain', help='Bounded refresh, profile and history maintenance; shared lock and limits')
    maintain.add_argument('--date', required=True, type=api.iso_date, help='Current Europe/Helsinki calendar date')
    maintain.add_argument('--max-requests', type=int, default=40)
    toto_seed = commands.add_parser('seed-toto', help='Opt in to Toto enrichment for 1–3 already collected races; offline')
    toto_seed.add_argument('--date', required=True, type=api.iso_date)
    toto_seed.add_argument('--track', required=True)
    toto_seed.add_argument('--races', required=True, help='Comma-separated race numbers, at most three')
    toto_seed.add_argument('--samples', type=int, default=3)
    toto_seed.add_argument('--interval', type=int, default=1800, help='Seconds between scheduled odds samples; minimum 900')
    toto_run = commands.add_parser('run-toto', help='Run only due Toto jobs, sharing the lock, ledger and stop state')
    toto_run.add_argument('--max-requests', type=int, default=8)
    toto_run.add_argument('--delay', type=float, default=60)
    toto_run.add_argument('--daily-budget', type=int, default=200)
    profiles = commands.add_parser('seed-profiles', help='Queue a bounded set of known horses and ancestors; offline')
    profiles.add_argument('--id', help='One exact horse ID already present in this archive')
    profiles.add_argument('--limit', type=int, default=10)
    profiles.add_argument('--generations', type=int, default=2)
    profiles.add_argument('--priority', type=int, default=110)
    profiles.add_argument('--refresh', action='store_true', help='Refresh the explicitly selected horse profile')
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
    photo = commands.add_parser('import-commons-photo', help='Import one identity-reviewed, CC-licensed Commons JPEG')
    photo.add_argument('--kind', required=True, choices=('horse', 'driver', 'trainer'))
    photo.add_argument('--id', required=True, help='Exact ID in this archive')
    photo.add_argument('--name', required=True, help='Expected name displayed by this archive (must match)')
    photo.add_argument('--file', required=True, help='Exact Wikimedia Commons File: title')
    photo.add_argument('--identity-note', required=True, help='Evidence that the pictured subject matches this ID')
    photo.add_argument('--replace', action='store_true', help='Intentionally replace the photo on this profile')
    remove_photo = commands.add_parser('remove-photo', help='Remove a profile photo locally; no network requests')
    remove_photo.add_argument('--kind', required=True, choices=('horse', 'driver', 'trainer'))
    remove_photo.add_argument('--id', required=True)
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
        elif args.command == 'seed-profiles':
            with db:
                if args.id:
                    if not db.execute('SELECT 1 FROM horses WHERE id=?', (args.id,)).fetchone():
                        raise ValueError('Select a horse already in the archive')
                    count = store.enqueue_profile(db, args.id, args.generations, args.priority, args.refresh)
                else:
                    if args.refresh:
                        raise ValueError('Profile refresh requires --id')
                    count = store.seed_profiles(db, args.limit, args.generations, args.priority)
            print(f'Queued {count} profile jobs. No requests sent.')
        elif args.command == 'seed-toto':
            with db:
                count = toto.seed(db, args.date, args.track, args.races.split(','), args.samples, args.interval)
            print(f'Queued {count} Toto meeting seeds. No requests sent.')
        elif args.command == 'maintain':
            from . import maintenance
            with collector.worker_lock(args.db):
                outcome = maintenance.run(db,args.date,max_requests=args.max_requests)
            return 2 if outcome in ('paused','retry','failed') else 0
        elif args.command in ('run', 'run-toto'):
            with collector.worker_lock(args.db):
                outcome = collector.run(db, max_requests=args.max_requests, delay=args.delay, daily_budget=args.daily_budget,
                                        provider='toto' if args.command == 'run-toto' else 'hippos')
            return 2 if outcome in ("paused", "retry", "failed") else 0
        elif args.command == "status":
            display(store.status(db))
        elif args.command == 'import-commons-photo':
            from . import photos
            with collector.worker_lock(args.db):
                display(photos.import_commons(db, args.kind, args.id, args.name, args.file,
                                             args.identity_note, args.replace))
        elif args.command == 'remove-photo':
            from . import photos
            with collector.worker_lock(args.db):
                print(f'Removed {photos.remove(db, args.kind, args.id)} photo assignment(s).')
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
