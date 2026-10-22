"""SQLite queue, minimized response snapshots and current racing records."""

import hashlib
import json
import sqlite3
from pathlib import Path

from .api import races_path, runners_path


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, 1):
        db.close()
        raise ValueError(f"Unsupported database version: {version}")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS control (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            paused_reason TEXT, paused_until REAL NOT NULL DEFAULT 0,
            last_request_at REAL NOT NULL DEFAULT 0,
            consecutive_failures INTEGER NOT NULL DEFAULT 0
        );
        INSERT OR IGNORE INTO control(id) VALUES (1);
        CREATE TABLE IF NOT EXISTS jobs (
            path TEXT PRIMARY KEY, kind TEXT NOT NULL, context TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','done','failed')),
            priority INTEGER NOT NULL DEFAULT 100, attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt REAL NOT NULL DEFAULT 0, last_error TEXT, last_success REAL
        );
        CREATE INDEX IF NOT EXISTS jobs_due ON jobs(status, next_attempt, priority);
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY, path TEXT NOT NULL, sha256 TEXT NOT NULL,
            first_seen REAL NOT NULL, body TEXT NOT NULL, parser_version INTEGER NOT NULL DEFAULT 1,
            UNIQUE(path, sha256)
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY, path TEXT NOT NULL, started_at REAL NOT NULL,
            finished_at REAL, status INTEGER, outcome TEXT NOT NULL DEFAULT 'interrupted',
            snapshot_id INTEGER REFERENCES snapshots(id)
        );
        CREATE INDEX IF NOT EXISTS requests_time ON requests(started_at);
        CREATE INDEX IF NOT EXISTS requests_path_success ON requests(path, id DESC) WHERE outcome='ok';
        CREATE TABLE IF NOT EXISTS meetings (
            date TEXT NOT NULL, track TEXT NOT NULL, name TEXT, start_time TEXT, city TEXT,
            canceled INTEGER, data TEXT NOT NULL, fetched_at REAL NOT NULL,
            PRIMARY KEY(date, track)
        );
        CREATE TABLE IF NOT EXISTS races (
            date TEXT NOT NULL, track TEXT NOT NULL, number TEXT NOT NULL,
            breed TEXT, start_form TEXT, distance TEXT, data TEXT NOT NULL, fetched_at REAL NOT NULL,
            PRIMARY KEY(date, track, number),
            FOREIGN KEY(date, track) REFERENCES meetings(date, track)
        );
        CREATE TABLE IF NOT EXISTS horses (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, breed TEXT, country TEXT, fetched_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS horses_name ON horses(name);
        CREATE TABLE IF NOT EXISTS entries (
            date TEXT NOT NULL, track TEXT NOT NULL, race_number TEXT NOT NULL,
            program_number TEXT NOT NULL, horse_id TEXT NOT NULL REFERENCES horses(id),
            placing TEXT, kilometer_time TEXT, prize TEXT, absent INTEGER,
            data TEXT NOT NULL, fetched_at REAL NOT NULL,
            PRIMARY KEY(date, track, race_number, program_number),
            FOREIGN KEY(date, track, race_number) REFERENCES races(date, track, number)
        );
        CREATE INDEX IF NOT EXISTS entries_horse ON entries(horse_id, date);
        PRAGMA user_version = 1;
    """)
    return db


def enqueue(db, path, kind, context, priority=100, refresh=False):
    cursor = db.execute(
        "INSERT OR IGNORE INTO jobs(path,kind,context,priority) VALUES(?,?,?,?)",
        (path, kind, encode(context), priority),
    )
    added = cursor.rowcount
    if refresh:
        added += db.execute(
            "UPDATE jobs SET status='pending',next_attempt=0,last_error=NULL,priority=? "
            "WHERE path=? AND status='done'", (priority, path),
        ).rowcount
    # Failed jobs require deliberate diagnosis instead of silently being retried.
    return added


def save_response(db, job, records, request_id, now):
    """Called inside a transaction: archive, materialize and discover together."""
    body = encode(records)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    db.execute("INSERT OR IGNORE INTO snapshots(path,sha256,first_seen,body) VALUES(?,?,?,?)",
               (job["path"], digest, now, body))
    snapshot_id = db.execute("SELECT id FROM snapshots WHERE path=? AND sha256=?",
                             (job["path"], digest)).fetchone()[0]
    context = json.loads(job["context"])
    day = context["date"]
    for record in records:
        data = encode(record)
        if job["kind"] == "calendar":
            track = record["trackCode"]
            db.execute("""INSERT INTO meetings VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(date,track) DO UPDATE SET name=excluded.name,start_time=excluded.start_time,
                city=excluded.city,canceled=excluded.canceled,data=excluded.data,fetched_at=excluded.fetched_at""",
                (day, track, record.get("name"), record.get("startTime"), record.get("trackCity"),
                 record.get("canceled"), data, now))
            enqueue(db, races_path(day, track), "races", {"date": day, "track": track}, job["priority"], True)
        elif job["kind"] == "races":
            track, number = context["track"], record["startNumber"]
            db.execute("""INSERT INTO races VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(date,track,number) DO UPDATE SET breed=excluded.breed,start_form=excluded.start_form,
                distance=excluded.distance,data=excluded.data,fetched_at=excluded.fetched_at""",
                (day, track, number, record.get("eventType"), record.get("startForm"),
                 record.get("baseDistance"), data, now))
            enqueue(db, runners_path(day, track, number), "runners",
                    {"date": day, "track": track, "number": number}, job["priority"], True)
    if job["kind"] == "runners":
        # A response is the entire current field. Historical versions remain in snapshots.
        db.execute("DELETE FROM entries WHERE date=? AND track=? AND race_number=?",
                   (day, context["track"], context["number"]))
        for record in records:
            db.execute("""INSERT INTO horses VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,breed=excluded.breed,country=excluded.country,fetched_at=excluded.fetched_at""",
                (record["horseId"], record["horseName"], record.get("horseBreed"),
                 record.get("horseRegistrationCountry"), now))
            db.execute("INSERT INTO entries VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (day, context["track"], context["number"], record["programNumber"], record["horseId"],
                 record.get("placing"), record.get("kilometerTime"), record.get("price"),
                 record.get("absent"), encode(record), now))
    db.execute("UPDATE requests SET outcome='ok',snapshot_id=?,finished_at=? WHERE id=?",
               (snapshot_id, now, request_id))
    db.execute("UPDATE jobs SET status='done',last_success=?,last_error=NULL,next_attempt=0 WHERE path=?",
               (now, job["path"]))
    db.execute("UPDATE control SET consecutive_failures=0 WHERE id=1")


def status(db):
    return {
        "control": dict(db.execute("SELECT * FROM control").fetchone()),
        "jobs": {row[0]: row[1] for row in db.execute("SELECT status,count(*) FROM jobs GROUP BY status")},
        "counts": {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                   for table in ("meetings", "races", "entries", "horses", "snapshots", "requests")},
        "failed_jobs": [dict(row) for row in db.execute(
            "SELECT path,last_error FROM jobs WHERE status='failed' ORDER BY path LIMIT 20")],
    }
