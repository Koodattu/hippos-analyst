"""Read-only, loopback-only browser for the local archive. No upstream requests."""

import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import api

WEB = Path(__file__).with_name("web")
ASSETS = {"/": ("index.html", "text/html"), "/app.mjs": ("app.mjs", "text/javascript"),
          "/model.mjs": ("model.mjs", "text/javascript"), "/styles.css": ("styles.css", "text/css"),
          "/saved.mjs": ("saved.mjs", "text/javascript"),
          "/locales/fi.mjs": ("locales/fi.mjs", "text/javascript")}


class Archive:
    def __init__(self, db):
        self.db = db
        self.heads = {}

    def head(self, path):
        if path not in self.heads:
            row = self.db.execute("""SELECT s.body, r.finished_at FROM requests r
                JOIN snapshots s ON s.id=r.snapshot_id WHERE r.path=? AND r.outcome='ok'
                ORDER BY r.id DESC LIMIT 1""", (path,)).fetchone()
            self.heads[path] = None if row is None else (json.loads(row[0]), row[1])
        return self.heads[path]

    def visible_meeting(self, day, track):
        head = self.head(api.calendar_path(day))
        return head is not None and any(str(r["trackCode"]) == track for r in head[0])

    def visible_race(self, day, track, number):
        head = self.head(api.races_path(day, track))
        return self.visible_meeting(day, track) and head is not None and any(
            str(r["startNumber"]) == number for r in head[0])

    def meeting_record(self, row):
        result = dict(row)
        result["data"] = json.loads(result["data"])
        races = self.race_list(row["date"], row["track"])
        result["races"] = races
        result["race_count"] = len(races)
        result["collected_races"] = sum(r["field_fetched_at"] is not None for r in races)
        result["races_fetched_at"] = (self.head(api.races_path(row["date"], row["track"])) or (None, None))[1]
        return result

    def race_list(self, day, track):
        head = self.head(api.races_path(day, track))
        numbers = {str(r["startNumber"]) for r in head[0]} if head else set()
        result = []
        for row in self.db.execute("SELECT * FROM races WHERE date=? AND track=? ORDER BY CAST(number AS INTEGER),number", (day, track)):
            if row["number"] not in numbers:
                continue
            race = dict(row)
            race["data"] = json.loads(race["data"])
            field = self.head(api.runners_path(day, track, row["number"]))
            race["field_fetched_at"] = field[1] if field else None
            race["entry_count"] = len(field[0]) if field else None
            # A date or opaque status code is not evidence of a published result.
            race["has_results"] = bool(field and any(
                str(r.get("placing") or "").strip() not in ("", "0") and not r.get("absent")
                for r in field[0]))
            result.append(race)
        return result

    def meeting_rows(self, start='0001-01-01', end='9999-12-31', track=''):
        query = 'SELECT * FROM meetings WHERE date BETWEEN ? AND ?'
        params = [start, end]
        if track:
            query += ' AND track=?'
            params.append(track)
        query += ' ORDER BY date,start_time,track'
        return [row for row in self.db.execute(query, params)
                if self.visible_meeting(row['date'], row['track'])]

    def overview(self):
        span = self.db.execute("SELECT min(json_extract(context,'$.date')),max(json_extract(context,'$.date')) FROM jobs WHERE kind='calendar' AND last_success IS NOT NULL").fetchone()
        meetings = self.meeting_rows()
        tracks = {m['track']: json.loads(m['data']).get('formattedTrackName') or m['city'] or m['track'] for m in meetings}
        # Calendar/race-list membership is enough for totals; never load runner fields here.
        races = sum(len((self.head(api.races_path(m['date'], m['track'])) or ([], None))[0]) for m in meetings)
        return {"meeting_count": len(meetings), "race_count": races,
                "horse_count": self.db.execute("SELECT count(*) FROM horses").fetchone()[0],
                "first_date": span[0], "last_date": span[1], "tracks": tracks,
                "last_fetched_at": self.db.execute("SELECT max(finished_at) FROM requests WHERE outcome='ok'").fetchone()[0],
                "pending": self.db.execute("SELECT count(*) FROM jobs WHERE status='pending'").fetchone()[0],
                "failed": self.db.execute("SELECT count(*) FROM jobs WHERE status='failed'").fetchone()[0],
                "paused": bool(self.db.execute("SELECT paused_reason FROM control WHERE id=1").fetchone()[0]),
                "now": datetime.now(timezone.utc).isoformat()}

    def calendar(self, start, end, track="", offset=0):
        if start > end or not 0 <= offset <= 10_000_000:
            raise ValueError("Invalid date range")
        days = [dict(row) for row in self.db.execute("""SELECT json_extract(context,'$.date') AS date,
            last_success AS fetched_at,status FROM jobs WHERE kind='calendar'
            AND json_extract(context,'$.date') BETWEEN ? AND ? ORDER BY date""", (start, end))]
        rows = self.meeting_rows(start, end, track)
        limit = 30
        # Reconcile removed meetings before paging; expand fields only for this page.
        offset = min(offset, max(0, (len(rows) - 1) // limit * limit))
        return {"meetings": [self.meeting_record(row) for row in rows[offset:offset + limit]],
                "days": days, "total": len(rows), "offset": offset, "limit": limit}

    def coverage(self, offset=0):
        if not 0 <= offset <= 10_000_000:
            raise ValueError("Invalid page")
        total = self.db.execute("SELECT count(*) FROM jobs WHERE kind='calendar'").fetchone()[0]
        limit = 30
        offset = min(offset, max(0, (total - 1) // limit * limit))
        rows = self.db.execute("""SELECT json_extract(context,'$.date') AS date,
            last_success AS fetched_at,status FROM jobs WHERE kind='calendar'
            ORDER BY date DESC LIMIT ? OFFSET ?""", (limit, offset)).fetchall()
        days = []
        for row in rows:
            day = dict(row)
            meetings = (self.head(api.calendar_path(day['date'])) or ([], None))[0]
            day.update(meetings=len(meetings), races=0, fields=0, missing_lists=0)
            for meeting in meetings:
                track = str(meeting['trackCode'])
                races = self.head(api.races_path(day['date'], track))
                if races is None:
                    day['missing_lists'] += 1
                    continue
                day['races'] += len(races[0])
                for race in races[0]:
                    path = api.runners_path(day['date'], track, str(race['startNumber']))
                    day['fields'] += self.db.execute("SELECT 1 FROM requests WHERE path=? AND outcome='ok' LIMIT 1", (path,)).fetchone() is not None
            days.append(day)
        return {'days': days, 'total': total, 'offset': offset, 'limit': limit}

    def meeting(self, day, track):
        rows = self.meeting_rows(day, day, track)
        if not rows:
            raise LookupError("Meeting not found")
        meeting = self.meeting_record(rows[0])
        return {"meeting": meeting, "races": meeting["races"]}

    def race(self, day, track, number):
        meeting = self.meeting(day, track)
        race = next((r for r in meeting["races"] if r["number"] == number), None)
        if race is None:
            raise LookupError("Race not found")
        entries = [json.loads(row[0]) for row in self.db.execute("SELECT data FROM entries WHERE date=? AND track=? AND race_number=? ORDER BY CAST(program_number AS INTEGER),program_number", (day, track, number))]
        form = {entry['horseId']: self.horse_starts(entry['horseId'], before=day, limit=5)
                for entry in entries}
        return {**meeting, "race": race, "entries": entries, "form": form}

    def horses(self, query, offset):
        # Python casefold handles Finnish letters; SQLite's built-in LIKE does not.
        self.db.create_function("casefold", 1, lambda s: s.casefold() if s else "", deterministic=True)
        where = "WHERE instr(casefold(name),?) > 0"
        term = query.strip().casefold()
        count = self.db.execute(f"SELECT count(*) FROM horses {where}", (term,)).fetchone()[0]
        rows = self.db.execute(f"SELECT * FROM horses {where} ORDER BY casefold(name),id LIMIT 30 OFFSET ?", (term, offset))
        return {"horses": [dict(row) for row in rows], "total": count, "offset": offset, "limit": 30}

    def horse(self, horse_id):
        row = self.db.execute("SELECT * FROM horses WHERE id=?", (horse_id,)).fetchone()
        if row is None:
            raise LookupError("Horse not found")
        return {"horse": dict(row), "starts": self.horse_starts(horse_id)}

    def saved(self, ids, start):
        if len(ids) > 100 or any(not value.isascii() or not value.isdigit() or len(value) > 30 for value in ids):
            raise ValueError("Invalid saved horses")
        horses, missing = [], []
        for horse_id in dict.fromkeys(ids):
            row = self.db.execute("SELECT * FROM horses WHERE id=?", (horse_id,)).fetchone()
            if row is None:
                missing.append(horse_id)
            else:
                horses.append({"horse": dict(row), "starts": self.horse_starts(horse_id, after=start)})
        return {"horses": horses, "missing": missing}

    def horse_starts(self, horse_id, before=None, limit=None, after=None):
        starts = []
        query = "SELECT e.*,m.city,m.data AS meeting_data FROM entries e JOIN meetings m ON m.date=e.date AND m.track=e.track WHERE horse_id=?"
        params = [horse_id]
        if before:
            query += ' AND e.date<?'
            params.append(before)
        if after:
            query += ' AND e.date>=?'
            params.append(after)
        query += ' ORDER BY e.date DESC,CAST(e.race_number AS INTEGER) DESC,e.track'
        for entry in self.db.execute(query, params):
            if not self.visible_race(entry["date"], entry["track"], entry["race_number"]):
                continue
            item = dict(entry)
            item["data"] = json.loads(item["data"])
            item["meeting_data"] = json.loads(item["meeting_data"])
            starts.append(item)
            if limit is not None and len(starts) >= limit:
                break
        return starts


def required(params, key):
    value = params.get(key, [""])[0]
    if not value or len(value) > 200:
        raise ValueError(f"Missing or invalid {key}")
    return value


def endpoint(archive, path, params):
    if path == "/api/overview":
        return archive.overview()
    if path == "/api/coverage":
        return archive.coverage(int(params.get('offset', ['0'])[0]))
    if path == "/api/calendar":
        return archive.calendar(api.iso_date(required(params, "from")), api.iso_date(required(params, "to")),
                                params.get("track", [""])[0], int(params.get("offset", ["0"])[0]))
    if path in ("/api/meeting", "/api/race"):
        day, track = api.iso_date(required(params, "date")), required(params, "track")
        if path == "/api/meeting":
            return archive.meeting(day, track)
        return archive.race(day, track, required(params, "number"))
    if path == "/api/horses":
        offset = int(params.get("offset", ["0"])[0])
        query = params.get("q", [""])[0]
        if not 0 <= offset <= 10_000_000 or len(query) > 200:
            raise ValueError("Invalid search")
        return archive.horses(query, offset)
    if path == "/api/horse":
        return archive.horse(required(params, "id"))
    if path == "/api/saved":
        ids = params.get("ids", [""])[0]
        return archive.saved(ids.split(',') if ids else [], api.iso_date(required(params, "from")))
    raise LookupError("Not found")


def make_server(db_path, port=8765):
    db_uri = Path(db_path).resolve().as_uri() + "?mode=ro"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            address = urlsplit(self.path)
            if self.headers.get("Host", "").split(":")[0] not in ("localhost", "127.0.0.1"):
                self.respond(403, b'{"error":"forbidden"}', "application/json")
                return
            if address.path.startswith("/api/"):
                try:
                    db = sqlite3.connect(db_uri, uri=True, timeout=10)
                    db.row_factory = sqlite3.Row
                    try:
                        db.execute("BEGIN")  # One consistent snapshot during collection.
                        result = endpoint(Archive(db), address.path, parse_qs(address.query))
                    finally:
                        db.close()
                    self.respond(200, json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json")
                except ValueError:
                    self.respond(400, b'{"error":"invalid_request"}', "application/json")
                except LookupError:
                    self.respond(404, b'{"error":"not_found"}', "application/json")
                except sqlite3.Error:
                    self.respond(503, b'{"error":"database_unavailable"}', "application/json")
            elif address.path in ASSETS:
                filename, content_type = ASSETS[address.path]
                self.respond(200, (WEB / filename).read_bytes(), content_type)
            else:
                self.respond(404, b"Not found", "text/plain")

        def respond(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(db_path, port):
    with make_server(db_path, port) as server:
        print(f"Local UI: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
        server.serve_forever()
