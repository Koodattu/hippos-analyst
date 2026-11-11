"""Local leaderboards over the latest published competitive race fields."""

import json
from datetime import date
from itertools import groupby
from operator import itemgetter

from . import api, browse, race_results


ROLES = ('horse', 'trainer', 'driver')
METRICS = ('starts', 'wins', 'podiums', 'money', 'rate')
RATE_MIN_STARTS = 10


def records(archive, today, period):
    token = (today, archive.db.total_changes,
             archive.db.execute("SELECT max(id) FROM requests WHERE outcome='ok'").fetchone()[0])
    cache = archive.browse_cache
    key = ('analytics', period)
    if cache is not None and key in cache and cache[key][0] == token:
        return cache[key][1]

    end = date.fromisoformat(today)
    start = {'all': date.min, 'year': end.replace(month=1, day=1),
             'month': date.fromordinal(max(1,end.toordinal()-29))}[period]
    keys = []
    for meeting in archive.meeting_rows(start.isoformat(), today):
        if json.loads(meeting['data']).get('canceled'):
            continue
        day, track = meeting['date'], meeting['track']
        races, _ = archive.head(api.races_path(day, track)) or ([], None)
        for race in races:
            if race.get('startType') in ('TOTO', 'PAIKALLIS') and str(race.get('status')) == '2':
                keys.append((day, track, str(race['startNumber'])))

    entries = archive.db.execute("""
        SELECT k.key AS race_index,e.data,h.name AS horse_name,e.date,e.prize
        FROM json_each(?) k JOIN entries e ON e.date=json_extract(k.value,'$[0]')
            AND e.track=json_extract(k.value,'$[1]') AND e.race_number=json_extract(k.value,'$[2]')
        JOIN horses h ON h.id=e.horse_id WHERE coalesce(e.absent,0)=0
        ORDER BY k.key, e.program_number""", (json.dumps(keys),))
    totals = {role:{} for role in ROLES}
    races = 0
    first = last = None
    for _, field in groupby(entries, itemgetter('race_index')):
        starters = [(json.loads(row['data']), row) for row in field]
        if not any(race_results.has_result(entry) for entry, _ in starters):
            continue
        races += 1
        day = starters[0][1]['date']
        first, last = first or day, day
        for entry, row in starters:
            place = race_results.outcome(entry)['place']
            prize = browse.numeric(row['prize'])
            for role in ROLES:
                identity = str(entry.get(role+'Id') or '').strip()
                if identity in ('', '0'):
                    continue
                stats = totals[role].setdefault(identity, dict(id=identity, name='', starts=0,
                                                               wins=0, podiums=0, money=None))
                name = row['horse_name'] if role == 'horse' else entry.get(role+'Name')
                if name:
                    stats['name'] = name
                stats['starts'] += 1
                stats['wins'] += place == 1
                stats['podiums'] += place in (1,2,3)
                if prize is not None:
                    stats['money'] = (stats['money'] or 0) + prize
    for group in totals.values():
        for stats in group.values():
            stats['rate'] = stats['wins'] / stats['starts']
    result = totals, dict(races=races, first=first, last=last)
    if cache is not None:
        cache[key] = (token,result)
    return result


def leaderboard(archive, params):
    today = api.iso_date(params['today'])
    role, metric = params.get('role','horse'), params.get('metric','wins')
    period, offset = params.get('period','all'), int(params.get('offset',0))
    if role not in ROLES or metric not in METRICS or period not in ('all','year','month') or offset < 0:
        raise ValueError('Invalid leaderboard filter')
    totals, coverage = records(archive,today,period)
    group = list(totals[role].values())
    names = archive.person_names() if group and role != 'horse' else None

    def display(row):
        return {**row,'name':names.resolve(row['id'],row['name']) if names else row['name']}

    leaders = {}
    for column in ('starts','wins','money'):
        known = [row for row in group if row[column] is not None]
        if known:
            best = max(row[column] for row in known)
            tied = [row for row in known if row[column] == best]
            leaders[column] = {**display(min(tied,key=lambda r:(browse.name_key(r['name']),r['id']))),
                               'ties':len(tied)}
    eligible = [row for row in group if row[metric] is not None
                and (metric != 'rate' or row['starts'] >= RATE_MIN_STARTS)]
    eligible.sort(key=lambda r:(-r[metric],browse.name_key(r['name']),r['id']))
    limit = 30
    offset = min(offset, max(0,(len(eligible)-1)//limit*limit))
    rows = []
    for index,row in enumerate(eligible[:offset+limit]):
        if index == 0 or row[metric] != eligible[index-1][metric]:
            rank = index+1
        if index >= offset:
            rows.append({**display(row),'rank':rank})
    return dict(rows=rows, total=len(eligible), limit=limit, offset=offset, leaders=leaders,
                coverage=coverage, role=role, metric=metric, period=period, rate_min_starts=RATE_MIN_STARTS)
