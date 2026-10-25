"""SQLite queue, minimized response snapshots and current racing records."""

import hashlib
import json
import sqlite3
from pathlib import Path

from .api import races_path, runners_path, profile_path, horse_id


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
        CREATE TABLE IF NOT EXISTS toto_targets (
            date TEXT NOT NULL, track TEXT NOT NULL, number TEXT NOT NULL,
            card_id TEXT, race_id TEXT UNIQUE, scheduled_start REAL, race_status TEXT,
            match_status TEXT NOT NULL DEFAULT 'pending', runners TEXT, runners_at REAL,
            pool_id TEXT, note TEXT,
            PRIMARY KEY(date,track,number),
            FOREIGN KEY(date,track,number) REFERENCES races(date,track,number)
        );
        CREATE TABLE IF NOT EXISTS toto_observations (
            request_id INTEGER PRIMARY KEY REFERENCES requests(id),
            race_id TEXT NOT NULL REFERENCES toto_targets(race_id), pool_id TEXT NOT NULL,
            observed_at REAL NOT NULL, scheduled_start REAL NOT NULL,
            phase TEXT NOT NULL, body TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS toto_observations_race ON toto_observations(race_id,observed_at DESC);
        CREATE TABLE IF NOT EXISTS horse_profiles (
            horse_id TEXT PRIMARY KEY REFERENCES horses(id), data TEXT NOT NULL, fetched_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS horse_parties (
            horse_id TEXT NOT NULL REFERENCES horse_profiles(horse_id),
            role TEXT NOT NULL CHECK(role IN ('owner','breeder')), label TEXT NOT NULL,
            party_key TEXT NOT NULL, PRIMARY KEY(horse_id,role)
        );
        CREATE INDEX IF NOT EXISTS parties_lookup ON horse_parties(role,party_key,horse_id);
        CREATE TABLE IF NOT EXISTS horse_parents (
            horse_id TEXT NOT NULL REFERENCES horse_profiles(horse_id),
            role TEXT NOT NULL CHECK(role IN ('sire','dam')), parent_id TEXT REFERENCES horses(id),
            name TEXT, PRIMARY KEY(horse_id,role)
        );
        CREATE INDEX IF NOT EXISTS parents_lookup ON horse_parents(parent_id,horse_id);
        CREATE TABLE IF NOT EXISTS maintenance_state (
            name TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tracks (
            id TEXT PRIMARY KEY, hippos_code TEXT NOT NULL UNIQUE,
            data TEXT NOT NULL, fetched_at REAL
        );
        CREATE TABLE IF NOT EXISTS photo_assets (
            sha256 TEXT PRIMARY KEY, image BLOB NOT NULL,
            width INTEGER NOT NULL, height INTEGER NOT NULL, metadata TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profile_photos (
            kind TEXT NOT NULL CHECK(kind IN ('horse','driver','trainer')), entity_id TEXT NOT NULL,
            asset_hash TEXT NOT NULL REFERENCES photo_assets(sha256),
            expected_name TEXT NOT NULL, identity_note TEXT NOT NULL,
            PRIMARY KEY(kind,entity_id)
        );
        PRAGMA user_version = 1;
    """)
    from . import tracks
    tracks.initialize(db)
    return db


def enqueue(db, path, kind, context, priority=100, refresh=False):
    cursor = db.execute(
        "INSERT OR IGNORE INTO jobs(path,kind,context,priority) VALUES(?,?,?,?)",
        (path, kind, encode(context), priority),
    )
    added = cursor.rowcount
    if refresh:
        added += db.execute(
            "UPDATE jobs SET status='pending',next_attempt=0,last_error=NULL,priority=?,context=? "
            "WHERE path=? AND status='done'", (priority, encode(context), path),
        ).rowcount
    # Failed jobs require deliberate diagnosis instead of silently being retried.
    return added


def enqueue_refresh(db, path, kind, context, priority, now, interval=86400):
    """Refresh stale successful jobs; preserve pending cooldowns and failed jobs."""
    context = {**context, 'refresh_after': interval}
    job = db.execute('SELECT status,last_success FROM jobs WHERE path=?', (path,)).fetchone()
    if job and job['status'] == 'pending':
        db.execute('UPDATE jobs SET context=?,priority=min(priority,?) WHERE path=?',
                   (encode(context), priority, path))
        return 0
    if job and (job['status'] == 'failed' or (job['last_success'] is not None and job['last_success'] > now-interval)):
        return 0
    return enqueue(db, path, kind, context, priority, True)


def save_response(db, job, records, request_id, now):
    """Called inside a transaction: archive, materialize and discover together."""
    body = encode(records)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    db.execute("INSERT OR IGNORE INTO snapshots(path,sha256,first_seen,body) VALUES(?,?,?,?)",
               (job["path"], digest, now, body))
    snapshot_id = db.execute("SELECT id FROM snapshots WHERE path=? AND sha256=?",
                             (job["path"], digest)).fetchone()[0]
    context = json.loads(job["context"])
    if job['kind'].startswith('toto_'):
        from . import toto
        toto.save_response(db, job, records, request_id, now)
    day = context.get("date")
    def discover(path, kind, child_context):
        if context.get('refresh_after'):
            return enqueue_refresh(db, path, kind, child_context, job['priority'], now, context['refresh_after'])
        return enqueue(db, path, kind, child_context, job['priority'], True)
    for record in records:
        data = encode(record)
        if job["kind"] == "calendar":
            track = record["trackCode"]
            from .tracks import observe
            observe(db, record, now)
            db.execute("""INSERT INTO meetings VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(date,track) DO UPDATE SET name=excluded.name,start_time=excluded.start_time,
                city=excluded.city,canceled=excluded.canceled,data=excluded.data,fetched_at=excluded.fetched_at""",
                (day, track, record.get("name"), record.get("startTime"), record.get("trackCity"),
                 record.get("canceled"), data, now))
            discover(races_path(day, track), "races", {"date": day, "track": track})
        elif job["kind"] == "races":
            track, number = context["track"], record["startNumber"]
            db.execute("""INSERT INTO races VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(date,track,number) DO UPDATE SET breed=excluded.breed,start_form=excluded.start_form,
                distance=excluded.distance,data=excluded.data,fetched_at=excluded.fetched_at""",
                (day, track, number, record.get("eventType"), record.get("startForm"),
                 record.get("baseDistance"), data, now))
            discover(runners_path(day, track, number), "runners",
                     {"date": day, "track": track, "number": number})
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
    if job['kind'] == 'profile':
        record = records[0]
        db.execute("""INSERT INTO horses VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,breed=coalesce(excluded.breed,horses.breed),
            country=coalesce(excluded.country,horses.country),fetched_at=excluded.fetched_at""",
            (record['id'], record['name'], record.get('breedCode'), record.get('registrationCountry'), now))
        db.execute('INSERT INTO horse_profiles VALUES(?,?,?) ON CONFLICT(horse_id) DO UPDATE SET data=excluded.data,fetched_at=excluded.fetched_at',
                   (record['id'], encode(record), now))
        db.execute('DELETE FROM horse_parties WHERE horse_id=?', (record['id'],))
        for role in ('owner', 'breeder'):
            label = record.get(role + 'Name')
            if label:
                key = hashlib.sha256(label.encode('utf-8')).hexdigest()
                db.execute('INSERT INTO horse_parties VALUES(?,?,?,?)', (record['id'], role, label, key))
        db.execute('DELETE FROM horse_parents WHERE horse_id=?', (record['id'],))
        for role in ('sire', 'dam'):
            parent = record.get(role)
            if not parent:
                continue
            if parent['id']:
                db.execute('INSERT OR IGNORE INTO horses VALUES(?,?,NULL,NULL,?)', (parent['id'], parent['name'] or parent['id'], now))
            db.execute('INSERT INTO horse_parents VALUES(?,?,?,?)', (record['id'], role, parent['id'], parent['name']))
        discover_parents(db, record['id'], context.get('remaining', 0), job['priority'])
    db.execute("UPDATE requests SET outcome='ok',snapshot_id=?,finished_at=? WHERE id=?",
               (snapshot_id, now, request_id))
    db.execute("UPDATE jobs SET status='done',last_success=?,last_error=NULL,next_attempt=0 WHERE path=?",
               (now, job["path"]))
    db.execute("UPDATE control SET consecutive_failures=0 WHERE id=1")


def status(db):
    from . import toto
    return {
        "toto": toto.coverage(db),
        "control": dict(db.execute("SELECT * FROM control").fetchone()),
        "jobs": {row[0]: row[1] for row in db.execute("SELECT status,count(*) FROM jobs GROUP BY status")},
        "counts": {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                   for table in ("meetings", "races", "entries", "horses", "snapshots", "requests", "horse_profiles", "horse_parties", "horse_parents")},
        "failed_jobs": [dict(row) for row in db.execute(
            "SELECT path,last_error FROM jobs WHERE status='failed' ORDER BY path LIMIT 20")],
    }


def enqueue_profile(db, value, remaining=2, priority=110, refresh=False):
    value = horse_id(value)
    if not 0 <= remaining <= 2:
        raise ValueError('Collect at most two ancestor generations per root')
    path = profile_path(value)
    added = enqueue(db, path, 'profile', {'id': value, 'remaining': remaining}, priority, refresh)
    existing = db.execute('SELECT context,status FROM jobs WHERE path=?', (path,)).fetchone()
    context = json.loads(existing['context'])
    if remaining > context.get('remaining', 0):
        context['remaining'] = remaining
        db.execute('UPDATE jobs SET context=? WHERE path=?', (encode(context), path))
    # Already collected ancestors can be reused without requesting their profile again.
    # Remaining depth strictly decreases, so shared ancestors and cycles terminate.
    if existing['status'] == 'done':
        added += discover_parents(db, value, remaining, priority)
    return added


def discover_parents(db, value, remaining, priority):
    if remaining <= 0:
        return 0
    return sum(enqueue_profile(db, row[0], remaining - 1, priority)
               for row in db.execute('SELECT parent_id FROM horse_parents WHERE horse_id=? AND parent_id IS NOT NULL', (value,)).fetchall())


def seed_profiles(db, limit=10, generations=2, priority=110):
    if not 1 <= limit <= 100 or not 0 <= generations <= 2:
        raise ValueError('Use 1–100 roots and 0–2 ancestor generations')
    # Only race participants seed new roots; ancestor stubs never grow an unbounded tree.
    roots = db.execute("""SELECT e.horse_id FROM entries e
        WHERE NOT EXISTS (SELECT 1 FROM jobs j WHERE j.path='/horse/'||e.horse_id)
        GROUP BY e.horse_id ORDER BY max(e.date) DESC,e.horse_id LIMIT ?""", (limit,)).fetchall()
    return sum(enqueue_profile(db, row[0], generations, priority) for row in roots)
