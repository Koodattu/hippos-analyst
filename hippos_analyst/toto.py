"""Optional, read-only Veikkaus Toto enrichment; never wagering or login."""

import json
import re
import socket
import time
import unicodedata
from datetime import datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from . import api

BASE_URL = 'https://www.veikkaus.fi/api/toto-info/v1'
PREFIX = 'toto:'
DAILY_BUDGET = 40
MIN_DELAY = 60


def endpoint(key):
    """Queue suffixes identify scheduled observations, never query the provider."""
    if not isinstance(key, str) or not key.startswith(PREFIX):
        raise ValueError('Expected a Toto queue key')
    path = key[len(PREFIX):].split('@', 1)[0]
    if not re.fullmatch(r'/cards/date/\d{4}-\d{2}-\d{2}|/card/[0-9]+/races|'
                        r'/race/[0-9]+/(?:runners|pools)|/pool/[0-9]+/odds', path):
        raise ValueError('Unsupported read-only Toto endpoint')
    return path


def fetch(key):
    request = Request(BASE_URL + endpoint(key), headers={
        'Accept': 'application/json', 'X-ESA-API-Key': 'ROBOT',
        'User-Agent': 'hippos-analyst/0.1 (private educational research; single worker)',
    })
    try:
        with build_opener(api.NoRedirects()).open(request, timeout=30) as response:
            body = response.read(api.MAX_RESPONSE_BYTES + 1)
            if len(body) > api.MAX_RESPONSE_BYTES:
                raise api.SchemaError('Toto response exceeds the 8 MiB limit')
            return api.Response(response.status, body, {k.lower(): v for k, v in response.headers.items()})
    except HTTPError as exc:
        with exc:
            return api.Response(exc.code, headers={k.lower(): v for k, v in exc.headers.items()})
    except (URLError, TimeoutError, socket.timeout, OSError, HTTPException):
        return api.Response(0)



def integer(value, label, maximum=10**16):
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r'[0-9]+', str(value)):
        raise api.SchemaError(f'Invalid Toto {label}')
    if not 1 <= int(value) <= maximum:
        raise api.SchemaError(f'Invalid Toto {label}')
    return str(int(value))


def text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise api.SchemaError(f'Invalid Toto {label}')
    return value.strip()


def boolean(value, label):
    if not isinstance(value, bool):
        raise api.SchemaError(f'Invalid Toto {label}')
    return value


def collection(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('collection'), list):
        raise api.SchemaError('Expected Toto collection')
    rows = payload['collection']
    if len(rows) > 500 or any(not isinstance(r, dict) for r in rows):
        raise api.SchemaError('Unexpected Toto collection size or item')
    return rows


def unique(records, key):
    if len({r[key] for r in records}) != len(records):
        raise api.SchemaError(f'Duplicate Toto {key}')
    return records


