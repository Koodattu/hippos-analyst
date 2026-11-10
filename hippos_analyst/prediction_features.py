"""Point-in-event-time features. No odds or current-race outcomes enter X."""

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import api, race_results

FEATURE_VERSION = 3

FEATURES = ['track', 'breed', 'start_form', 'distance', 'lane', 'handicap', 'field_size',
            'history_count', 'recent_count', 'days_since_start', 'win_rate', 'recent_win_rate',
            'recent_finish', 'gallop_rate', 'comparable_time', 'time_count',
            'driver_rate', 'driver_count', 'trainer_rate', 'trainer_count',
            'form_vs_field', 'time_vs_field', 'discipline',
            'discipline_history_count', 'discipline_win_rate', 'discipline_recent_finish',
            'discipline_gallop_rate', 'discipline_driver_rate', 'discipline_driver_count',
            'discipline_trainer_rate', 'discipline_trainer_count']
CATEGORICAL = ['track', 'breed', 'start_form', 'discipline']
SIGNATURE_FIELDS = ('horseId', 'programNumber', 'absent', 'distance', 'lane', 'driverId', 'trainerId')


def signature(race, entries):
    value = {k: race.get(k) for k in ('date', 'trackCode', 'startNumber', 'startType',
                                     'startForm', 'baseDistance', 'eventType', 'monte', 'plannedTime')}
    value['field'] = [{k: e.get(k) for k in SIGNATURE_FIELDS}
                      for e in sorted(entries, key=lambda e: str(e['programNumber']))]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def number(value, missing=-1.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else missing
    except (TypeError, ValueError):
        return missing


def kilometre_seconds(value):
    match = re.fullmatch(r'(\d)\.(\d{2})\.(\d)', str(value))
    if not match:
        return None
    minutes, seconds, tenths = map(int, match.groups())
    result = minutes * 60 + seconds + tenths / 10
    return result if seconds < 60 and 60 <= result <= 180 else None


def supported(race):
    return (race.get('startType') == 'TOTO' and (race.get('monte') is False or race.get('monte') is True)
            and race.get('eventType') in ('LAMMINVERISET', 'KYLMAVERISET')
            and race.get('startForm') in ('RYHMALAHTO', 'TASOITUSAJO'))


def discipline(race):
    return 'monte' if race.get('monte') is True else 'sulky' if race.get('monte') is False else 'unknown'


def result_reason(race, entries):
    starters = [e for e in entries if not e.get('absent')]
    if not supported(race):
        return 'unsupported_type'
    if race.get('status') != '2':
        return 'unsettled_status'
    if len(starters) < 2 or len({str(e['horseId']) for e in entries}) != len(entries):
        return 'invalid_field'
    outcomes = [race_results.outcome(e) for e in starters]
    if any(o['kind'] == 'unknown' or (o['place'] is not None and o['place']>len(starters)) for o in outcomes):
        return 'unknown_placing'
    if sum(race_results.winner(e) for e in starters) != 1:
        return 'winner_not_unique'
    return None


def scheduled_at(race):
    try:
        return datetime.fromisoformat(race['date'] + 'T' + race['plannedTime']).replace(
            tzinfo=ZoneInfo('Europe/Helsinki')).timestamp()
    except (ValueError, KeyError, TypeError):
        return None


def read_groups(db):
    """Use latest successful source membership, including field completeness."""
    heads = {r['path']: r for r in db.execute('''SELECT q.id,q.path,q.finished_at,s.body
        FROM requests q JOIN snapshots s ON s.id=q.snapshot_id
        WHERE q.id IN (SELECT max(id) FROM requests WHERE outcome='ok' GROUP BY path)''')}
    visible = set()
    for path, row in heads.items():
        if path.startswith('/race/search/'):
            for meeting in json.loads(row['body']):
                if not meeting.get('canceled'):
                    visible.add((meeting['date'], str(meeting['trackCode'])))
    groups = []
    for day, track in sorted(visible):
        race_head = heads.get(api.races_path(day, track))
        if race_head is None:
            continue
        for race in json.loads(race_head['body']):
            key = (day, track, str(race['startNumber']))
            field = heads.get(api.runners_path(*key))
            if field is None:
                continue
            entries = sorted(json.loads(field['body']), key=lambda e: int(e['programNumber']))
            groups.append({'key': key, 'race': race, 'entries': entries,
                           'signature': signature(race, entries), 'field_at': field['finished_at'],
                           'request_id': field['id']})
    return sorted(groups, key=lambda g: g['key'])


def build_features(groups):
    """Batch each date: even another race that same day cannot supply history."""
    horses, drivers, trainers = defaultdict(list), defaultdict(list), defaultdict(list)
    discipline_drivers, discipline_trainers = defaultdict(list), defaultdict(list)
    dates = defaultdict(list)
    for g in groups:
        dates[g['key'][0]].append(g)
    excluded = Counter()
    for day, daily in sorted(dates.items()):
        for g in daily:
            race = g['race']
            kind = discipline(race)
            g['reason'] = result_reason(race, g['entries'])
            excluded[g['reason'] or 'eligible'] += 1
            g['starters'] = [e for e in g['entries'] if not e.get('absent')]
            rows, forms, times = [], [], []
            for e in g['starters']:
                history = horses[str(e['horseId'])]
                recent = history[-5:]
                same = [h for h in history if h['discipline'] == kind]
                same_recent = same[-5:]
                distance = number(e.get('distance'))
                comparable = [h['time'] for h in same[-10:] if h['time'] is not None
                              and h['breed'] == race.get('eventType')
                              and h['start'] == race.get('startForm')
                              and abs(h['distance'] - distance) <= 200]
                km = sum(comparable) / len(comparable) if comparable else -1
                wins = sum(h['win'] for h in history)
                recent_wins = sum(h['win'] for h in recent)
                form = (recent_wins + 1) / (len(recent) + 10)
                dh = drivers[str(e['driverId'])] if e.get('driverId') else []
                th = trainers[str(e['trainerId'])] if e.get('trainerId') else []
                dd = discipline_drivers[(str(e['driverId']),kind)] if e.get('driverId') else []
                dt = discipline_trainers[(str(e['trainerId']),kind)] if e.get('trainerId') else []
                rows.append([g['key'][1], race.get('eventType', ''), race.get('startForm', ''),
                             distance, number(e.get('lane')), distance-number(race.get('baseDistance')),
                             len(g['starters']), len(history), len(recent),
                             (date.fromisoformat(day)-date.fromisoformat(history[-1]['day'])).days if history else -1,
                             (wins+1)/(len(history)+10), form,
                             sum(h['finish'] for h in recent)/len(recent) if recent else -1,
                             sum(h['gallop'] for h in recent)/len(recent) if recent else -1,
                             km, len(comparable), (sum(dh[-100:])+2)/(len(dh[-100:])+20), len(dh),
                             (sum(th[-100:])+2)/(len(th[-100:])+20), len(th),
                             # Field-relative values are filled after all runners are read.
                             0, 0, kind, len(same), (sum(h['win'] for h in same)+1)/(len(same)+10),
                             sum(h['finish'] for h in same_recent)/len(same_recent) if same_recent else -1,
                             sum(h['gallop'] for h in same_recent)/len(same_recent) if same_recent else -1,
                             (sum(dd[-100:])+2)/(len(dd[-100:])+20), len(dd),
                             (sum(dt[-100:])+2)/(len(dt[-100:])+20), len(dt)])
                forms.append(form)
                times.append(km)
            mean_form = sum(forms)/len(forms) if forms else 0
            known_times = [t for t in times if t > 0]
            mean_time = sum(known_times)/len(known_times) if known_times else 0
            for row, form, km in zip(rows, forms, times):
                row[20:22] = [form-mean_form, km-mean_time if km > 0 else -1]
            g['x'] = rows
            g['y'] = [int(race_results.winner(e)) for e in g['starters']]
            g['form_scores'] = [math.log(f) for f in forms]
        for g in daily:
            if g['reason']:
                continue
            for e in g['starters']:
                result = race_results.outcome(e)
                win = int(race_results.winner(e))
                placing = result['place']
                horses[str(e['horseId'])].append({
                    'day': day, 'win': win, 'finish': (placing if placing else len(g['starters']))/len(g['starters']),
                    'gallop': int(race_results.galloped(e)),
                    'time': kilometre_seconds(e.get('kilometerTime')) if result['kind']=='placed' else None,
                    'breed': g['race'].get('eventType'), 'start': g['race'].get('startForm'),
                    'discipline': discipline(g['race']),
                    'distance': number(e.get('distance'))})
                if e.get('driverId'):
                    drivers[str(e['driverId'])].append(win)
                    discipline_drivers[(str(e['driverId']),discipline(g['race']))].append(win)
                if e.get('trainerId'):
                    trainers[str(e['trainerId'])].append(win)
                    discipline_trainers[(str(e['trainerId']),discipline(g['race']))].append(win)
    return groups, dict(excluded)
