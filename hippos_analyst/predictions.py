"""Offline CatBoost experiment and local prospective forecasting. No provider calls."""

import argparse
import json
import math
import random
import sqlite3
import time
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import prediction_features as features, prediction_store as persistence


def snapshot(database, destination=':memory:'):
    target = sqlite3.connect(destination)
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)) as source:
        source.backup(target)
    target.row_factory = sqlite3.Row
    return target


def softmax(scores, temperature=1):
    peak = max(scores)
    values = [math.exp((float(v)-peak)/temperature) for v in scores]
    return [v/sum(values) for v in values]


def chronological_split(groups):
    days = sorted({g['key'][0] for g in groups})
    if len(days) < 40 or len(groups) < 200:
        raise ValueError('Need at least 200 eligible races across 40 dates')
    a, b, c = [days[int(len(days)*fraction)] for fraction in (.6, .75, .85)]
    return {name: [g for g in groups if low <= g['key'][0] < high]
            for name, low, high in [('train', '', a), ('tune', a, b),
                                   ('calibration', b, c), ('test', c, '9999')]}


def pool(groups, labels=True):
    from catboost import Pool
    return Pool([row for g in groups for row in g['x']],
                label=[v for g in groups for v in g['y']] if labels else None,
                group_id=[i for i, g in enumerate(groups) for _ in g['x']],
                cat_features=features.CATEGORICAL, feature_names=features.FEATURES)


def scores_for(model, groups):
    if not groups:
        return []
    flat = model.predict(pool(groups, labels=False))
    result, pos = [], 0
    for g in groups:
        result.append([float(v) for v in flat[pos:pos+len(g['x'])]])
        pos += len(g['x'])
    return result


def metrics(groups, probabilities):
    losses, briers, hits, bins = [], [], [], defaultdict(list)
    for g, ps in zip(groups, probabilities):
        winner = g['y'].index(1)
        losses.append(-math.log(max(ps[winner], 1e-15)))
        briers.append(sum((p-y)**2 for p, y in zip(ps, g['y'])))
        tied = [i for i, p in enumerate(ps) if abs(p-max(ps)) < 1e-12]
        hits.append(1/len(tied) if winner in tied else 0)
        for p, y in zip(ps, g['y']):
            bins[min(int(p*10), 9)].append((p, y))
    if not losses:
        return {'races': 0}
    return {'races': len(losses), 'log_loss': sum(losses)/len(losses),
            'brier': sum(briers)/len(briers), 'top_pick_rate': sum(hits)/len(hits),
            'calibration': [{'lower': k/10, 'count': len(v), 'predicted': sum(p for p,y in v)/len(v),
                             'observed': sum(y for p,y in v)/len(v)} for k,v in sorted(bins.items())]}


def market_probs(group):
    odds = [features.number(e.get('winOdds')) for e in group['starters']]
    return softmax([-math.log(o) for o in odds]) if all(o > 0 for o in odds) else None


def comparison(groups, probabilities):
    uniform = [[1/len(g['x'])]*len(g['x']) for g in groups]
    form = [softmax(g['form_scores']) for g in groups]
    matched = [(g, p, market_probs(g)) for g,p in zip(groups, probabilities) if market_probs(g)]
    result = {'catboost': metrics(groups, probabilities), 'uniform': metrics(groups, uniform),
              'recent_form': metrics(groups, form),
              'market_final_retrospective': metrics([g for g,p,m in matched], [m for g,p,m in matched]),
              'catboost_market_cohort': metrics([g for g,p,m in matched], [p for g,p,m in matched])}
    # Paired uncertainty by meeting, not independent runner rows.
    meetings = defaultdict(list)
    for g, p, baseline in zip(groups, probabilities, form):
        w = g['y'].index(1)
        meetings[g['key'][:2]].append(-math.log(max(p[w],1e-15))+math.log(baseline[w]))
    blocks, rng = list(meetings.values()), random.Random(42)
    draws = []
    for _ in range(500):
        values = [v for block in rng.choices(blocks, k=len(blocks)) for v in block]
        draws.append(sum(values)/len(values))
    draws.sort()
    result['log_loss_delta_vs_form_95pct'] = [draws[12], draws[487]]
    return result


