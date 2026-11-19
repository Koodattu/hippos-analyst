"""Bounded, read-only tables and previews for the racing workspace."""

import json
import re

from . import api
from .directory_index import LatestName


def numeric(value):
    match = re.fullmatch(r'(\d+(?:[.,]\d+)?)(?:[a-zA-Z]|=)*', str(value or '').strip())
    return float(match[1].replace(',', '.')) if match else None


def prepare(archive):
    archive.db.create_function('fold', 1, lambda s: (s or '').casefold(), deterministic=True)
    archive.db.create_function('number', 1, numeric, deterministic=True)
    archive.db.create_collation('FINNISH', lambda a,b: (name_key(a)>name_key(b))-(name_key(a)<name_key(b)))


def visible(archive, *, rowids=False):
    return f"""WITH visible AS (
        SELECT e.*, {'e.rowid AS entry_id,' if rowids else ''} result_known(e.absent,e.placing,json_extract(e.data,'$.disqualifiedCode')) AS result_known,
            result_win(e.absent,e.placing,json_extract(e.data,'$.disqualifiedCode')) AS result_win,
            result_place(e.absent,e.placing,json_extract(e.data,'$.disqualifiedCode')) AS result_place
        FROM entries e WHERE {archive.entry_filter()}) """


def options(params):
    offset = int(params.get('offset', '0'))
    query = params.get('q', '').strip()
    if not 0 <= offset <= 10_000_000 or len(query) > 200:
        raise ValueError('Invalid table query')
    today = api.iso_date(params['today'])
    return offset, query, today


def followed_activity(archive, params, today):
    """One snapshot for all followed profiles, including horses linked by current party records."""
    groups = {}
    for role in ('horse', 'driver', 'trainer', 'owner', 'breeder'):
        for identity in params.get(role, []):
            if not identity or len(identity) > 200:
                raise ValueError('Invalid followed profile')
            groups[role, identity] = dict(role=role, id=identity, upcoming=[], recent=[])
    horses = {identity for role, identity in groups if role == 'horse'}
    if len(horses) > 100 or len(groups) - len(horses) > 100:
        raise ValueError('Too many followed profiles')
    if not groups:
        return []
    names = archive.person_names()
    db = archive.db
    for horse in db.execute('SELECT id,name FROM horses WHERE id IN (SELECT value FROM json_each(?))',
                            (json.dumps(list(horses)),)):
        groups['horse', horse['id']]['name'] = horse['name']
    parties = {}
    for role in ('owner', 'breeder'):
        keys = [identity for kind, identity in groups if kind == role]
        for row in db.execute('SELECT horse_id,party_key,label FROM horse_parties WHERE role=? '
                              'AND party_key IN (SELECT value FROM json_each(?))', (role,json.dumps(keys))):
            key = (role, row['party_key'])
            groups[key]['name'] = row['label']
            parties.setdefault(row['horse_id'], []).append(key)

    source, args = visible(archive,rowids=True), []
    filters = ['v.horse_id IN (SELECT value FROM json_each(?))']
    args.append(json.dumps(list(horses.union(parties))))
    for role in ('driver', 'trainer'):
        ids = [identity for kind, identity in groups if kind == role]
        if ids:
            filters.append(f"CAST(json_extract(v.data,'$.{role}Id') AS TEXT) IN (SELECT value FROM json_each(?))")
            args.append(json.dumps(ids))
    # Keep only the latest five past starts for each followed subject. All future
    # fields are still classified individually (including already settled races).
    recent = set()
    subjects = {'horse': horses.union(parties)}
    for role in ('driver','trainer'):
        subjects[role] = [identity for kind,identity in groups if kind == role]
    for role, identities in subjects.items():
        column = 'horse_id' if role == 'horse' else f"CAST(json_extract(e.data,'$.{role}Id') AS TEXT)"
        for identity in identities:
            recent.update(row[0] for row in db.execute(source + f"""SELECT e.entry_id FROM visible e
                JOIN races r ON (r.date,r.track,r.number)=(e.date,e.track,e.race_number)
                WHERE {column}=? AND e.date<?
                ORDER BY e.date DESC,json_extract(r.data,'$.plannedTime') DESC,e.track DESC,
                         CAST(e.race_number AS INTEGER) DESC,CAST(e.program_number AS INTEGER) DESC LIMIT 5""",
                (identity,today)))
    query = source + """SELECT v.*, m.city, json_extract(m.data,'$.formattedTrackName') AS venue,
        json_extract(m.data,'$.canceled') AS canceled, json_extract(r.data,'$.plannedTime') AS time
        FROM visible v JOIN meetings m USING(date,track)
        JOIN races r ON r.date=v.date AND r.track=v.track AND r.number=v.race_number
        WHERE (v.date>=? AND (""" + ' OR '.join(filters) + """)) OR v.entry_id IN (SELECT value FROM json_each(?))
        ORDER BY v.date DESC,time DESC,v.track DESC,CAST(v.race_number AS INTEGER) DESC,
                 CAST(v.program_number AS INTEGER) DESC"""
    settled_today = {tuple(row) for row in db.execute(
        """SELECT DISTINCT track,race_number FROM entries WHERE date=?
           AND result_known(absent,placing,json_extract(data,'$.disqualifiedCode'))""", (today,))}
    for row in db.execute(query, [today,*args,json.dumps(sorted(recent))]):
        entry = json.loads(row['data'])
        keys = [('horse', row['horse_id']), ('driver', str(entry.get('driverId'))),
                ('trainer', str(entry.get('trainerId'))), *parties.get(row['horse_id'], [])]
        upcoming = (row['date'] >= today and not row['result_known'] and
                    (row['date'] != today or (row['track'], row['race_number']) not in settled_today))
        buckets = [groups[key]['upcoming' if upcoming else 'recent'] for key in keys if key in groups
                   and (upcoming or len(groups[key]['recent']) < 5)]
        if not buckets:
            continue
        entry = names.entry(entry)
        start = {k: row[k] for k in ('date','track','race_number','time','horse_id','program_number','canceled')}
        start['venue'] = row['venue'] or row['city'] or row['track']
        start['data'] = {k: entry[k] for k in ('horseName','driverName','trainerName','distance','placing',
            'absent','disqualifiedCode','shortKilometerTime','kilometerTime','price') if k in entry}
        for bucket in buckets:
            bucket.append(start)
    for group in groups.values():
        group['upcoming'].reverse()
        if group['role'] in ('driver', 'trainer'):
            full_name = names.resolve(group['id'], None)
            if full_name:
                group['name'] = full_name
    return list(groups.values())