def normalize(kind, payload, context):
    if kind == 'toto_odds':
        return normalize_odds(payload, context)
    rows = collection(payload)
    if kind == 'toto_cards':
        result = []
        for r in rows:
            if r.get('country') != 'FI' or r.get('raceType') != 'TROT':
                continue
            if r.get('meetDate') != context['date']:
                raise api.SchemaError('Toto card date mismatch')
            result.append({'cardId': integer(r.get('cardId'), 'card ID'),
                           'trackAbbreviation': text(r.get('trackAbbreviation'), 'track'),
                           'trackName': text(r.get('trackName'), 'track name'),
                           'cancelled': boolean(r.get('cancelled'), 'cancellation')})
        return unique(result, 'cardId')
    if kind == 'toto_races':
        result = []
        for r in rows:
            if integer(r.get('cardId'), 'card ID') != context['card_id']:
                raise api.SchemaError('Toto race belongs to another card')
            stamp = int(integer(r.get('startTime'), 'start time')) / 1000
            midnight = datetime.fromisoformat(context['date']).replace(tzinfo=timezone.utc).timestamp()
            # The card's meetDate is authoritative. Check a plausible Finnish
            # day window without requiring an external IANA database on Windows.
            if not midnight - 3 * 3600 <= stamp < midnight + 86400:
                raise api.SchemaError('Toto race date mismatch')
            result.append({'raceId': integer(r.get('raceId'), 'race ID'),
                           'number': integer(r.get('number'), 'race number', 99),
                           'startTime': stamp, 'raceStatus': text(r.get('raceStatus'), 'race status'),
                           'distance': integer(r.get('distance'), 'distance', 100000)})
        unique(result, 'raceId')
        return unique(result, 'number')
    if kind == 'toto_runners':
        result = []
        for r in rows:
            if integer(r.get('raceId'), 'race ID') != context['race_id']:
                raise api.SchemaError('Toto runner belongs to another race')
            record = {'runnerId': integer(r.get('runnerId'), 'runner ID'),
                           'startNumber': integer(r.get('startNumber'), 'runner number', 99),
                           'horseName': text(r.get('horseName'), 'horse name'),
                           'distance': integer(r.get('distance'), 'runner distance', 100000),
                           'scratched': boolean(r.get('scratched'), 'scratch')}
            for field in ('frontShoes', 'rearShoes', 'specialCart', 'driverStats'):
                if r.get(field) is not None:
                    record[field] = text(r[field], field)
            result.append(record)
        unique(result, 'runnerId')
        return unique(result, 'startNumber')
    if kind == 'toto_pools':
        result = []
        for r in rows:
            if r.get('poolType') != 'VOI':
                continue
            races = r.get('races')
            if not isinstance(races, list) or len(races) != 1 or not isinstance(races[0], dict):
                raise api.SchemaError('Unexpected Toto win-pool races')
            if integer(races[0].get('raceId'), 'pool race ID') != context['race_id']:
                raise api.SchemaError('Toto pool belongs to another race')
            if integer(r.get('cardId'), 'card ID') != context['card_id']:
                raise api.SchemaError('Toto pool belongs to another card')
            result.append({'poolId': integer(r.get('poolId'), 'pool ID'),
                           'poolStatus': text(r.get('poolStatus'), 'pool status')})
        if len(result) > 1:
            raise api.SchemaError('Ambiguous Toto win pool')
        return result
    raise api.SchemaError('Unknown Toto job kind')


def normalized_name(value):
    # Preserve punctuation and country suffixes: uncertainty must remain unmatched.
    return ' '.join(unicodedata.normalize('NFC', value).casefold().split())


def matched_runners(db, context, records):
    local = {str(r['program_number']): dict(r) for r in db.execute(
        'SELECT program_number,horse_id,data FROM entries WHERE date=? AND track=? AND race_number=?',
        (context['date'], context['track'], context['number']))}
    if not records or set(local) != {r['startNumber'] for r in records}:
        return None
    matched = []
    for r in records:
        entry = local[r['startNumber']]
        data = json.loads(entry['data'])
        if normalized_name(data['horseName']) != normalized_name(r['horseName']) or str(data.get('distance')) != r['distance']:
            return None
        matched.append({**r, 'horse_id': entry['horse_id']})
    return matched


def seed(db, day, track, numbers, samples=3, interval=1800):
    from . import store
    api.iso_date(day)
    track = api.identifier(track)
    numbers = list(dict.fromkeys(integer(n, 'race number', 99) for n in numbers))
    if not 1 <= len(numbers) <= 3 or not 1 <= samples <= 3 or not 900 <= interval <= 86400:
        raise ValueError('Select 1–3 known races, 1–3 samples and a 900–86400 second sample interval')
    state = db.execute('SELECT * FROM control').fetchone()
    if state['paused_reason'] or state['paused_until'] > time.time():
        raise ValueError('Collection is stopped or cooling down; no Toto seeds added')
    if db.execute("SELECT 1 FROM jobs WHERE status='failed' LIMIT 1").fetchone():
        raise ValueError('Investigate failed collection jobs before adding Toto work')
    for number in numbers:
        if not db.execute('SELECT 1 FROM entries WHERE date=? AND track=? AND race_number=? LIMIT 1', (day,track,number)).fetchone():
            raise ValueError('Toto enrichment requires an already collected Hippos field')
    # One explicitly selected meeting per seed; repeated seeds never refresh done jobs.
    key = f'toto:/cards/date/{day}@{track}'
    if db.execute('SELECT 1 FROM jobs WHERE path=?', (key,)).fetchone():
        return 0
    for number in numbers:
        db.execute('INSERT OR IGNORE INTO toto_targets(date,track,number) VALUES(?,?,?)', (day,track,number))
    return store.enqueue(db, key, 'toto_cards', {'date':day,'track':track,'numbers':numbers,'samples':samples,'interval':interval}, 80)


