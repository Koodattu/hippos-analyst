"""Directory totals maintained in the same transaction as their source observations."""

import json

from . import api, race_results


def listed_meetings(one_day=False):
    calendar = "AND path=:calendar" if one_day else "AND path GLOB '/race/search/*'"
    return f"""
        FROM (SELECT max(id) AS id FROM requests WHERE outcome='ok' {calendar} GROUP BY path) latest
        JOIN requests c ON c.id=latest.id JOIN snapshots calendar ON calendar.id=c.snapshot_id
        CROSS JOIN json_each(calendar.body) item
        JOIN meetings m ON m.date=json_extract(item.value,'$.date')
            AND m.track=CAST(json_extract(item.value,'$.trackCode') AS TEXT)
        LEFT JOIN snapshots list ON list.id=(SELECT snapshot_id FROM requests
            WHERE outcome='ok' AND path='/race/'||m.date||'/'||m.track||'/races' ORDER BY id DESC LIMIT 1)
    """


def hidden_keys(day=None):
    races = "SELECT date,track,number FROM races"
    if day:
        races += " WHERE date=:day"
    return (races + " EXCEPT SELECT m.date,m.track,CAST(json_extract(r.value,'$.startNumber') AS TEXT) "
            + listed_meetings(bool(day)) + " CROSS JOIN json_each(list.body) r")


def entry_filter(db):
    if not db.execute("SELECT 1 FROM directory_hidden_races LIMIT 1").fetchone():
        return '1'
    return """rowid NOT IN (SELECT e.rowid FROM directory_hidden_races h CROSS JOIN entries e
              WHERE e.date=h.date AND e.track=h.track AND e.race_number=h.number)"""


class LatestName:
    def __init__(self):
        self.key = None
        self.name = None

    def step(self, name, fetched, day, track, race, number):
        key = (fetched, day)
        tie = (track, race, number)
        if self.key is None or key > self.key or key == self.key and tie < self.tie:
            self.key, self.tie, self.name = key, tie, name

    def finalize(self):
        return self.name


def field_ids(db, day, track, number):
    return db.execute("""SELECT horse_id,CAST(json_extract(data,'$.driverId') AS TEXT),
        CAST(json_extract(data,'$.trainerId') AS TEXT) FROM entries
        WHERE date=? AND track=? AND race_number=?""", (day, track, number)).fetchall()


def merge_field(db, key, records, now, *, new):
    """Append a new field, or advance timestamps for an identical observation."""
    if not records or db.execute("SELECT 1 FROM directory_hidden_races WHERE (date,track,number)=(?,?,?)", key).fetchone():
        return True
    if any(r.get(role+'Name') is not None and not isinstance(r[role+'Name'], str)
           for r in records for role in ('driver','trainer')):
        return False
    day = key[0]
    horse_ids = {str(r['horseId']) for r in records}
    prior_pairs = set()
    if new:
        # A horse's own history is short, even if its driver has thousands of starts.
        for horse, driver, trainer in db.execute(f"""SELECT horse_id,CAST(json_extract(data,'$.driverId') AS TEXT),
                CAST(json_extract(data,'$.trainerId') AS TEXT) FROM entries
                WHERE horse_id IN (SELECT value FROM json_each(?)) AND (date,track,race_number)!=(?,?,?)
                AND {entry_filter(db)}""", (json.dumps(sorted(horse_ids)), *key)):
            prior_pairs.update((('driver', driver, horse), ('trainer', trainer, horse)))
    groups = {}
    for runner in sorted(records, key=lambda r: str(r['programNumber'])):
        horse = str(runner['horseId'])
        known = race_results.has_result(runner)
        for role in ('horse','driver','trainer'):
            raw_id = runner.get(role+'Id')
            if raw_id is None or role != 'horse' and str(raw_id) in ('','0'):
                continue
            identity = str(raw_id)
            group = groups.setdefault((role,identity), {
                'name': None if role == 'horse' else str(runner.get(role+'Name') or '').strip(' '),
                'entries': 0, 'horses': set(), 'settled': False, 'open': False})
            group['entries'] += 1
            if new and role != 'horse' and (role,identity,horse) not in prior_pairs:
                group['horses'].add(horse)
            group['settled'] |= known
            group['open'] |= not known
    # For out-of-order or tied timestamps use the full deterministic name ordering.
    for role in ('horse','driver','trainer'):
        ids = [identity for kind,identity in groups if kind == role]
        if db.execute("""SELECT 1 FROM directory_activity WHERE role=? AND id IN
                (SELECT value FROM json_each(?)) AND fetched_at>=? LIMIT 1""",
                (role,json.dumps(ids),now)).fetchone():
            return False
    if not new:
        db.executemany("UPDATE directory_activity SET name=?,fetched_at=? WHERE role=? AND id=?",
                       ((g['name'],now,*key) for key,g in groups.items()))
        return True
    db.executemany("""INSERT INTO directory_activity(role,id,name,entries,horses,fetched_at,last_entry,last_result,open_dates)
        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(role,id) DO UPDATE SET
        name=excluded.name,entries=entries+excluded.entries,horses=horses+excluded.horses,
        fetched_at=excluded.fetched_at,last_entry=max(last_entry,excluded.last_entry),
        last_result=nullif(max(coalesce(last_result,''),coalesce(excluded.last_result,'')),''),
        open_dates=CASE WHEN excluded.open_dates='[]' OR EXISTS
            (SELECT 1 FROM json_each(directory_activity.open_dates) WHERE value=excluded.last_entry)
            THEN open_dates ELSE json_insert(open_dates,'$[#]',excluded.last_entry) END""",
        ((role,identity,g['name'],g['entries'],None if role=='horse' else len(g['horses']),now,day,
          day if g['settled'] else None,json.dumps([day] if g['open'] else []))
         for (role,identity),g in groups.items()))
    return True


