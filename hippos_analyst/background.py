"""Standalone archive worker. Opt into continuous operation with --continuous."""

import argparse
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import collector, maintenance, store


def run(database, *, continuous=False, delay=30, daily_budget=200,
        clock=time.time, sleep=time.sleep, fetch=None, emit=print):
    """Use the same lock/ledger as manual collection; never clear stops or jobs."""
    if not 15 <= delay <= 3600 or not 1 <= daily_budget <= 500:
        raise ValueError('Use 15–3600 second spacing and a 1–500 daily budget')
    with collector.worker_lock(database):
        db = store.connect(database)
        try:
            while True:
                today = datetime.fromtimestamp(clock(), ZoneInfo('Europe/Helsinki')).date().isoformat()
                before = db.execute('SELECT count(*) FROM requests').fetchone()[0]
                emit(f'Maintenance started for Helsinki date {today}')
                outcome = maintenance.run(db, today, delay=delay, daily_budget=daily_budget,
                                          clock=clock, sleep=sleep, fetch=fetch, emit=emit)
                integrity = db.execute('PRAGMA quick_check').fetchone()[0]
                if integrity != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                    raise RuntimeError('SQLite integrity check failed')
                status = store.status(db)
                status.update(outcome=outcome, integrity=integrity, pid=os.getpid(),
                              continuous=continuous, delay=delay, daily_budget=daily_budget,
                              finished_at=datetime.fromtimestamp(clock(), timezone.utc).isoformat())
                target = Path(database).with_suffix('.background.json')
                temporary = target.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
                temporary.replace(target)
                emit(f'Maintenance finished: {outcome}; counts={json.dumps(status["counts"])}')
                if not continuous or outcome in ('paused', 'failed'):
                    return outcome
                now = clock()
                if outcome == 'budget':
                    next_run = now - now % 86400 + 86400
                elif outcome == 'retry':
                    if status['control']['paused_reason']:
                        return 'paused'
                    next_run = max(now + 60, status['control']['paused_until'])
                elif status['counts']['requests'] == before:
                    next_run = now + 60
                else:
                    # The collector enforces spacing across pass boundaries too.
                    next_run = now
                if next_run > now:
                    emit(f'Waiting until {datetime.fromtimestamp(next_run, timezone.utc).isoformat()}')
                while clock() < next_run:
                    if db.execute('SELECT paused_reason FROM control').fetchone()[0]:
                        emit('Worker stopped by persistent pause')
                        return 'paused'
                    sleep(min(30, next_run-clock()))
        except Exception:
            # Unexpected local errors must not cause repeated unattended requests.
            # Preserve any provider reason, cooldown and failed-job evidence.
            db.rollback()
            with db:
                db.execute("UPDATE control SET paused_reason=coalesce(paused_reason,?) WHERE id=1",
                           ('Background worker error; inspect local log before resuming',))
            raise
        finally:
            db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='data/hippos.sqlite3')
    parser.add_argument('--continuous', action='store_true', help='Keep collecting until stopped; no OS schedule')
    parser.add_argument('--delay', type=float, default=30)
    parser.add_argument('--daily-budget', type=int, default=200)
    args = parser.parse_args(argv)
    database = Path(args.db).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(database.with_suffix('.background.log'),
                                  maxBytes=2_000_000, backupCount=4, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s UTC %(levelname)s %(message)s')
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger = logging.getLogger('hippos.background')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        logger.info('Worker PID %s; continuous=%s; delay=%s; daily_budget=%s',
                    os.getpid(), args.continuous, args.delay, args.daily_budget)
        outcome = run(database, continuous=args.continuous, delay=args.delay,
                      daily_budget=args.daily_budget, emit=logger.info)
        return 2 if outcome in ('paused', 'retry', 'failed') else 0
    except RuntimeError as exc:
        if str(exc) == 'Another collector is using this database':
            logger.info('Skipped: another collector holds the worker lock')
            return 0
        logger.exception('Background worker stopped')
        return 2
    except Exception:
        logger.exception('Background worker stopped')
        return 2
    finally:
        logger.removeHandler(handler)
        handler.close()


if __name__ == '__main__':
    raise SystemExit(main())