def enqueue(db, path, kind, context, due=0):
    from . import store
    key = PREFIX + path
    store.enqueue(db, key, kind, context, 80)
    if due:
        db.execute("UPDATE jobs SET next_attempt=? WHERE path=? AND attempts=0", (due,key))


def target(db, c):
    return db.execute('SELECT * FROM toto_targets WHERE date=? AND track=? AND number=?',
                      (c['date'],c['track'],c['number'])).fetchone()


def save_response(db, job, records, request_id, now):
    from .store import encode
    c = json.loads(job['context'])
    kind = job['kind']
    if kind == 'toto_cards':
        candidates = [r for r in records if r['trackAbbreviation'].upper() == c['track'].upper() and not r['cancelled']]
        if len(candidates) != 1:
            db.execute("UPDATE toto_targets SET match_status='unmatched',note='card' WHERE date=? AND track=?", (c['date'],c['track']))
            return
        c['card_id'] = candidates[0]['cardId']
        enqueue(db, f"/card/{c['card_id']}/races", 'toto_races', c)
    elif kind == 'toto_races':
        for number in c['numbers']:
            race = next((r for r in records if r['number'] == number), None)
            if race is None:
                db.execute("UPDATE toto_targets SET match_status='unmatched',note='race' WHERE date=? AND track=? AND number=?", (c['date'],c['track'],number))
                continue
            local = db.execute('SELECT distance FROM races WHERE date=? AND track=? AND number=?', (c['date'],c['track'],number)).fetchone()
            if str(local[0]) != race['distance']:
                db.execute("UPDATE toto_targets SET match_status='unmatched',note='distance' WHERE date=? AND track=? AND number=?", (c['date'],c['track'],number))
                continue
            db.execute('UPDATE toto_targets SET card_id=?,race_id=?,scheduled_start=?,race_status=? WHERE date=? AND track=? AND number=?',
                       (c['card_id'],race['raceId'],race['startTime'],race['raceStatus'],c['date'],c['track'],number))
            rc = {**c,'number':number,'race_id':race['raceId']}
            enqueue(db, f"/race/{race['raceId']}/runners", 'toto_runners', rc)
    elif kind == 'toto_runners':
        matched = matched_runners(db,c,records)
        db.execute('UPDATE toto_targets SET runners=?,runners_at=?,match_status=?,note=? WHERE race_id=?',
                   (encode(matched or records),now,'matched' if matched else 'unmatched',None if matched else 'runners',c['race_id']))
        if matched:
            enqueue(db, f"/race/{c['race_id']}/pools", 'toto_pools', c)
    elif kind == 'toto_pools':
        if not records:
            db.execute("UPDATE toto_targets SET note='no_win_pool' WHERE race_id=?", (c['race_id'],))
            return
        pool = records[0]
        db.execute('UPDATE toto_targets SET pool_id=? WHERE race_id=?', (pool['poolId'],c['race_id']))
        enqueue(db, f"/pool/{pool['poolId']}/odds@1", 'toto_odds', {**c,'pool_id':pool['poolId'],'pool_status':pool['poolStatus'],'sample':1})
    elif kind == 'toto_odds':
        save_odds(db, c, records, request_id, now)


