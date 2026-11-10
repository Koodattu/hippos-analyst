"""Separate, immutable prediction records; safe to read without CatBoost installed."""

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from .prediction_features import signature, supported, scheduled_at, result_reason


def path_for(database):
    return Path(database).with_suffix('.predictions.sqlite3')


def connect(database):
    db = sqlite3.connect(path_for(database), timeout=10)
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS models(id TEXT PRIMARY KEY,created_at REAL NOT NULL,
            artifact TEXT NOT NULL,report TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY,model_id TEXT NOT NULL,
            date TEXT NOT NULL,track TEXT NOT NULL,number TEXT NOT NULL,mode TEXT NOT NULL,
            signature TEXT NOT NULL,source_request INTEGER NOT NULL,created_at REAL NOT NULL,
            body TEXT NOT NULL,UNIQUE(model_id,date,track,number,mode,signature,source_request));
        CREATE INDEX IF NOT EXISTS predictions_race ON predictions(date,track,number,id DESC);
    ''')
    return db


def save(db, model_id, group, probabilities, mode, source_request, now, report):
    if len(probabilities) != len(group['starters']) or abs(sum(probabilities)-1) > 1e-6:
        raise ValueError('Invalid field probabilities')
    if any(not 0 <= p <= 1 for p in probabilities):
        raise ValueError('Invalid probability')
    body = {'model_id': model_id, 'mode': mode, 'created_at': now,
            'field_observed_at': group['field_at'], 'field_request_id': group['request_id'],
            'source_request': source_request, 'scheduled_at': scheduled_at(group['race']),
            'training_end': report['splits']['train']['end'],
            'calibration_end': report['splits']['calibration']['end'],
            'experimental': True, 'test_metrics': report['test'],
            'runners': [{'horse_id': str(e['horseId']), 'number': str(e['programNumber']),
                         'probability': float(p), 'history_count': int(row[7])}
                        for e, p, row in zip(group['starters'], probabilities, group['x'])]}
    db.execute('''INSERT OR IGNORE INTO predictions(model_id,date,track,number,mode,signature,
        source_request,created_at,body) VALUES(?,?,?,?,?,?,?,?,?)''',
        (model_id, *group['key'], mode, group['signature'], source_request, now,
         json.dumps(body, allow_nan=False)))


def read_race(archive_db, race, entries, now=None):
    if not supported(race):
        return {'status': 'unsupported'}
    if race.get('status') == '2' and result_reason(race,entries) == 'unknown_placing':
        return {'status':'unknown_result'}
    filename = archive_db.execute('PRAGMA database_list').fetchone()[2]
    path = path_for(filename) if filename else None
    if path is None or not path.exists():
        return {'status': 'unavailable'}
    now = time.time() if now is None else now
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)) as db:
            row = db.execute('''SELECT signature,body FROM predictions
                WHERE date=? AND track=? AND number=? ORDER BY (mode='forecast') DESC,id DESC LIMIT 1''',
                (race['date'], str(race['trackCode']), str(race['startNumber']))).fetchone()
    except sqlite3.Error:
        return {'status': 'unavailable'}
    if not row:
        return {'status': 'unavailable'}
    if row[0] != signature(race, entries):
        return {'status': 'changed_field'}
    body = json.loads(row[1])
    if body['mode'] == 'forecast' and now < (body['scheduled_at'] or now):
        if now-body['created_at'] > 86400 or now-body['field_observed_at'] > 86400:
            return {'status': 'stale'}
    return {'status': 'ready', **body}
