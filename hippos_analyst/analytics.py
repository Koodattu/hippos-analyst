"""Local leaderboards over the latest published competitive race fields."""

from datetime import date

from . import api, browse


ROLES = ('horse', 'trainer', 'driver')
METRICS = ('starts', 'wins', 'podiums', 'money', 'rate')
RATE_MIN_STARTS = 10


def records(archive, today, period, role):
    end = date.fromisoformat(today)
    start = {'all': date.min, 'year': end.replace(month=1, day=1),
             'month': date.fromordinal(max(1,end.toordinal()-29))}[period].isoformat()
    # SQLite selects the bare name from the unique latest day with a name.
    rows = archive.db.execute("""WITH totals AS (
        SELECT id,name,max(CASE WHEN name IS NOT NULL THEN date END) AS named_date,
               sum(starts) AS starts,sum(wins) AS wins,sum(podiums) AS podiums,sum(money) AS money
        FROM leaderboard_days WHERE role=:role AND date BETWEEN :start AND :end GROUP BY id)
        SELECT t.id,coalesce(h.name,t.name,'') AS name,starts,wins,podiums,money,
               cast(wins AS REAL)/starts AS rate FROM totals t
        LEFT JOIN horses h ON :role='horse' AND h.id=t.id""", {'role':role,'start':start,'end':today})
    coverage = archive.db.execute("""SELECT count(*) AS races,min(date) AS first,max(date) AS last
        FROM report_fields WHERE competitive=1 AND date BETWEEN ? AND ?""", (start,today)).fetchone()
    return [dict(row) for row in rows], dict(coverage)


def leaderboard(archive, params):
    today = api.iso_date(params['today'])
    role, metric = params.get('role','horse'), params.get('metric','wins')
    period, offset = params.get('period','all'), int(params.get('offset',0))
    if role not in ROLES or metric not in METRICS or period not in ('all','year','month') or offset < 0:
        raise ValueError('Invalid leaderboard filter')
    group, coverage = records(archive,today,period,role)
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
