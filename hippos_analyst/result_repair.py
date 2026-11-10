"""Requeue old runner snapshots once, under the collector's existing limits."""

import json
import time
from collections import Counter

from . import api, store


def plan(db, enqueue=False, now=None):
    now = time.time() if now is None else now
    candidates = db.execute('''SELECT j.*,s.body,s.parser_version FROM jobs j
        JOIN requests q ON q.id=(SELECT max(id) FROM requests WHERE path=j.path AND outcome='ok')
        JOIN snapshots s ON s.id=q.snapshot_id WHERE j.kind='runners' ''').fetchall()
    outdated = [row for row in candidates if row['parser_version'] < api.RUNNER_PARSER_VERSION]
    queued = 0
    if enqueue:
        state = db.execute('SELECT * FROM control').fetchone()
        if state['paused_reason'] or state['paused_until']>now or db.execute("SELECT 1 FROM jobs WHERE status='failed' LIMIT 1").fetchone():
            raise ValueError('Resolve existing stop, cooldown or failed jobs before result repair')
        for row in outdated:
            entries = json.loads(row['body'])
            special = any(str(e.get('placing','')).isdigit() and int(e['placing'])>=100 for e in entries)
            priority = 20 if special else 30
            if row['status'] == 'done':
                queued += store.enqueue(db,row['path'],'runners',json.loads(row['context']),priority,refresh=True)
            elif row['status'] == 'pending':
                # Never change cooldowns, failed jobs, attempts, or the request ledger.
                db.execute('UPDATE jobs SET priority=min(priority,?) WHERE path=?',(priority,row['path']))
    return {'parser_version':api.RUNNER_PARSER_VERSION,'observed_fields':len(candidates),
            'current_fields':len(candidates)-len(outdated),'remaining_fields':len(outdated),
            'remaining_by_status':dict(Counter(row['status'] for row in outdated)), 'newly_queued':queued,
            'unretained_source_fields':[r[0] for r in db.execute("SELECT name FROM source_fields WHERE kind='runners' AND retained=0 ORDER BY name")]}