def order_by(params, columns, default):
    key = params.get('sort', '')
    direction = params.get('dir') or 'asc'
    if direction not in ('asc', 'desc') or key and key not in columns:
        raise ValueError('Invalid sort')
    if not key:
        return default
    expression = columns[key]
    return f'({expression}) IS NULL, {expression} {direction}, {default}'


def page(db, source, args, ordering, offset, limit=30, total=None):
    if total is None:
        total = db.execute(source + ' SELECT count(*) FROM filtered', args).fetchone()[0]
    offset = min(offset, max(0, (total - 1) // limit * limit))
    rows = db.execute(source + f' SELECT * FROM filtered ORDER BY {ordering} LIMIT ? OFFSET ?',
                      (*args, limit, offset))
    return {'rows': [dict(row) for row in rows], 'total': total, 'offset': offset, 'limit': limit}


FINNISH_ORDER = str.maketrans({'å':'{a','ä':'{b','ö':'{c'})


def name_key(value):
    return (value or '').casefold().translate(FINNISH_ORDER)


def directory_records(archive, kind, today):
    # Each server has its own cache. A successful observation commits with its request ID;
    # the token is read inside the same transaction as the records it identifies.
    token = (archive.db.execute("SELECT max(id) FROM requests WHERE outcome='ok'").fetchone()[0],
             archive.db.total_changes, today)
    cached = archive.browse_cache.get(kind) if archive.browse_cache is not None else None
    if cached and cached[0] == token:
        return cached[1]
    # Most archived subjects have only past starts. Inspect unsettled dates only
    # for subjects whose field extends to or beyond the requested day.
    dates = """CASE WHEN a.last_entry < :today THEN a.last_entry ELSE
        nullif(max(coalesce(a.last_result,''),coalesce((SELECT max(value) FROM json_each(a.open_dates)
            WHERE value < :today),'')),'') END AS last_date,
        CASE WHEN a.last_entry >= :today THEN (SELECT min(value) FROM json_each(a.open_dates)
            WHERE value >= :today) END AS next_date"""
    if kind == 'horses':
        rows = archive.db.execute(f"""SELECT h.*,coalesce(a.entries,0) AS entries,{dates},
                json_extract(p.data,'$.gender') AS gender,json_extract(p.data,'$.birthDate') AS birth_date,
                CAST(substr(:today,1,4) AS INTEGER)-CAST(substr(json_extract(p.data,'$.birthDate'),1,4) AS INTEGER) AS age
            FROM horses h LEFT JOIN directory_activity a ON a.role='horse' AND a.id=h.id
            LEFT JOIN horse_profiles p ON p.horse_id=h.id""", {'today':today})
        records = [dict(row) for row in rows]
    else:
        rows = archive.db.execute(f"""SELECT a.id,a.role,a.name,a.horses,a.entries,{dates},a.fetched_at
            FROM directory_activity a WHERE a.role IN ('driver','trainer')""", {'today':today})
        records = [dict(row) for row in rows]
        records.extend(dict(row) for row in archive.db.execute("""SELECT party_key AS id,role,label AS name,
            count(*) AS horses,NULL AS entries,NULL AS last_date,NULL AS next_date,max(p.fetched_at) AS fetched_at
            FROM horse_parties r JOIN horse_profiles p ON p.horse_id=r.horse_id GROUP BY role,party_key,label"""))
    if kind == 'people':
        names = archive.person_names()
        for row in records:
            if row['role'] in ('driver', 'trainer'):
                row['source_name'] = row['name']
                row['name'] = names.resolve(row['id'], row['name'])
    records.sort(key=lambda row:(name_key(row['name']),row.get('role',''),row['id']))
    if archive.browse_cache is not None:
        archive.browse_cache[kind] = (token,records)
    return records


def directory(archive, kind, params):
    prepare(archive)
    offset,query,today = options(params)
    role = params.get('role','all')
    activity_filter = params.get('activity','')
    if role not in ('all','driver','trainer','owner','breeder') or activity_filter not in ('','all','past','upcoming'):
        raise ValueError('Invalid directory filter')
    ages = {}
    for key in ('min_age','max_age'):
        if params.get(key):
            ages[key] = int(params[key])
            if not 0 <= ages[key] <= 60:
                raise ValueError('Invalid age')
    columns = ('name','breed','age','gender','entries','last_date','next_date') if kind=='horses' else ('name','role','horses','entries','last_date','next_date')
    sort = params.get('sort','')
    direction = params.get('dir') or 'asc'
    if sort and sort not in columns or direction not in ('asc','desc'):
        raise ValueError('Invalid sort')
    records = directory_records(archive,kind,today)
    term = query.casefold()
    def matches(row):
        if term not in (row['name'] or '').casefold() and term not in (row.get('source_name') or '').casefold():
            return False
        if kind=='horses':
            if any(params.get(key) and params[key] != row[key] for key in ('breed','gender')):
                return False
            if ages and row['age'] is None:
                return False
            if ages and row['age'] is not None and (row['age']<ages.get('min_age',0) or row['age']>ages.get('max_age',60)):
                return False
            return params.get('upcoming')!='1' or row['next_date'] is not None
        return (role=='all' or row['role']==role) and (activity_filter not in ('past','upcoming') or row['last_date' if activity_filter=='past' else 'next_date'] is not None)
    rows = [row for row in records if matches(row)]
    if sort:
        present = [row for row in rows if row[sort] is not None]
        missing = [row for row in rows if row[sort] is None]
        present.sort(key=lambda row:name_key(row[sort]) if isinstance(row[sort],str) else row[sort], reverse=direction=='desc')
        rows = present+missing
    total = len(rows)
    offset = min(offset,max(0,(total-1)//30*30))
    result = {'rows':rows[offset:offset+30],'total':total,'offset':offset,'limit':30}
    if kind=='horses':
        result['breeds'] = sorted({row['breed'] for row in records if row['breed']})
    return result


def activity(archive, params, limit=30):
    prepare(archive)
    offset, query, today = options(params)
    archive.db.create_function('person_name', 2, archive.person_names().resolve, deterministic=True)
    source, args = visible(archive), []
    role, identity = params.get('role', 'horse'), params.get('id', '')
    if not identity or role not in ('horse', 'driver', 'trainer'):
        raise ValueError('Invalid activity identity')
    if role == 'horse':
        condition = 'horse_id=?'
        if archive.db.execute('SELECT 1 FROM horses WHERE id=?', (identity,)).fetchone() is None:
            raise LookupError('Horse not found')
    else:
        condition = f"CAST(json_extract(v.data,'$.{role}Id') AS TEXT)=?"
    source += f""", scoped AS (SELECT v.*,m.city,m.data AS meeting_data,
        r.data AS race_data,json_extract(v.data,'$.horseName') AS horse_name,
        person_name(CAST(json_extract(v.data,'$.driverId') AS TEXT),json_extract(v.data,'$.driverName')) AS driver_name,
        person_name(CAST(json_extract(v.data,'$.trainerId') AS TEXT),json_extract(v.data,'$.trainerName')) AS trainer_name,
        json_extract(v.data,'$.distance') AS distance,
        result_known AS has_result,
        (v.date>=? AND NOT result_known) AS upcoming
        FROM visible v JOIN meetings m ON m.date=v.date AND m.track=v.track
        JOIN races r ON r.date=v.date AND r.track=v.track AND r.number=v.race_number WHERE {condition}) """
    args += [today, identity]
    identity_columns = ''
    if role != 'horse':
        archive.db.create_aggregate('latest_name',6,LatestName)
        identity_columns = f""",latest_name({role}_name,fetched_at,date,track,race_number,program_number) AS name,
            latest_name(json_extract(data,'$.{role}Name'),fetched_at,date,track,race_number,program_number) AS source_name,
            max(fetched_at) AS fetched_at"""
    summary = dict(archive.db.execute(source + """SELECT count(*) AS entries,count(DISTINCT horse_id) AS horses,
        coalesce(sum(has_result),0) AS results,
        coalesce(sum(result_win),0) AS wins,
        coalesce(sum(upcoming),0) AS upcoming""" + identity_columns + ' FROM scoped', args).fetchone())
    if role != 'horse' and not summary['entries']:
        raise LookupError('Person not found')
    person = None
    if role != 'horse':
        person = {'name':summary.pop('name'), 'source_name':summary.pop('source_name'), 'fetched_at':summary.pop('fetched_at'), 'id':identity, 'role':role}
    period = params.get('period') or ('upcoming' if summary['upcoming'] else 'history')
    if period not in ('upcoming', 'history', 'horses'):
        raise ValueError('Invalid period')
    total = None if query or params.get('track') or params.get('before') else (
        summary['horses'] if period == 'horses' else summary['upcoming'] if period == 'upcoming'
        else summary['entries']-summary['upcoming'])
    if period == 'horses':
        source += """, filtered AS (SELECT horse_id AS id,max(horse_name) AS name,count(*) AS entries,
            max(CASE WHEN date<? OR result_known THEN date END) AS last_date,
            min(CASE WHEN upcoming THEN date END) AS next_date FROM scoped
            WHERE instr(fold(horse_name),?)>0 GROUP BY horse_id)"""
        args += [today, query.casefold()]
        columns = {'name': 'fold(name) COLLATE FINNISH', 'entries': 'entries', 'last_date': 'last_date', 'next_date': 'next_date'}
        result = page(archive.db, source, args, order_by(params, columns, 'fold(name) COLLATE FINNISH,id'), offset, limit, total)
    else:
        source += ', filtered AS (SELECT * FROM scoped WHERE upcoming=? AND instr(fold(horse_name),?)>0'
        args += [int(period == 'upcoming'), query.casefold()]
        if params.get('before'):
            source += ' AND date<?'
            args.append(api.iso_date(params['before']))
        if params.get('track'):
            source += ' AND track=?'
            args.append(params['track'])
        source += ')'
        columns = {'date': 'date', 'name': 'fold(horse_name) COLLATE FINNISH', 'track': 'fold(city) COLLATE FINNISH',
                   'number': 'number(program_number)', 'distance': 'number(distance)',
                   'driver': "nullif(fold(driver_name),'') COLLATE FINNISH", 'trainer': "nullif(fold(trainer_name),'') COLLATE FINNISH",
                   'placing': 'result_place',
                   'time': 'CASE WHEN has_result THEN number(kilometer_time) END',
                   'prize': 'CASE WHEN has_result THEN number(prize) END'}
        columns['status'] = 'absent'
        default = f"date {'ASC' if period == 'upcoming' else 'DESC'},track,number(race_number),race_number,number(program_number),program_number"
        result = page(archive.db, source, args, order_by(params, columns, default), offset, limit, total)
        for row in result['rows']:
            for key in ('data', 'meeting_data', 'race_data'):
                row[key] = json.loads(row[key])
            row['data'] = archive.person_names().entry(row['data'])
    return {**result, 'period': period, 'summary': summary, 'person': person,
            'photo': archive.photo(role, identity)}


def preview(archive, params):
    identity = params.get('id', '')
    kind = params.get('kind', 'horse')
    if kind in ('owner', 'breeder'):
        result = archive.party(kind, identity)
        result['horses'] = result['horses'][:5]
        return result
    if kind in ('driver', 'trainer'):
        return activity(archive, {**params, 'role': kind}, limit=5)
    if kind != 'horse':
        raise ValueError('Invalid preview')
    result = archive.horse(identity, include_starts=False, include_family=False)
    # Race previews use the already loaded form, and never download whole histories.
    result['activity'] = activity(archive, {**params, 'role': 'horse', 'period': 'history'}, limit=5)
    return result