def refresh(db, fields=None):
    if fields is not None and not fields:
        return
    membership = entry_filter(db)
    known = "result_known(absent,placing,json_extract(data,'$.disqualifiedCode'))"
    for column, role in enumerate(('horse', 'driver', 'trainer')):
        identity = 'horse_id' if role == 'horse' else f"CAST(json_extract(data,'$.{role}Id') AS TEXT)"
        index = 'entries_horse' if role == 'horse' else f'entries_{role}_names'
        args = {'role': role}
        where = f"{membership} AND {identity} NOT IN ('','0')" if role != 'horse' else membership
        if fields is not None:
            ids = {row[column] for row in fields if row[column] is not None}
            if not ids:
                continue
            args['ids'] = json.dumps(sorted(ids))
            subset = " IN (SELECT value FROM json_each(:ids))"
            db.execute("DELETE FROM directory_activity WHERE role=:role AND id" + subset, args)
            where += f" AND {identity}" + subset
        name = 'NULL' if role == 'horse' else f"""latest_name(trim(coalesce(json_extract(data,'$.{role}Name'),'')),
                    fetched_at,date,track,race_number,program_number)"""
        horses = 'NULL' if role == 'horse' else 'count(DISTINCT horse_id)'
        db.execute(f"""INSERT INTO directory_activity(role,id,name,entries,horses,fetched_at,last_entry,
                    last_result,open_dates)
            SELECT :role,{identity},{name},count(*),{horses},max(fetched_at),max(date),
                   max(date) FILTER (WHERE {known}), json_group_array(DISTINCT date) FILTER (WHERE NOT {known})
            FROM entries INDEXED BY {index} WHERE {where} GROUP BY {identity}""", args)


def reconcile_day(db, day):
    args = {'day': day, 'calendar': api.calendar_path(day)}
    current = {tuple(row) for row in db.execute(hidden_keys(day), args)}
    old = {tuple(row) for row in db.execute("SELECT * FROM directory_hidden_races WHERE date=?", (day,))}
    db.executemany("DELETE FROM directory_hidden_races WHERE date=? AND track=? AND number=?", old - current)
    db.executemany("INSERT INTO directory_hidden_races VALUES(?,?,?)", current - old)
    return [row for key in current ^ old for row in field_ids(db, *key)]


def catch_up(db):
    # Rebuild if an older collector wrote observations during a rolling upgrade.
    latest, saved = db.execute("""SELECT (SELECT coalesce(max(id),0) FROM requests WHERE outcome='ok'),
        (SELECT value FROM maintenance_state WHERE name='directory_index_v1')""").fetchone()
    if saved is not None and int(saved) == latest:
        return
    db.execute("DELETE FROM directory_hidden_races")
    db.execute("INSERT INTO directory_hidden_races " + hidden_keys())
    db.execute("DELETE FROM directory_activity")
    refresh(db)
    db.execute("INSERT OR REPLACE INTO maintenance_state VALUES('directory_index_v1',?)", (str(latest),))


def initialize(db):
    race_results.register_sql(db)
    db.create_aggregate('latest_name', 6, LatestName)
    with db:
        db.execute("BEGIN IMMEDIATE")
        catch_up(db)
