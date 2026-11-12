"""Bounded scheduled refreshes, profile discovery and contiguous history growth."""

import calendar
import json
import time
from datetime import date, timedelta

from . import api, collector, store

PROFILE_ROOTS_PER_DAY = 100
PROFILE_SEED_BATCH = 10


def refresh_interval(offset):
    if offset in (0,1):
        return 3600
    return 6*3600 if offset < 0 else 86400


def seed_history(db):
    """Advance from October 2026, never from an isolated older sample."""
    if db.execute("SELECT 1 FROM jobs WHERE status='pending' AND kind IN ('calendar','races','runners') "
                  "AND json_extract(context,'$.refresh_after') IS NULL LIMIT 1").fetchone():
        return {'queued': 0, 'reason': 'history_pending'}
    month = date(2026, 10, 1)
    empty = 0
    while True:
        days = [month + timedelta(days=n) for n in range(calendar.monthrange(month.year,month.month)[1])]
        jobs = db.execute("SELECT * FROM jobs WHERE kind IN ('calendar','races','runners') "
                          "AND json_extract(context,'$.date') BETWEEN ? AND ?", (days[0].isoformat(),days[-1].isoformat())).fetchall()
        # A queued refresh does not erase an earlier successful observation.
        # Newly discovered fields must still be collected before advancing.
        if any(j['last_success'] is None or j['status']=='failed' for j in jobs):
            return {'queued': 0, 'month': month.strftime('%Y-%m'), 'reason': 'month_pending'}
        known = {json.loads(j['context'])['date'] for j in jobs if j['kind']=='calendar'}
        missing = [day.isoformat() for day in days if day.isoformat() not in known]
        if missing:
            count = sum(store.enqueue(db,api.calendar_path(day),'calendar',{'date':day},100) for day in missing)
            return {'queued': count, 'month': month.strftime('%Y-%m'), 'reason': 'seeded'}
        meetings = db.execute('SELECT count(*) FROM meetings WHERE date BETWEEN ? AND ?',
                              (days[0].isoformat(),days[-1].isoformat())).fetchone()[0]
        empty = 0 if meetings else empty + 1
        if empty >= 12:
            return {'queued': 0, 'month': month.strftime('%Y-%m'), 'reason': 'twelve_empty_months'}
        month = (month-timedelta(days=1)).replace(day=1)


def prepare(db, today, now):
    """Offline planning, called inside the shared worker lock and transaction."""
    today = date.fromisoformat(api.iso_date(today))
    state = db.execute('SELECT * FROM control').fetchone()
    if state['paused_reason'] or state['paused_until'] > now:
        raise ValueError('Collection is paused or cooling down')
    if db.execute("SELECT 1 FROM jobs WHERE status='failed' LIMIT 1").fetchone():
        raise ValueError('Investigate failed jobs before scheduling more work')
    # Check the historical frontier before adding this wake-up's refresh work.
    history = seed_history(db)
    if history.get('reason') == 'twelve_empty_months':
        return {'refresh': 0, 'profiles': 0, 'history': history}
    refresh = 0
    for offset in range(-3, 8):
        day = (today+timedelta(days=offset)).isoformat()
        priority = 10+abs(offset)
        interval = refresh_interval(offset)
        refresh += store.enqueue_refresh(db,api.calendar_path(day),'calendar',{'date':day},priority,now,interval)
        children = db.execute("SELECT path,kind,context FROM jobs WHERE kind IN ('races','runners') "
                              "AND json_extract(context,'$.date')=?", (day,)).fetchall()
        for child in children:
            refresh += store.enqueue_refresh(db,child['path'],child['kind'],json.loads(child['context']),priority,now,interval)
    profiles = 0
    seeded = db.execute("SELECT value FROM maintenance_state WHERE name='profile_seed_day'").fetchone()
    count = db.execute("SELECT value FROM maintenance_state WHERE name='profile_seed_count'").fetchone()
    # An old same-day marker represents the previous policy's five roots, not zero.
    used = (int(count[0]) if count else 5) if seeded and seeded[0] == today.isoformat() else 0
    pending = db.execute("SELECT 1 FROM jobs WHERE kind IN ('profile','horse_photo') AND status='pending' LIMIT 1").fetchone()
    if not pending and used < PROFILE_ROOTS_PER_DAY:
        profiles = store.seed_profiles(db,limit=min(PROFILE_SEED_BATCH,PROFILE_ROOTS_PER_DAY-used),generations=2,priority=90)
        db.execute("INSERT INTO maintenance_state VALUES('profile_seed_day',?) "
                   "ON CONFLICT(name) DO UPDATE SET value=excluded.value", (today.isoformat(),))
        db.execute("INSERT INTO maintenance_state VALUES('profile_seed_count',?) "
                   "ON CONFLICT(name) DO UPDATE SET value=excluded.value", (str(used+profiles),))
    return {'refresh':refresh,'profiles':profiles,'history':history}


def run(db, today, *, max_requests=40, delay=30, daily_budget=200,
        clock=time.time, sleep=time.sleep, fetch=None, emit=print):
    """Caller holds worker_lock throughout all phases. No background child worker."""
    if not 4 <= max_requests <= 40:
        raise ValueError('Maintenance permits 4–40 requests per wake-up')
    if not collector.MIN_HIPPOS_DELAY <= delay <= 3600 or not 1 <= daily_budget <= 5000:
        raise ValueError(f'Maintenance requires {collector.MIN_HIPPOS_DELAY}–3600 second spacing and a 1–5000 daily budget')
    state = db.execute('SELECT * FROM control').fetchone()
    if state['paused_reason']:
        emit('Collection remains paused; no work scheduled.')
        return 'paused'
    if state['paused_until'] > clock():
        return 'retry'
    if db.execute("SELECT 1 FROM jobs WHERE status='failed' LIMIT 1").fetchone():
        return 'failed'
    now = clock()
    if db.execute('SELECT count(*) FROM requests WHERE started_at>=?',(now-now%86400,)).fetchone()[0] >= daily_budget:
        emit('Combined daily budget reached; no work scheduled.')
        return 'budget'
    with db:
        plan = prepare(db,today,now)
    emit(json.dumps(plan))
    if plan['history'].get('reason') == 'twelve_empty_months':
        with db:
            db.execute("UPDATE control SET paused_reason=? WHERE id=1",
                       ('Twelve empty historical months; investigate depth before resuming',))
        return 'paused'
    # Dedicated shares prevent a full refresh queue from starving profiles/history.
    refresh = max_requests//2
    profiles = max_requests//4
    for queue, limit in [('refresh',refresh),('profiles',profiles),('history',max_requests-refresh-profiles)]:
        emit(f'Processing {queue}: at most {limit} requests')
        result = collector.run(db,queue=queue,max_requests=limit,delay=delay,daily_budget=daily_budget,
                               clock=clock,sleep=sleep,fetch=fetch,emit=emit)
        if result not in ('idle','limit'):
            return result
    return 'limit'
