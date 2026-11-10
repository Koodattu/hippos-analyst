import copy
import json
import unittest

from hippos_analyst import api, race_results, result_repair, prediction_features as f
from test_predictions import group
import test_collector as fixtures
from test_collector import DAY, RUNNERS


class ResultTests(unittest.TestCase):
    def test_disqualification_is_not_a_finishing_place_or_a_winner(self):
        r=race_results.outcome({'placing':'106','disqualifiedCode':'hlo'})
        self.assertEqual(r,{'kind':'disqualified','place':None,'code':'hlo','recorded_position':6})
        for code in ('hlo','hll','hpl','hel','hkä','hrp','hva','hyl','k','future-code'):
            self.assertFalse(race_results.winner({'placing':'1','disqualifiedCode':code}))
        self.assertEqual(race_results.outcome({'placing':'106'})['kind'],'unknown')
        self.assertEqual(race_results.outcome({'placing':'0','disqualifiedCode':'K'})['kind'],'nonfinish')
        self.assertTrue(race_results.winner({'placing':'1='}))
        self.assertFalse(race_results.winner({'placing':'1','absent':True}))
        self.assertTrue(race_results.galloped({'gallop':False,'disqualifiedCode':'hpl'}))
        self.assertFalse(race_results.galloped({'gallop':False,'disqualifiedCode':'hyl'}))

    def test_disqualified_loser_keeps_race_and_history_without_bad_speed_or_rank(self):
        g=group();g['entries'][1].update(placing='102',disqualifiedCode='hlo')
        self.assertIsNone(f.result_reason(g['race'],g['entries']))
        built,_=f.build_features([g,group('2026-08-02')])
        self.assertEqual(built[0]['y'],[1,0])
        self.assertEqual(len(built[0]['starters']),2)
        self.assertEqual(built[1]['x'][1][7],1)
        self.assertEqual(built[1]['x'][1][12],1)
        self.assertEqual(built[1]['x'][1][14],-1)
        g['entries'][1]['disqualifiedCode']='new-unverified-code'
        self.assertEqual(f.result_reason(g['race'],g['entries']),'unknown_placing')

    def test_code_preservation_and_invalid_type(self):
        entry=copy.deepcopy(RUNNERS[0]);entry.update(placing='106',disqualifiedCode='hlo',originalDriverId=123,winOdds2='1.23',finishing='45',placementExpectations='RAHASIJA',hasEquipmentChanges=False,equipmentChangesText='')
        context={'date':DAY,'track':'H','number':'1'}
        self.assertEqual(api.normalize('runners',[entry],context)[0]['disqualifiedCode'],'hlo')
        self.assertEqual(api.normalize('runners',[entry],context)[0]['originalDriverId'],'123')
        self.assertEqual(api.normalize('runners',[entry],context)[0]['winOdds2'],'1.23')
        self.assertEqual(api.normalize('runners',[entry],context)[0]['placementExpectations'],'RAHASIJA')
        self.assertIs(api.normalize('runners',[entry],context)[0]['hasEquipmentChanges'],False)
        entry.pop('disqualifiedCode')
        self.assertIn('disqualifiedCode',api.normalize('runners',[entry],context)[0])
        for invalid in (1,True,[],{}):
            entry['disqualifiedCode']=invalid
            with self.assertRaises(api.SchemaError): api.normalize('runners',[entry],context)


class RepairTests(unittest.TestCase):
    setUp=fixtures.CollectorTests.setUp
    tearDown=fixtures.CollectorTests.tearDown
    seed=fixtures.CollectorTests.seed
    fetch=fixtures.CollectorTests.fetch
    run_worker=fixtures.CollectorTests.run_worker

    def test_parser_provenance_inventory_idempotent_repair_and_preserved_evidence(self):
        self.run_worker()
        path=api.runners_path(DAY,'H','1')
        old=self.db.execute('SELECT id FROM snapshots WHERE path=?',(path,)).fetchone()[0]
        self.db.execute('UPDATE snapshots SET parser_version=1 WHERE id=?',(old,));self.db.commit()
        before=self.db.execute('SELECT count(*) FROM requests').fetchone()[0]
        with self.db:
            self.assertEqual(result_repair.plan(self.db,True,now=self.clock())['newly_queued'],1)
            self.assertEqual(result_repair.plan(self.db,True,now=self.clock())['newly_queued'],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0],before)
        self.payloads[path]=copy.deepcopy(RUNNERS)
        self.payloads[path][0].update(placing='106',disqualifiedCode='hlo',newProviderField='unreviewed private text')
        self.run_worker()
        self.assertEqual(result_repair.plan(self.db)['remaining_fields'],0)
        self.assertEqual(self.db.execute('SELECT parser_version FROM snapshots WHERE id=?',(old,)).fetchone()[0],1)
        self.assertEqual(json.loads(self.db.execute('SELECT data FROM entries').fetchone()[0])['disqualifiedCode'],'hlo')
        self.assertEqual(self.db.execute("SELECT retained FROM source_fields WHERE name='disqualifiedCode'").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT retained FROM source_fields WHERE name='newProviderField'").fetchone()[0],0)
        self.assertNotIn('unreviewed private text',' '.join(r[0] for r in self.db.execute('SELECT body FROM snapshots')))

    def test_repair_does_not_clear_stops_cooldowns_or_retry_failed_jobs(self):
        self.run_worker()
        for sql in ["UPDATE control SET paused_reason='provider stop'", "UPDATE control SET paused_until=99999999999", "UPDATE jobs SET status='failed' WHERE kind='runners'"]:
            self.db.execute(sql)
            with self.assertRaises(ValueError): result_repair.plan(self.db,True,now=self.clock())
            self.db.rollback()
