"""Read-only browser and WSGI application for the archive. No upstream requests."""

import hashlib
import json
import logging
import os
from contextlib import closing
from http import HTTPStatus
import sqlite3
from datetime import datetime, timezone
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server as make_wsgi_server
from pathlib import Path
from urllib.parse import parse_qs

from . import analytics, api, toto, browse, tracks, photos, prediction_store, prediction_results, race_results
from .person_names import PersonNames, ScopedNames
from . import directory_index

WEB = Path(__file__).with_name("web")
ASSETS = {"/": ("index.html", "text/html"), "/app.mjs": ("app.mjs", "text/javascript"),
          "/model.mjs": ("model.mjs", "text/javascript"), "/styles.css": ("styles.css", "text/css"),
          "/saved.mjs": ("saved.mjs", "text/javascript"),
          "/photos.mjs": ("photos.mjs", "text/javascript"),
          "/track-map.mjs": ("track-map.mjs", "text/javascript"),
          "/locales/fi.mjs": ("locales/fi.mjs", "text/javascript")}
for _photo in ('vermo', 'teivo', 'track-f', 'track-j', 'track-jo', 'track-k', 'track-kt',
               'track-ku', 'track-l', 'track-la', 'track-m', 'track-o', 'track-p',
               'track-s', 'track-tk', 'track-to', 'track-y'):
    ASSETS[f'/images/{_photo}.jpg'] = (f'images/{_photo}.jpg', 'image/jpeg')

