import copy
import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hippos_analyst import prediction_results as results, prediction_store as persistence
from hippos_analyst import prediction_features as features, predictions, server
from test_predictions import group


def report():
    return {'id':'v1', 'features':features.FEATURES, 'feature_version':features.FEATURE_VERSION, 'test':{}, 'splits':{
        'train':{'end':'2026-07-01'}, 'tune':{'end':'2026-07-15'},
        'calibration':{'end':'2026-07-31'}}}


def saved(g, probabilities=(.7,.3), mode='backtest'):
    return {'signature':g['signature'], 'body':json.dumps({
        'mode':mode, 'created_at':g['field_at']+10, 'field_observed_at':g['field_at'],
        'scheduled_at':features.scheduled_at(g['race']),
        'runners':[{'horse_id':e['horseId'],'number':e['programNumber'],'probability':p}
                   for e,p in zip(g['entries'],probabilities)]})}


class ScoringTests(unittest.TestCase):
    def test_winner_probability_odds_rank_and_metrics(self):
        row,reason=results.score_field(group(),saved(group()),report())
        self.assertIsNone(reason)
        self.assertEqual(row['hit_credit'],1)
        self.assertEqual(row['winner_rank'],1)
        self.assertAlmostEqual(row['picks'][0]['model_odds'],1/.7)
        self.assertAlmostEqual(row['log_loss'],-math.log(.7))
        self.assertAlmostEqual(row['brier'],.18)
        g=group();g['entries'][0]['placing']='2';g['entries'][1]['placing']='1'
        row,_=results.score_field(g,saved(g),report())
        self.assertEqual(row['hit_credit'],0)
        self.assertEqual(row['winner_rank'],2)
        self.assertEqual(row['winner']['probability'],.3)
        row,_=results.score_field(g,saved(g,(.5,.5)),report())
        self.assertEqual(row['hit_credit'],.5)
        self.assertEqual(len(row['picks']),2)

    def test_all_learning_stages_must_precede_target_date(self):
        g=group()
        for stage in ('train','tune','calibration'):
            r=report();r['splits'][stage]['end']=g['key'][0]
            self.assertEqual(results.score_field(g,saved(g),r)[1],'fitting_overlap')
            r['splits'][stage]['end']='2026-08-02'
            self.assertEqual(results.score_field(g,saved(g),r)[1],'fitting_overlap')

    def test_changed_field_identity_probabilities_and_late_forecast_rejected(self):
        g=group();s=saved(g);s['signature']='changed'
        self.assertEqual(results.score_field(g,s,report())[1],'changed_field')
        for mutate,reason in [
            (lambda b:b['runners'][0].update(horse_id='999'),'identity_mismatch'),
            (lambda b:b['runners'].append(b['runners'][0]),'identity_mismatch'),
            (lambda b:b['runners'][0].update(probability=float('nan')),'invalid_probabilities'),
            (lambda b:b['runners'][0].update(probability=.6),'invalid_probabilities'),
            (lambda b:b.update(created_at=b['scheduled_at']-300),'invalid_forecast_time'),
            (lambda b:b.update(field_observed_at=b['created_at']+1),'invalid_forecast_time')]:
            s=saved(g,mode='forecast');body=json.loads(s['body']);mutate(body);s['body']=json.dumps(body)
            self.assertEqual(results.score_field(g,s,report())[1],reason)

    def test_removing_all_target_and_future_outcomes_preserves_target_features(self):
        groups=[group('2026-08-01'),group('2026-08-02'),group('2026-08-03')]
        full=features.build_features(copy.deepcopy(groups))[0][1]['x']
        truncated=copy.deepcopy(groups[:2])
        truncated[-1]['race']['status']='0'
        for e in truncated[-1]['entries']:
            for key in ('placing','kilometerTime','gallop','winOdds'):
                e.pop(key,None)
        self.assertEqual(full,features.build_features(truncated)[0][-1]['x'])


class EvaluationTests(unittest.TestCase):
    def test_latest_version_once_summary_before_pagination_and_mode_separation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'archive.sqlite3'
            archive=sqlite3.connect(path);output=persistence.connect(path)
            groups,_=features.build_features([group(number=str(i)) for i in range(1,36)])
            try:
                with output:
                    output.execute('INSERT INTO models VALUES(?,?,?,?)',('v1',1,'unused',json.dumps(report())))
                    for g in groups:
                        persistence.save(output,'v1',g,[.1,.9],'backtest',1,g['field_at'],report())
                        persistence.save(output,'v1',g,[.7,.3],'backtest',2,g['field_at']+10,report())
                    persistence.save(output,'v1',groups[0],[.1,.9],'forecast',1,groups[0]['field_at']+10,report())
                with patch.object(features,'read_groups',return_value=groups):
                    page=results.evaluate(archive,'2026-08-01','2026-08-01',offset=30)
                    self.assertEqual(page['summary']['evaluated'],35)
                    self.assertEqual(page['summary']['hits'],35)
                    self.assertEqual(len(page['rows']),5)
                    self.assertEqual(page['total'],35)
                    forecast=results.evaluate(archive,'2026-08-01','2026-08-01',mode='forecast')
                    self.assertEqual(forecast['total'],1)
                    self.assertEqual(forecast['summary']['hits'],0)
                    self.assertEqual(forecast['summary']['unscored'],34)
                    self.assertEqual(forecast['excluded']['no_prediction'],34)
                    self.assertEqual(results.evaluate(archive,'2026-08-02','2026-08-02')['total'],0)
            finally:
                output.close();archive.close()

    def test_missing_sidecar_and_invalid_api_filters(self):
        archive=sqlite3.connect(':memory:')
        try:
            self.assertEqual(results.evaluate(archive,'2026-08-01','2026-08-02')['total'],0)
            valid={'from':['2026-08-01'],'to':['2026-08-02']}
            self.assertEqual(server.endpoint(SimpleNamespace(db=archive),'/api/predictions/results',valid)['total'],0)
            for extra in ({'mode':['all']},{'offset':['-1']},{'from':['invalid']},{'to':['2026-07-01']}):
                with self.assertRaises(ValueError):
                    server.endpoint(SimpleNamespace(db=archive),'/api/predictions/results',{**valid,**extra})
        finally:
            archive.close()

    def test_backtest_overlap_rejected_before_reading_archive_or_loading_model(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact=Path(temp);(artifact/'report.json').write_text(json.dumps(report()),encoding='utf-8')
            with patch.object(predictions,'snapshot') as snapshot:
                with self.assertRaisesRegex(ValueError,'after training, tuning and calibration'):
                    predictions.backtest('nonexistent.sqlite3',artifact,'2026-07-31','2026-08-01')
                snapshot.assert_not_called()
