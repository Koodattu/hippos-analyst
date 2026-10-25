"""Venue identities and curated facts, separate from race-day observations."""

import json
import math
from pathlib import Path

from . import api

CATALOG = json.loads(Path(__file__).with_name('track_catalog.json').read_text(encoding='utf-8'))
FACTS = {item['code']: item for item in CATALOG['tracks']}
FIELDS = ('trackNumber', 'trackShortname', 'trackName', 'trackCity', 'trackType',
          'formattedTrackName', 'latitude', 'longitude', 'finnishTrack')


def identity(code):
    return 'hippos-' + api.identifier(code)


def observe(db, record, fetched_at):
    code = record['trackCode']
    data = {key: record[key] for key in FIELDS if key in record}
    data['date'] = record['date']
    db.execute('''INSERT INTO tracks(id,hippos_code,data,fetched_at) VALUES(?,?,?,?)
        ON CONFLICT(hippos_code) DO UPDATE SET data=excluded.data,fetched_at=excluded.fetched_at
        WHERE tracks.fetched_at IS NULL OR excluded.fetched_at>tracks.fetched_at
          OR (excluded.fetched_at=tracks.fetched_at
              AND json_extract(excluded.data,'$.date')>=json_extract(tracks.data,'$.date'))''',
        (identity(code), code, json.dumps(data, ensure_ascii=False), fetched_at))


def initialize(db):
    """Offline, additive backfill. Called at writer startup, never by HTTP reads."""
    with db:
        for code in FACTS:
            db.execute("INSERT OR IGNORE INTO tracks(id,hippos_code,data) VALUES(?,?,'{}')",
                       (identity(code), code))
        if not db.execute("SELECT 1 FROM maintenance_state WHERE name='tracks_backfilled_v1'").fetchone():
            for row in db.execute('SELECT data,fetched_at FROM meetings ORDER BY fetched_at,date,track').fetchall():
                observe(db, json.loads(row['data']), row['fetched_at'])
            db.execute("INSERT INTO maintenance_state VALUES('tracks_backfilled_v1','1')")


def coordinates(data):
    try:
        lat, lon = float(data['latitude']), float(data['longitude'])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None
    return {'latitude': lat, 'longitude': lon}


def profile(row):
    observed = json.loads(row['data'])
    curated = FACTS.get(row['hippos_code'], {})
    return {'id': row['id'], 'code': row['hippos_code'],
            'name': curated.get('name') or observed.get('trackShortname') or observed.get('formattedTrackName') or row['hippos_code'],
            'city': curated.get('city') or observed.get('trackCity'),
            'racing_city': observed.get('trackCity'),
            'category': observed.get('trackType'),
            'coordinates': coordinates(observed), 'observed': observed, 'fetched_at': row['fetched_at'],
            'address': curated.get('address'), 'website': curated.get('website'),
            'description': curated.get('description'), 'technical': curated.get('technical'),
            'image': curated.get('image'),
            'provider_ids': {'hippos': {'code': row['hippos_code'], 'number': observed.get('trackNumber')},
                             **curated.get('provider_ids', {})},
            'sources': ([{'url': CATALOG['source'], 'checked': CATALOG['checked'], 'kind': 'profile'}] if curated else [])
                       + ([{'url': curated['technical']['source'], 'checked': curated['technical']['checked'], 'kind': 'technical'}] if curated.get('technical') else [])}


def directory(archive, params):
    query = params.get('q', '').strip().casefold()
    today = api.iso_date(params['today'])
    offset = int(params.get('offset', '0'))
    if len(query) > 200 or not 0 <= offset <= 10_000_000:
        raise ValueError('Invalid track search')
    meetings = {}
    for meeting in archive.meeting_rows():
        meetings.setdefault(meeting['track'], []).append(meeting)
    rows = []
    for row in archive.db.execute('SELECT * FROM tracks'):
        item = profile(row)
        if query not in ' '.join(str(item.get(key) or '') for key in ('name', 'city', 'racing_city', 'code')).casefold():
            continue
        dates = meetings.get(item['code'], [])
        item['meeting_count'] = len(dates)
        item['next_date'] = min((m['date'] for m in dates if m['date'] >= today and not m['canceled']), default=None)
        rows.append(item)
    from .browse import name_key
    rows.sort(key=lambda item: (name_key(item['city']), name_key(item['name']), item['id']))
    offset = min(offset, max(0, (len(rows)-1)//30*30))
    return {'rows': rows[offset:offset+30], 'total': len(rows), 'offset': offset, 'limit': 30}


def detail(archive, params):
    row = archive.db.execute('SELECT * FROM tracks WHERE id=?', (params.get('id', ''),)).fetchone()
    if row is None:
        raise LookupError('Track not found')
    today = api.iso_date(params['today'])
    offset = int(params.get('offset', '0'))
    period = params.get('period') or 'upcoming'
    if period not in ('upcoming', 'history') or not 0 <= offset <= 10_000_000:
        raise ValueError('Invalid track period')
    meetings = archive.meeting_rows(track=row['hippos_code'])
    selected = [m for m in meetings if (m['date'] >= today) == (period == 'upcoming')]
    selected.sort(key=lambda m: (m['date'], m['start_time'] or ''), reverse=period == 'history')
    total = len(selected)
    offset = min(offset, max(0, (total-1)//30*30))
    return {'track': profile(row), 'meeting_count': len(meetings),
            'upcoming_count': sum(m['date'] >= today for m in meetings),
            'history_count': sum(m['date'] < today for m in meetings),
            'rows': [archive.meeting_record(m) for m in selected[offset:offset+30]],
            'period': period, 'total': total, 'offset': offset, 'limit': 30}