def forecast_eligible(group, report, now):
    start = features.scheduled_at(group['race'])
    return (features.supported(group['race']) and group['race'].get('status') == '0'
            and group['key'][0] > report['splits']['calibration']['end']
            and start is not None and start > now+300
            and group['field_at'] is not None and 0 <= now-group['field_at'] <= 86400
            and 2 <= len(group['starters']) and len({str(e['horseId']) for e in group['entries']}) == len(group['entries'])
            and not any(str(e.get('placing') or '0') != '0' for e in group['entries']))


def predict(database, artifact, model=None, now=None):
    from catboost import CatBoostRanker
    now = time.time() if now is None else now
    report = json.loads((artifact/'report.json').read_text(encoding='utf-8'))
    if report['features'] != features.FEATURES or report.get('feature_version',1) != features.FEATURE_VERSION:
        raise ValueError('Model feature schema mismatch; train a new model')
    if model is None:
        model = CatBoostRanker()
        model.load_model(str(artifact/'model.cbm'))
    db = snapshot(database)
    try:
        token = db.execute("SELECT coalesce(max(id),0) FROM requests WHERE outcome='ok'").fetchone()[0]
        groups, _ = features.build_features(features.read_groups(db))
    finally:
        db.close()
    selected = [g for g in groups if forecast_eligible(g, report, now)]
    scores = scores_for(model, selected)
    output = persistence.connect(database)
    try:
        with output:
            for g, values in zip(selected, scores):
                # Inference may take time; never publish a newly created past-start forecast.
                created = max(now, time.time())
                if forecast_eligible(g, report, created):
                    persistence.save(output, report['id'], g, softmax(values, report['temperature']),
                                     'forecast', token, created, report)
    finally:
        output.close()
    return len(selected)


