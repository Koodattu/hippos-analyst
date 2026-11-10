import copy
import importlib.util
import json
import math
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from hippos_analyst import prediction_features as f, predictions as p, prediction_store as ps, store, api


def group(day='2026-08-01', number='1'):
    race = dict(date=day,trackCode='H',startNumber=number,startType='TOTO',monte=False,
                eventType='LAMMINVERISET',startForm='RYHMALAHTO',baseDistance='2100',status='2',plannedTime='18:00')
    entries = [dict(horseId=str(i),programNumber=str(i),absent=False,placing=str(i),
                    distance='2100',lane=str(i),driverId=str(i+10),trainerId=str(i+20),
                    gallop=False,kilometerTime='1.17.8',winOdds=str(i+1)) for i in (1,2)]
    return dict(key=(day,'H',number),race=race,entries=entries,signature=f.signature(race,entries),
                field_at=f.scheduled_at(race)-3600,request_id=1)


class FeatureTests(unittest.TestCase):
    def test_current_outcomes_odds_and_career_totals_cannot_change_features(self):
        before, target = group(), group('2026-08-02')
        original = f.build_features(copy.deepcopy([before,target]))[0][-1]['x']
        for e in target['entries']:
            e.update(placing='2',winOdds='1000',kilometerTime='1.01.0',price='999999',
                     horsePriceSum='999999',gallop=True,record='1.00.0')
        self.assertEqual(original,f.build_features([before,target])[0][-1]['x'])

    def test_same_day_and_future_races_never_supply_history(self):
        groups = [group(),group(number='2'),group('2026-08-02'),group('2026-08-03')]
        built,_=f.build_features(groups)
        self.assertEqual([g['x'][0][7] for g in built],[0,0,2,3])
        changed=copy.deepcopy(groups)
        changed[-1]['entries'][0]['placing']='2'
        self.assertEqual(built[2]['x'],f.build_features(changed)[0][2]['x'])

    def test_unknown_results_ties_and_other_disciplines_excluded(self):
        for mutation, reason in [(lambda g:g['entries'][0].update(placing='101'),'unknown_placing'),
                                  (lambda g:g['entries'][1].update(placing='1'),'winner_not_unique'),
                                  (lambda g:g['race'].update(monte=True),'unsupported_type'),
                                  (lambda g:g['race'].update(status='0'),'unsettled_status')]:
            g=group();mutation(g)
            self.assertEqual(f.result_reason(g['race'],g['entries']),reason)

    def test_time_parser_and_missing_history(self):
        self.assertEqual(f.kilometre_seconds('1.17.8'),77.8)
        for value in ['1.99.0','17,8','hll',None]:self.assertIsNone(f.kilometre_seconds(value))
        g=f.build_features([group()])[0][0]
        self.assertEqual(g['x'][0][7:10],[0,0,-1])

    def test_signature_tracks_field_changes_not_results_or_names(self):
        g=group();e=g['entries']
        e[0].update(placing='3',horseName='different spelling',price='100')
        self.assertEqual(g['signature'],f.signature(g['race'],e))
        e[0]['absent']=True
        self.assertNotEqual(g['signature'],f.signature(g['race'],e))

    def test_chronological_splits_keep_dates_together(self):
        groups=[group((date(2026,5,1)+timedelta(days=i//5)).isoformat(),str(i%5+1)) for i in range(300)]
        splits=p.chronological_split(groups)
        ranges=[{g['key'][0] for g in v} for v in splits.values()]
        for a,b in zip(ranges,ranges[1:]):self.assertLess(max(a),min(b))
        self.assertEqual(sum(map(len,splits.values())),300)

    def test_metrics_softmax_and_market(self):
        g=f.build_features([group()])[0][0]
        probs=p.softmax([1000,1000])
        self.assertEqual(probs,[.5,.5])
        metrics=p.metrics([g],[probs])
        self.assertAlmostEqual(metrics['log_loss'],math.log(2))
        self.assertEqual(metrics['brier'],.5)
        self.assertEqual(metrics['top_pick_rate'],.5)
        self.assertAlmostEqual(sum(p.market_probs(g)),1)
        g['starters'][0]['winOdds']=None
        self.assertIsNone(p.market_probs(g))

    def test_forecast_cutoff_staleness_and_results(self):
        g=f.build_features([group('2026-11-11')])[0][0]
        g['race']['status']='0'
        for e in g['entries']:e['placing']='0'
        report={'splits':{'calibration':{'end':'2026-10-01'}}}
        now=f.scheduled_at(g['race'])-1800
        self.assertTrue(p.forecast_eligible(g,report,now))
        self.assertFalse(p.forecast_eligible(g,report,now+1700))
        g['field_at']=now-86401
        self.assertFalse(p.forecast_eligible(g,report,now))
        g['field_at']=now;g['entries'][0]['placing']='1'
        self.assertFalse(p.forecast_eligible(g,report,now))


class PersistenceTests(unittest.TestCase):
    def test_immutable_forecasts_field_invalidation_and_no_archive_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'archive.sqlite3'
            archive=store.connect(path)
            output=ps.connect(path)
            try:
                g=f.build_features([group('2026-11-11')])[0][0]
                report={'splits':{'train':{'end':'2026-08-01'},'calibration':{'end':'2026-10-01'}},'test':{}}
                stamp=g['field_at']+10
                with output:
                    ps.save(output,'v1',g,[.6,.4],'forecast',1,stamp,report)
                    ps.save(output,'v1',g,[.1,.9],'forecast',1,stamp+1,report)
                    ps.save(output,'v2',g,[.2,.8],'backtest',2,stamp+2,report)
                data=ps.read_race(archive,g['race'],g['entries'],stamp+2)
                self.assertEqual(data['runners'][0]['probability'],.6)
                self.assertEqual(data['mode'],'forecast')
                self.assertEqual(output.execute('select count(*) from predictions').fetchone()[0],2)
                self.assertEqual(archive.execute('select count(*) from requests').fetchone()[0],0)
                g['entries'][0]['driverId']='999'
                self.assertEqual(ps.read_race(archive,g['race'],g['entries'],stamp)['status'],'changed_field')
            finally:
                archive.close();output.close()

    def test_source_membership_and_snapshot_are_respected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'archive.sqlite3';db=store.connect(path)
            try:
                g=group();day,track,n=g['key']
                for kind,records,context,pathkey in [
                    ('calendar',[dict(date=day,trackCode=track,canceled=False)],{'date':day},api.calendar_path(day)),
                    ('races',[g['race']],{'date':day,'track':track},api.races_path(day,track)),
                    ('runners',g['entries'],{'date':day,'track':track,'number':n},api.runners_path(day,track,n))]:
                    # Minimal request/snapshot records exercise read-only extraction, independent of parsers.
                    cur=db.execute('insert into snapshots(path,sha256,first_seen,body) values(?,?,?,?)',
                                   (pathkey,kind,1,json.dumps(records)))
                    db.execute("insert into requests(path,started_at,finished_at,outcome,snapshot_id) values(?,1,2,'ok',?)",(pathkey,cur.lastrowid))
                db.commit()
                self.assertEqual(len(f.read_groups(db)),1)
                snap=p.snapshot(path)
                db.execute("update snapshots set body='[]' where path=?",(api.calendar_path(day),));db.commit()
                self.assertEqual(f.read_groups(db),[])
                self.assertEqual(len(f.read_groups(snap)),1)
                snap.close()
            finally:db.close()


@unittest.skipUnless(importlib.util.find_spec('catboost'),'Optional ML environment required')
class CatBoostIntegrationTests(unittest.TestCase):
    def test_real_grouped_training_serialization_and_prediction(self):
        from catboost import CatBoostRanker
        groups,_=f.build_features([group('2026-08-01'),group('2026-08-02'),group('2026-08-03')])
        model=CatBoostRanker(loss_function='QuerySoftMax',iterations=3,depth=2,thread_count=2,allow_writing_files=False)
        model.fit(p.pool(groups),verbose=False)
        with tempfile.TemporaryDirectory() as temp:
            path=str(Path(temp)/'model.cbm');model.save_model(path)
            loaded=CatBoostRanker();loaded.load_model(path)
            expected=p.scores_for(model,groups)
            actual=p.scores_for(loaded,groups)
            self.assertEqual(expected,actual)
            self.assertTrue(all(abs(sum(p.softmax(s))-1)<1e-9 for s in actual))