def nonnegative(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10**15:
        raise api.SchemaError(f'Invalid Toto {label}')
    return value


def normalize_odds(payload, context):
    if not isinstance(payload, dict) or payload.get('poolType') != 'VOI':
        raise api.SchemaError('Expected a Toto win-odds response')
    if integer(payload.get('poolId'), 'pool ID') != context['pool_id']:
        raise api.SchemaError('Toto odds belong to another pool')
    updated = int(integer(payload.get('updated'), 'odds timestamp')) / 1000
    if not 946684800 <= updated <= 4102444800:
        raise api.SchemaError('Unexpected Toto timestamp unit')
    rows = payload.get('odds')
    if not isinstance(rows, list) or len(rows) > 99:
        raise api.SchemaError('Unexpected Toto odds list')
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise api.SchemaError('Invalid Toto odds item')
        # Observed probable=1009 represents 10.09: netPool=16146 / amount=1600.
        # Scratched runner 6 in the verified historical pool omitted probable.
        # Retain absence separately from zero; neither is a quoted return.
        result.append({'number':integer(row.get('runnerNumber'),'odds runner number',99),
                       'probable':nonnegative(row['probable'],'probable odds') if 'probable' in row else None})
    unique(result,'number')
    return [{'updated':updated,'odds':result}]


def save_odds(db, c, records, request_id, now):
    from .store import encode
    row = target(db,c)
    runners = json.loads(row['runners'] or '[]')
    matched = matched_runners(db,c,runners)
    if row['match_status'] != 'matched' or not matched or any(a['horse_id'] != b['horse_id'] for a,b in zip(runners,matched)):
        db.execute("UPDATE toto_targets SET match_status='unmatched',note='field_changed' WHERE race_id=?",(c['race_id'],))
        return
    by_number = {r['startNumber']:r for r in runners}
    observation = records[0]
    if observation['updated'] > now + 300:
        raise api.SchemaError('Toto odds timestamp is in the future')
    if any(r['number'] not in by_number for r in observation['odds']):
        raise api.SchemaError('Toto odds refer to an unverified participant')
    odds = [{**r,'horse_id':by_number[r['number']]['horse_id']} for r in observation['odds']]
    phase = 'before_scheduled_start' if now < row['scheduled_start'] and observation['updated'] < row['scheduled_start'] else 'after_scheduled_start'
    db.execute('INSERT INTO toto_observations VALUES(?,?,?,?,?,?,?)',
               (request_id,c['race_id'],c['pool_id'],now,row['scheduled_start'],phase,encode({'updated':observation['updated'],'odds':odds})))
    sample = c['sample'] + 1
    due = now + c['interval']
    # CONNECTED is the status observed on both current Finnish win pools.
    if sample <= c['samples'] and due < row['scheduled_start'] and c['pool_status'] in ('OPEN', 'CONNECTED'):
        enqueue(db,f"/pool/{c['pool_id']}/odds@{sample}",'toto_odds',{**c,'sample':sample},due)


def read_race(db, day, track, number):
    row = db.execute('SELECT * FROM toto_targets WHERE date=? AND track=? AND number=?',(day,track,number)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result['collection_failed'] = bool(db.execute(
        "SELECT 1 FROM jobs WHERE kind LIKE 'toto_%' AND status='failed' "
        "AND json_extract(context,'$.date')=? AND json_extract(context,'$.track')=? "
        "AND (json_extract(context,'$.number')=? OR json_extract(context,'$.number') IS NULL) LIMIT 1",
        (day,track,str(number))).fetchone())
    result['runners'] = json.loads(row['runners'] or '[]')
    c = {'date':day,'track':track,'number':number}
    matched = matched_runners(db,c,result['runners']) if row['match_status']=='matched' else None
    if row['match_status']=='matched' and (not matched or any(a.get('horse_id') != b['horse_id'] for a,b in zip(result['runners'],matched))):
        result['match_status'] = 'unmatched'
        result['note'] = 'field_changed'
    result['observations'] = []
    if result['match_status'] == 'matched':
        for observation in db.execute('SELECT * FROM toto_observations WHERE race_id=? ORDER BY observed_at DESC,request_id DESC LIMIT 3',(row['race_id'],)):
            item = dict(observation)
            item['data'] = json.loads(item.pop('body'))
            result['observations'].append(item)
    return result


def coverage(db):
    return {'targets':db.execute('SELECT count(*) FROM toto_targets').fetchone()[0],
            'matched':db.execute("SELECT count(*) FROM toto_targets WHERE match_status='matched'").fetchone()[0],
            'unmatched':db.execute("SELECT count(*) FROM toto_targets WHERE match_status='unmatched'").fetchone()[0],
            'observations':db.execute('SELECT count(*) FROM toto_observations').fetchone()[0],
            'pending':db.execute("SELECT count(*) FROM jobs WHERE path LIKE 'toto:%' AND status='pending'").fetchone()[0],
            'failed':db.execute("SELECT count(*) FROM jobs WHERE path LIKE 'toto:%' AND status='failed'").fetchone()[0],
            'last_fetched_at':db.execute('SELECT max(observed_at) FROM toto_observations').fetchone()[0]}