def train(database):
    import catboost
    identity = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    artifact = Path(database).resolve().parent/'models'/identity
    artifact.mkdir(parents=True)
    db = snapshot(database, artifact/'archive.sqlite3')
    try:
        token = db.execute("SELECT coalesce(max(id),0) FROM requests WHERE outcome='ok'").fetchone()[0]
        groups, excluded = features.build_features(features.read_groups(db))
    finally:
        db.close()
    # Only completed days; never include today's still-changing meetings.
    today = datetime.now(features.ZoneInfo('Europe/Helsinki')).date().isoformat()
    eligible = [g for g in groups if not g['reason'] and g['key'][0] < today]
    splits = chronological_split(eligible)
    model = catboost.CatBoostRanker(loss_function='QuerySoftMax', iterations=400, depth=4,
                                   learning_rate=.04, l2_leaf_reg=5, random_seed=42,
                                   thread_count=4, allow_writing_files=False)
    model.fit(pool(splits['train']), eval_set=pool(splits['tune']),
              early_stopping_rounds=40, verbose=False)
    calibration = splits['calibration']
    scores = scores_for(model, calibration)
    temperatures = [.5, .65, .8, 1, 1.25, 1.5, 2, 3]
    temperature = min(temperatures, key=lambda t: metrics(calibration, [softmax(s,t) for s in scores])['log_loss'])
    test = splits['test']
    probabilities = [softmax(s, temperature) for s in scores_for(model, test)]
    report = {'id': identity, 'created_at': time.time(), 'catboost_version': catboost.__version__,
              'source_request': token, 'features': features.FEATURES, 'feature_version': features.FEATURE_VERSION, 'temperature': temperature,
              'trees': model.tree_count_, 'excluded': excluded, 'experimental': True,
              'evaluation': 'retrospective_event_time; latest backfilled records, not historical knowledge',
              'splits': {k: {'start': v[0]['key'][0], 'end': v[-1]['key'][0], 'races': len(v),
                             'runners': sum(len(g['x']) for g in v)} for k,v in splits.items()},
              'test': comparison(test, probabilities),
              'by_breed': {breed: metrics([g for g in test if g['race']['eventType']==breed],
                            [p for g,p in zip(test,probabilities) if g['race']['eventType']==breed])
                           for breed in sorted({g['race']['eventType'] for g in test})}}
    report['beats_simple_baselines'] = all(report['test']['catboost']['log_loss'] < report['test'][b]['log_loss']
                                           for b in ('uniform', 'recent_form'))
    model.save_model(str(artifact/'model.cbm'))
    (artifact/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    output = persistence.connect(database)
    try:
        with output:
            output.execute('INSERT INTO models VALUES(?,?,?,?)',
                           (identity, report['created_at'], str(artifact), json.dumps(report)))
            for g, p in zip(test, probabilities):
                persistence.save(output, identity, g, p, 'backtest', token, report['created_at'], report)
    finally:
        output.close()
    forecasts = predict(database, artifact, model)
    print(json.dumps({'artifact': str(artifact), 'splits': report['splits'], 'test': report['test'],
                      'beats_simple_baselines': report['beats_simple_baselines'], 'forecasts': forecasts}, indent=2))
    return artifact


def backtest(database, artifact, start, end):
    """Apply the frozen model only after every label-learning cutoff, without refitting."""
    from .prediction_results import fitting_cutoff
    report=json.loads((artifact/'report.json').read_text(encoding='utf-8'))
    if report['features'] != features.FEATURES or report.get('feature_version',1) != features.FEATURE_VERSION:
        raise ValueError('Model feature schema mismatch')
    if start <= fitting_cutoff(report) or start > end:
        raise ValueError('Backtest dates must be after training, tuning and calibration')
    from catboost import CatBoostRanker
    db=snapshot(database)
    try:
        token=db.execute("SELECT coalesce(max(id),0) FROM requests WHERE outcome='ok'").fetchone()[0]
        groups,_=features.build_features(features.read_groups(db))
    finally:
        db.close()
    now=time.time()
    today=datetime.now(features.ZoneInfo('Europe/Helsinki')).date().isoformat()
    selected=[g for g in groups if start <= g['key'][0] <= min(end,today) and not g['reason']
              and features.scheduled_at(g['race']) is not None and features.scheduled_at(g['race']) < now]
    if not selected:
        return {'races':0}
    model=CatBoostRanker();model.load_model(str(artifact/'model.cbm'))
    probabilities=[softmax(s,report['temperature']) for s in scores_for(model,selected)]
    output=persistence.connect(database)
    try:
        with output:
            for g,ps in zip(selected,probabilities):
                persistence.save(output,report['id'],g,ps,'backtest',token,now,report)
    finally:
        output.close()
    return {'races':len(selected),'fit_cutoff':fitting_cutoff(report),'metrics':comparison(selected,probabilities)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['train','predict','backtest'])
    parser.add_argument('--db', default='data/hippos.sqlite3')
    parser.add_argument('--model', type=Path, help='Versioned model artifact directory; required for predict')
    parser.add_argument('--watch', action='store_true', help='Recompute local forecasts on new observations every 60 seconds')
    parser.add_argument('--from', dest='start', type=features.date.fromisoformat)
    parser.add_argument('--to', dest='end', type=features.date.fromisoformat)
    args = parser.parse_args()
    if args.command == 'train':
        if args.watch:
            parser.error('Train once; use predict --watch to refresh forecasts')
        train(args.db)
        return
    if not args.model:
        parser.error('predict/backtest requires --model')
    if args.command == 'backtest':
        if args.watch or not args.start or not args.end:
            parser.error('backtest requires --from/--to and does not support --watch')
        print(json.dumps(backtest(args.db,args.model,args.start.isoformat(),args.end.isoformat()),indent=2))
        return
    last_token = None
    while True:
        with closing(sqlite3.connect(Path(args.db).resolve().as_uri()+'?mode=ro',uri=True)) as db:
            token = db.execute("SELECT max(id) FROM requests WHERE outcome='ok'").fetchone()[0]
        if token != last_token:
            print(json.dumps({'created_at': time.time(), 'eligible_forecasts': predict(args.db,args.model)}),flush=True)
            last_token = token
        if not args.watch:
            break
        time.sleep(60)


if __name__ == '__main__':
    main()
