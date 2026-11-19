"""Current field metadata and daily leaderboard contributions for read-only pages."""

import json
from dataclasses import dataclass

from . import api, directory_index, prediction_features, race_results
from .browse import numeric


def head(db, path):
    row = db.execute("""SELECT s.body,q.finished_at FROM requests q JOIN snapshots s ON s.id=q.snapshot_id
        WHERE q.path=? AND q.outcome='ok' ORDER BY q.id DESC LIMIT 1""", (path,)).fetchone()
    return (json.loads(row[0]), row[1]) if row else ([], None)


@dataclass(slots=True)
class DailyStats:
    name: str | None = None
    starts: int = 0
    wins: int = 0
    podiums: int = 0
    money: float | None = None


def refresh_day(db, day):
    db.execute("DELETE FROM report_fields WHERE date=?", (day,))
    db.execute("DELETE FROM leaderboard_days WHERE date=?", (day,))
    totals = {}
    fields = []
    # Preserve the archive's tie order when two observations supply different display names.
    meetings = db.execute("SELECT m.track,m.canceled,list.body " + directory_index.listed_meetings(one_day=True)
                          + " ORDER BY m.start_time,m.track", {'calendar':api.calendar_path(day)})
    for track,canceled,body in meetings:
        for race in json.loads(body) if body else ():
            number = str(race['startNumber'])
            entries, fetched = head(db, api.runners_path(day, track, number))
            if fetched is None:
                continue
            known = any(race_results.has_result(e) for e in entries)
            competitive = known and not canceled and race.get('startType') in ('TOTO','PAIKALLIS') and str(race.get('status')) == '2'
            reason = 'canceled_meeting' if canceled else prediction_features.result_reason(race, entries)
            fields.append((day,track,number,fetched,len(entries),known,competitive,reason))
            if not competitive:
                continue
            for entry in sorted(entries, key=lambda e: str(e['programNumber'])):
                if entry.get('absent'):
                    continue
                place = race_results.outcome(entry)['place']
                prize = numeric(entry.get('price'))
                for role in ('horse','driver','trainer'):
                    identity = str(entry.get(role+'Id') or '').strip()
                    if identity in ('','0'):
                        continue
                    stats = totals.setdefault((role,identity), DailyStats())
                    if role != 'horse' and entry.get(role+'Name'):
                        stats.name = entry[role+'Name']
                    stats.starts += 1
                    stats.wins += place == 1
                    stats.podiums += place in (1,2,3)
                    if prize is not None:
                        stats.money = (stats.money or 0) + prize
    db.executemany("INSERT INTO report_fields VALUES(?,?,?,?,?,?,?,?)", fields)
    db.executemany("INSERT INTO leaderboard_days VALUES(?,?,?,?,?,?,?,?)",
                   ((day,role,identity,s.name,s.starts,s.wins,s.podiums,s.money)
                    for (role,identity),s in totals.items()))


def catch_up(db):
    latest, saved = db.execute("""SELECT (SELECT coalesce(max(id),0) FROM requests WHERE outcome='ok'),
        (SELECT value FROM maintenance_state WHERE name='reports_v1')""").fetchone()
    if saved is not None and int(saved) == latest:
        return
    if saved is None:
        days = db.execute('SELECT DISTINCT date FROM meetings ORDER BY date')
    else:
        days = db.execute("""SELECT DISTINCT json_extract(j.context,'$.date') FROM requests r
            JOIN jobs j ON j.path=r.path WHERE r.id>? AND r.outcome='ok' AND j.kind IN ('calendar','races','runners')""",
            (int(saved),))
    for day, in days:
        refresh_day(db, day)
    db.execute("INSERT OR REPLACE INTO maintenance_state VALUES('reports_v1',?)", (str(latest),))
