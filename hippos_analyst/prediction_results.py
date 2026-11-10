"""Score immutable predictions against current verified results, without refitting."""

import json
import math
import sqlite3
from collections import Counter
from contextlib import closing

from . import prediction_features as features, prediction_store, predictions, race_results


def fitting_cutoff(report):
    # Tree fitting, early stopping and calibration all learn from labels.
    return max(report['splits'][part]['end'] for part in ('train', 'tune', 'calibration'))


def score_field(group, prediction, report):
    if group['key'][0] <= fitting_cutoff(report):
        return None, 'fitting_overlap'
    if group['signature'] != prediction['signature']:
        return None, 'changed_field'
    body = json.loads(prediction['body'])
    if body['mode'] == 'forecast':
        start = body.get('scheduled_at')
        if start is None or body['created_at'] >= start-300 or body['field_observed_at'] > body['created_at']:
            return None, 'invalid_forecast_time'
    entries = [e for e in group['entries'] if not e.get('absent')]
    quotes = {(str(r['horse_id']),str(r['number'])):r['probability'] for r in body['runners']}
    identities = [(str(e['horseId']),str(e['programNumber'])) for e in entries]
    if len(quotes) != len(body['runners']) or set(quotes) != set(identities):
        return None, 'identity_mismatch'
    ps = [quotes[key] for key in identities]
    if any(not isinstance(p,(int,float)) or not math.isfinite(p) or not 0 <= p <= 1 for p in ps) or abs(sum(ps)-1)>1e-6:
        return None, 'invalid_probabilities'
    winner = next(i for i,e in enumerate(entries) if race_results.winner(e))
    top = [i for i,p in enumerate(ps) if abs(p-max(ps))<1e-12]
    def runner(i):
        e=entries[i]
        return {'id':str(e['horseId']), 'number':str(e['programNumber']), 'name':e.get('horseName',''),
                'probability':ps[i], 'model_odds':1/ps[i] if ps[i]>0 else None}
    g = {**group, 'starters':entries, 'y':[int(i==winner) for i in range(len(entries))]}
    market = predictions.market_probs(g)
    market_top = [i for i,p in enumerate(market) if abs(p-max(market))<1e-12] if market else []
    return {'date':group['key'][0], 'track':group['key'][1], 'number':group['key'][2],
            'picks':[runner(i) for i in top], 'winner':runner(winner),
            'winner_rank':1+sum(p>ps[winner]+1e-12 for p in ps),
            'hit_credit':1/len(top) if winner in top else 0,
            'market_credit':(1/len(market_top) if winner in market_top else 0) if market else None,
            'log_loss':-math.log(max(ps[winner],1e-15)),
            'brier':sum((p-y)**2 for p,y in zip(ps,g['y'])),
            'market_log_loss':-math.log(max(market[winner],1e-15)) if market else None,
            'mode':body['mode'], 'created_at':body['created_at'], 'fit_cutoff':fitting_cutoff(report)}, None


def evaluate(archive_db, start, end, mode='backtest', offset=0):
    if mode not in ('backtest','forecast') or not 0 <= offset <= 10_000_000 or start>end:
        raise ValueError('Invalid prediction evaluation filter')
    filename = archive_db.execute('PRAGMA database_list').fetchone()[2]
    path = prediction_store.path_for(filename) if filename else None
    result={'rows':[], 'total':0, 'offset':0, 'limit':30, 'mode':mode, 'from':start, 'to':end,
            'model_id':None, 'fit_cutoff':None, 'summary':{}, 'excluded':{}}
    if path is None or not path.exists():
        return result
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        db.execute('BEGIN')
        model=db.execute('SELECT id,report FROM models ORDER BY created_at DESC LIMIT 1').fetchone()
        if model is None:
            return result
        report=json.loads(model['report'])
        result.update(model_id=model['id'],fit_cutoff=fitting_cutoff(report))
        saved={}
        for row in db.execute('''SELECT * FROM predictions WHERE model_id=? AND mode=?
            AND date BETWEEN ? AND ? ORDER BY id DESC''',(model['id'],mode,start,end)):
            saved.setdefault((row['date'],row['track'],row['number']),dict(row))
    rows,excluded=[],Counter()
    eligible=0
    for group in features.read_groups(archive_db):
        if not start <= group['key'][0] <= end:
            continue
        reason=features.result_reason(group['race'],group['entries'])
        if reason:
            excluded[reason]+=1
            continue
        eligible+=1
        prediction=saved.get(group['key'])
        if prediction is None:
            excluded['no_prediction']+=1
            continue
        row,reason=score_field(group,prediction,report)
        if reason:
            excluded[reason]+=1
        else:
            rows.append(row)
    rows.sort(key=lambda r:(r['date'],r['track'],int(r['number'])),reverse=True)
    market_rows=[r for r in rows if r['market_credit'] is not None]
    summary={'eligible':eligible, 'evaluated':len(rows), 'unscored':eligible-len(rows),
             'hits':sum(r['hit_credit'] for r in rows),
             'hit_rate':sum(r['hit_credit'] for r in rows)/len(rows) if rows else None,
             'log_loss':sum(r['log_loss'] for r in rows)/len(rows) if rows else None,
             'brier':sum(r['brier'] for r in rows)/len(rows) if rows else None,
             'market_races':len(market_rows),
             'market_hit_rate':sum(r['market_credit'] for r in market_rows)/len(market_rows) if market_rows else None,
             'market_log_loss':sum(r['market_log_loss'] for r in market_rows)/len(market_rows) if market_rows else None,
             'model_market_log_loss':sum(r['log_loss'] for r in market_rows)/len(market_rows) if market_rows else None}
    offset=min(offset,max(0,(len(rows)-1)//30*30))
    return {**result,'rows':rows[offset:offset+30], 'total':len(rows),'offset':offset,
            'summary':summary, 'excluded':dict(excluded)}