class Archive:
    def __init__(self, db, browse_cache=None):
        self.db = db
        race_results.register_sql(db)
        self.browse_cache = browse_cache
        self.heads = {}
        self._person_names = None
        self._scoped_names = None
        self._entry_filter = None

    def entry_filter(self):
        """Exclude retained races removed from the latest source lists during index scans."""
        if self._entry_filter is None:
            self._entry_filter = directory_index.entry_filter(self.db)
        return self._entry_filter

    def photo(self, kind, entity_id):
        return photos.get(self.db, kind, entity_id)

    def person_names(self, *, scoped=False):
        if scoped and self._person_names is None:
            if self._scoped_names is None:
                self._scoped_names = ScopedNames(self.db, self.entry_filter())
            return self._scoped_names
        if self._person_names is None:
            token = (self.db.execute("SELECT max(id) FROM requests WHERE outcome='ok'").fetchone()[0],
                     self.db.total_changes)
            cached = self.browse_cache.get('person_names') if self.browse_cache is not None else None
            if cached and cached[0] == token:
                self._person_names = cached[1]
            else:
                self._person_names = PersonNames.from_archive(self.db, self.entry_filter())
                if self.browse_cache is not None:
                    self.browse_cache['person_names'] = (token, self._person_names)
        return self._person_names

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

    def meeting_record(self, row, compact=False):
        result = dict(row)
        result['track_id'] = tracks.identity(row['track'])
        result["data"] = json.loads(result["data"])
        races = self.race_list(row["date"], row["track"], compact)
        result["races"] = races
        result["race_count"] = len(races)
        result["collected_races"] = sum(r["field_fetched_at"] is not None for r in races)
        result["races_fetched_at"] = (self.head(api.races_path(row["date"], row["track"])) or (None, None))[1]
        return result

    def race_list(self, day, track, compact=False):
        columns = 'r.number' if compact else 'r.*'
        result = []
        for row in self.db.execute(f"""SELECT {columns},f.fetched_at AS field_fetched_at,f.entry_count,f.has_results
                FROM races r LEFT JOIN report_fields f USING(date,track,number)
                WHERE r.date=? AND r.track=? AND NOT EXISTS (SELECT 1 FROM directory_hidden_races h
                    WHERE (h.date,h.track,h.number)=(r.date,r.track,r.number))
                ORDER BY CAST(r.number AS INTEGER),r.number""", (day,track)):
            race = dict(row)
            if not compact:
                race["data"] = json.loads(race["data"])
            race["has_results"] = bool(race["has_results"])
            result.append(race)
        return result

    def meeting_rows(self, start='0001-01-01', end='9999-12-31', track=''):
        query = 'SELECT m.* FROM calendar_tracks c JOIN meetings m USING(date,track) WHERE c.date BETWEEN ? AND ?'
        params = [start, end]
        if track:
            query += ' AND track=?'
            params.append(track)
        query += ' ORDER BY c.date,c.start_time,c.track'
        return list(self.db.execute(query, params))

    def overview(self):
        span = self.db.execute("SELECT min(json_extract(context,'$.date')),max(json_extract(context,'$.date')) FROM jobs WHERE kind='calendar' AND last_success IS NOT NULL").fetchone()
        meetings = self.db.execute('SELECT track,label FROM calendar_tracks ORDER BY date,start_time,track')
        track_names = {}
        meeting_count = 0
        for track, name in meetings:
            track_names[track] = name
            meeting_count += 1
        race_count = self.db.execute("SELECT (SELECT count(*) FROM races)-(SELECT count(*) FROM directory_hidden_races)").fetchone()[0]
        return {"meeting_count": meeting_count, "race_count": race_count,
                "horse_count": self.db.execute("SELECT count(*) FROM horses").fetchone()[0],
                "first_date": span[0], "last_date": span[1], "tracks": track_names,
                "last_fetched_at": self.db.execute("SELECT max(finished_at) FROM requests WHERE outcome='ok'").fetchone()[0],
                "pending": self.db.execute("SELECT count(*) FROM jobs WHERE status='pending'").fetchone()[0],
                "failed": self.db.execute("SELECT count(*) FROM jobs WHERE status='failed'").fetchone()[0],
                "paused": bool(self.db.execute("SELECT paused_reason FROM control WHERE id=1").fetchone()[0]),
                "toto": toto.coverage(self.db),
                "now": datetime.now(timezone.utc).isoformat()}

    def calendar(self, start, end, track="", offset=0, compact=False):
        if start > end or not 0 <= offset <= 10_000_000:
            raise ValueError("Invalid date range")
        days = [dict(row) for row in self.db.execute("""SELECT json_extract(context,'$.date') AS date,
            last_success AS fetched_at,status FROM jobs WHERE kind='calendar'
            AND json_extract(context,'$.date') BETWEEN ? AND ? ORDER BY date""", (start, end))]
        rows = self.meeting_rows(start, end, track)
        limit = 30
        # Reconcile removed meetings before paging; expand fields only for this page.
        offset = min(offset, max(0, (len(rows) - 1) // limit * limit))
        return {"meetings": [self.meeting_record(row,compact) for row in rows[offset:offset + limit]],
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
        entries = [self.person_names(scoped=True).entry(json.loads(row[0])) for row in self.db.execute("SELECT data FROM entries WHERE date=? AND track=? AND race_number=? ORDER BY CAST(program_number AS INTEGER),program_number", (day, track, number))]
        form = {entry['horseId']: self.horse_starts(entry['horseId'], before=day, limit=5)
                for entry in entries}
        return {**meeting, "race": race, "entries": entries, "form": form,
                "toto": toto.read_race(self.db, day, track, number),
                "prediction": prediction_store.read_race(self.db, race['data'], entries)}

    def horses(self, query, offset):
        # Python casefold handles Finnish letters; SQLite's built-in LIKE does not.
        self.db.create_function("casefold", 1, lambda s: s.casefold() if s else "", deterministic=True)
        where = "WHERE instr(casefold(name),?) > 0"
        term = query.strip().casefold()
        count = self.db.execute(f"SELECT count(*) FROM horses {where}", (term,)).fetchone()[0]
        rows = self.db.execute(f"SELECT * FROM horses {where} ORDER BY casefold(name),id LIMIT 30 OFFSET ?", (term, offset))
        return {"horses": [dict(row) for row in rows], "total": count, "offset": offset, "limit": 30}

    def horse(self, horse_id, offspring_offset=0, include_starts=True, include_family=True, family_order='h.name,h.id'):
        row = self.db.execute("SELECT * FROM horses WHERE id=?", (horse_id,)).fetchone()
        if row is None:
            raise LookupError("Horse not found")
        if not 0 <= offspring_offset <= 10_000_000:
            raise ValueError('Invalid page')
        profile = self.db.execute('SELECT data,fetched_at FROM horse_profiles WHERE horse_id=?', (horse_id,)).fetchone()
        job = self.db.execute('SELECT status FROM jobs WHERE path=?', (api.profile_path(horse_id),)).fetchone()
        parties = [dict(p) for p in self.db.execute('SELECT role,label,party_key AS id FROM horse_parties WHERE horse_id=? ORDER BY role', (horse_id,))]
        result = {"horse": dict(row), "starts": self.horse_starts(horse_id) if include_starts else [],
                  'photo': self.photo('horse', horse_id),
                  'profile': {'data': self.person_names().entry(json.loads(profile['data'])), 'fetched_at': profile['fetched_at']} if profile else None,
                  'profile_status': job['status'] if job else 'not_queued', 'parties': parties,
                  'pedigree': {}, 'offspring': {'horses': [], 'total': 0, 'offset': 0, 'limit': 30}}
        if not include_family:
            return result
        children = ' FROM horses h JOIN horse_profiles p ON p.horse_id=h.id WHERE EXISTS (SELECT 1 FROM horse_parents r WHERE r.horse_id=h.id AND r.parent_id=?)'
        total = self.db.execute('SELECT count(*)' + children, (horse_id,)).fetchone()[0]
        offspring_offset = min(offspring_offset, max(0, (total-1)//30*30))
        offspring = [dict(h) for h in self.db.execute('SELECT h.*,p.fetched_at AS relationship_fetched_at' + children + f' ORDER BY {family_order} LIMIT 30 OFFSET ?', (horse_id, offspring_offset))]
        return {**result,
                'pedigree': self.pedigree(horse_id),
                'offspring': {'horses':offspring,'total':total,'offset':offspring_offset,'limit':30}}

    def pedigree(self, value, depth=3, seen=None):
        if depth <= 0:
            return {}
        seen = (seen or set()) | {value}
        result = {}
        for r in self.db.execute('SELECT r.*,p.fetched_at FROM horse_parents r LEFT JOIN horse_profiles p ON p.horse_id=r.parent_id WHERE r.horse_id=?', (value,)).fetchall():
            cycle = r['parent_id'] in seen
            result[r['role']] = {'id':r['parent_id'], 'name':r['name'], 'fetched_at':r['fetched_at'],
                'cycle':cycle, 'parents':self.pedigree(r['parent_id'], depth-1, seen) if r['parent_id'] and not cycle else {}}
        return result

    def parties(self, role, query='', offset=0):
        if role not in ('owner','breeder') or len(query)>200 or not 0 <= offset <= 10_000_000:
            raise ValueError('Invalid relationship search')
        self.db.create_function('casefold', 1, lambda s:s.casefold() if s else '', deterministic=True)
        source = """ FROM horse_parties r JOIN horse_profiles p ON p.horse_id=r.horse_id
            WHERE r.role=? AND instr(casefold(r.label),?)>0"""
        args = (role, query.strip().casefold())
        total = self.db.execute('SELECT count(DISTINCT party_key)' + source, args).fetchone()[0]
        offset = min(offset, max(0,(total-1)//30*30))
        rows = self.db.execute('SELECT r.party_key AS id,r.label AS name,count(*) AS horses,max(p.fetched_at) AS fetched_at' + source + ' GROUP BY r.party_key,r.label ORDER BY casefold(r.label),r.party_key LIMIT 30 OFFSET ?', (*args,offset))
        return {'parties':[dict(r) for r in rows], 'role':role,'total':total,'offset':offset,'limit':30}

    def party(self, role, key, offset=0, ordering='h.name,h.id'):
        if role not in ('owner','breeder') or len(key)!=64 or any(c not in '0123456789abcdef' for c in key) or not 0 <= offset <= 10_000_000:
            raise ValueError('Invalid relationship')
        source = ' FROM horse_parties r JOIN horse_profiles p ON p.horse_id=r.horse_id JOIN horses h ON h.id=r.horse_id WHERE r.role=? AND r.party_key=?'
        args = (role,key)
        row = self.db.execute('SELECT r.label AS name,count(*) AS horses,max(p.fetched_at) AS fetched_at' + source, args).fetchone()
        if not row['horses']:
            raise LookupError('Relationship not found')
        total = row['horses']
        offset = min(offset,max(0,(total-1)//30*30))
        horses = [dict(h) for h in self.db.execute('SELECT h.*,p.fetched_at AS relationship_fetched_at' + source + f' ORDER BY {ordering} LIMIT 30 OFFSET ?', (*args,offset))]
        return {'party':{**dict(row),'id':key,'role':role},'horses':horses,'total':total,'offset':offset,'limit':30}

    def prepare_people(self, role):
        if role not in ('driver', 'trainer'):
            raise ValueError('Invalid role')
        self.db.create_function('person_name', 2, self.person_names().resolve, deterministic=True)

    def people(self, role, query='', offset=0):
        if not 0 <= offset <= 10_000_000 or len(query) > 200:
            raise ValueError('Invalid search')
        self.prepare_people(role)
        self.db.create_function('casefold', 1, lambda s: s.casefold() if s else '', deterministic=True)
        grouped = """WITH people AS (SELECT id,person_name(id,name) AS name,name AS source_name,
            entries,horses,last_entry AS last_date,fetched_at FROM directory_activity WHERE role=?) """
        where = ' FROM people WHERE (instr(casefold(name),?)>0 OR instr(casefold(source_name),?)>0)'
        args = (role, query.strip().casefold(), query.strip().casefold())
        total = self.db.execute(grouped + 'SELECT count(*)' + where, args).fetchone()[0]
        offset = min(offset, max(0, (total - 1) // 30 * 30))
        rows = self.db.execute(grouped + 'SELECT *' + where + ' ORDER BY casefold(name),id LIMIT 30 OFFSET ?', (*args, offset))
        return {'people': [dict(r) for r in rows], 'total': total, 'offset': offset, 'limit': 30, 'role': role}

    def person(self, role, person_id, today, period='', offset=0):
        if period not in ('', 'upcoming', 'history') or not 0 <= offset <= 10_000_000:
            raise ValueError('Invalid page')
        self.prepare_people(role)
        source = f"""WITH source AS (
            SELECT e.*, result_known(e.absent,e.placing,json_extract(e.data,'$.disqualifiedCode')) AS result_known,
                result_win(e.absent,e.placing,json_extract(e.data,'$.disqualifiedCode')) AS result_win,
                CAST(json_extract(e.data,'$.{role}Id') AS TEXT) AS person_id,
                trim(coalesce(json_extract(e.data,'$.{role}Name'),'')) AS source_name,
                person_name(CAST(json_extract(e.data,'$.{role}Id') AS TEXT),
                    trim(coalesce(json_extract(e.data,'$.{role}Name'),''))) AS person_name
            FROM entries e WHERE {self.entry_filter()} AND person_id NOT IN ('','0')),
            person_entries AS (SELECT *,
            result_known AS has_result,
            (date>=? AND NOT result_known) AS upcoming
            FROM source WHERE person_id=?) """
        args = (today, person_id)
        person = self.db.execute(source + """SELECT person_id AS id,person_name AS name,source_name,fetched_at
            FROM person_entries ORDER BY fetched_at DESC,date DESC,track,race_number,program_number LIMIT 1""", args).fetchone()
        if person is None:
            raise LookupError('Person not found')
        summary = dict(self.db.execute(source + """SELECT count(*) AS entries,count(DISTINCT horse_id) AS horses,
            sum(has_result) AS results,sum(result_win) AS wins,
            sum(upcoming) AS upcoming FROM person_entries""", args).fetchone())
        period = period or ('upcoming' if summary['upcoming'] else 'history')
        total = summary['upcoming'] if period == 'upcoming' else summary['entries'] - summary['upcoming']
        offset = min(offset, max(0, (total - 1) // 30 * 30))
        order = 'ASC' if period == 'upcoming' else 'DESC'
        rows = self.db.execute(source + f"""SELECT p.*,m.city,m.data AS meeting_data FROM person_entries p
            JOIN meetings m ON m.date=p.date AND m.track=p.track WHERE upcoming=?
            ORDER BY p.date {order},p.track,CAST(p.race_number AS INTEGER),p.race_number,
                CAST(p.program_number AS INTEGER),p.program_number LIMIT 30 OFFSET ?""",
            (*args, int(period == 'upcoming'), offset))
        starts = []
        for row in rows:
            item = dict(row)
            item['data'] = self.person_names().entry(json.loads(item['data']))
            item['meeting_data'] = json.loads(item['meeting_data'])
            starts.append(item)
        return {'person': {**dict(person), 'role': role}, 'summary': summary, 'starts': starts,
                'photo': self.photo(role, person_id),
                'period': period, 'total': total, 'offset': offset, 'limit': 30}

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
            item["data"] = self.person_names(scoped=True).entry(json.loads(item["data"]))
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
    flat = {key: value[0] for key, value in params.items()}
    if path == '/api/analytics':
        required(params, 'today')
        return analytics.leaderboard(archive, flat)
    if path == '/api/predictions/results':
        return prediction_results.evaluate(archive.db, api.iso_date(required(params,'from')),
            api.iso_date(required(params,'to')), flat.get('mode','backtest'),int(flat.get('offset','0')))
    if path in ('/api/tracks', '/api/track'):
        required(params, 'today')
        if path == '/api/track':
            required(params, 'id')
            return tracks.detail(archive, flat)
        return tracks.directory(archive, flat)
    if path in ('/api/directory/horses', '/api/directory/people', '/api/activity', '/api/preview'):
        required(params, 'today')
        if path == '/api/activity':
            return browse.activity(archive, flat)
        if path == '/api/preview':
            return browse.preview(archive, flat)
        return browse.directory(archive, path.rsplit('/', 1)[-1], flat)
    if path == "/api/overview":
        return archive.overview()
    if path == "/api/coverage":
        return archive.coverage(int(params.get('offset', ['0'])[0]))
    if path == "/api/calendar":
        return archive.calendar(api.iso_date(required(params, "from")), api.iso_date(required(params, "to")),
                                params.get("track", [""])[0], int(params.get("offset", ["0"])[0]), flat.get('view')=='compact')
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
        section = params.get('section', ['full'])[0]
        if section not in ('full', 'activity', 'family'):
            raise ValueError('Invalid horse section')
        browse.prepare(archive)
        ordering = browse.order_by(flat if section == 'family' else {},
                                   {'name':'fold(h.name) COLLATE FINNISH','observed':'p.fetched_at'},'h.name,h.id')
        return archive.horse(required(params, "id"), int(params.get('offspring_offset',['0'])[0]),
                             include_starts=section == 'full', include_family=section != 'activity', family_order=ordering)
    if path == '/api/parties':
        return archive.parties(required(params,'role'),params.get('q',[''])[0],int(params.get('offset',['0'])[0]))
    if path == '/api/party':
        browse.prepare(archive)
        ordering = browse.order_by(flat,{'name':'fold(h.name) COLLATE FINNISH','observed':'p.fetched_at'},'h.name,h.id')
        return archive.party(required(params,'role'),required(params,'id'),int(params.get('offset',['0'])[0]),ordering)
    if path == '/api/people':
        return archive.people(required(params, 'role'), params.get('q', [''])[0], int(params.get('offset', ['0'])[0]))
    if path == '/api/person':
        return archive.person(required(params, 'role'), required(params, 'id'), api.iso_date(required(params, 'from')),
                              params.get('period', [''])[0], int(params.get('offset', ['0'])[0]))
    if path == "/api/saved":
        ids = params.get("ids", [""])[0]
        return archive.saved(ids.split(',') if ids else [], api.iso_date(required(params, "from")))
    if path == '/api/followed':
        return browse.followed_activity(archive, params, api.iso_date(required(params, 'today')))
    raise LookupError("Not found")


def application(db_path, trusted_hosts=()):
    db_uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    hosts = {"localhost", "127.0.0.1", *(h.strip().lower() for h in trusted_hosts if h.strip())}
    browse_cache = {}

    def dispatch(path, query):
        if path in ASSETS:
            filename, content_type = ASSETS[path]
            return 200, (WEB / filename).read_bytes(), content_type
        if path != '/healthz' and not path.startswith(('/media/', '/api/')):
            return 404, b'Not found', 'text/plain'
        media = path.startswith('/media/')
        try:
            with closing(sqlite3.connect(db_uri, uri=True, timeout=10)) as db:
                db.row_factory = sqlite3.Row
                if path == '/healthz':
                    if db.execute('SELECT 1 FROM control WHERE id=1').fetchone():
                        return 200, b'ok', 'text/plain'
                    return 503, b'Archive unavailable', 'text/plain'
                if media:
                    return 200, photos.image(db, path), 'image/jpeg'
                db.execute('BEGIN')
                result = endpoint(Archive(db, browse_cache), path, parse_qs(query))
            body = json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()
            return 200, body, 'application/json'
        except ValueError:
            return 400, b'{"error":"invalid_request"}', 'application/json'
        except LookupError:
            if media:
                return 404, b'Not found', 'text/plain'
            return 404, b'{"error":"not_found"}', 'application/json'
        except sqlite3.Error as exc:
            logging.getLogger(__name__).warning("Archive read failed (%s)", getattr(exc, 'sqlite_errorname', type(exc).__name__))
            return 503, b'{"error":"database_unavailable"}', 'application/json'

    def app(environ, start_response):
        host, separator, port = environ.get('HTTP_HOST', '').lower().partition(':')
        method = environ['REQUEST_METHOD']
        path = environ['PATH_INFO']
        headers = [('X-Content-Type-Options', 'nosniff'), ('Content-Security-Policy',
            "default-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")]
        cache = 'no-store'
        if host not in hosts or (separator and not port.isdecimal()):
            status, body, mime = 403, b'{"error":"forbidden"}', 'application/json'
        elif method not in ('GET', 'HEAD'):
            status, body, mime = 405, b'Method not allowed', 'text/plain'
            headers.append(('Allow', 'GET, HEAD'))
        else:
            status, body, mime = dispatch(path, environ.get('QUERY_STRING', ''))
            if status == 200 and path in ASSETS:
                tag = '"' + hashlib.sha256(body).hexdigest() + '"'
                headers.append(('ETag', tag))
                cache = 'private, no-cache'
                if tag in (v.strip() for v in environ.get('HTTP_IF_NONE_MATCH', '').split(',')):
                    status = 304
        headers.append(('Cache-Control', cache))
        if status != 304:
            headers.extend([('Content-Type', mime if mime.startswith('image/') else mime + '; charset=utf-8'),
                            ('Content-Length', str(len(body)))])
        start_response(f'{status} {HTTPStatus(status).phrase}', headers)
        return [] if method == 'HEAD' or status == 304 else [body]

    return app


def deployment_app():
    from . import store
    path = os.environ.get('HIPPOS_DB', '/data/hippos.sqlite3')
    # Gunicorn preload initializes or upgrades the archive before accepting traffic.
    store.connect(path).close()
    return application(path, os.environ.get('HIPPOS_TRUSTED_HOSTS', '').split(','))


class LocalServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def make_server(db_path, port=8765):
    return make_wsgi_server('127.0.0.1', port, application(db_path), server_class=LocalServer)


def serve(db_path, port):
    with make_server(db_path, port) as server:
        print(f"Local UI: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
        server.serve_forever()
