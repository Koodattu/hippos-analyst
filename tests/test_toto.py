"""Synthetic contract and safety tests for optional Toto enrichment."""
import copy
import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from hippos_analyst import api, collector, store, toto
from hippos_analyst.server import Archive
import test_collector as fixtures
from test_collector import DAY, HORSE_ID, response


class TotoTests(unittest.TestCase):
    seed = fixtures.CollectorTests.seed
    fetch = fixtures.CollectorTests.fetch
    run_worker = fixtures.CollectorTests.run_worker
    tearDown = fixtures.CollectorTests.tearDown
    # Reuse the Hippos fixture setup, not its inherited test suite.
    def setUp(self):
        fixtures.CollectorTests.setUp(self)
        self.clock.now = datetime.fromisoformat(DAY + "T08:00:00+00:00").timestamp()
        self.run_worker()
        self.calls.clear()
        # Keep the provider's event date and the fake clock consistent.
        self.start = self.clock() + 20000
        self.cards = {'collection':[{'cardId':101,'country':'FI','raceType':'TROT','meetDate':DAY,
                                    'trackAbbreviation':'H','trackName':'Vermo','cancelled':False}]}
        self.races = {'collection':[{'cardId':101,'raceId':202,'number':1,'startTime':int(self.start*1000),
                                    'distance':2100,'raceStatus':'OPEN'}]}
        # The Hippos fixture runner has no distance: add a real participant distance.
        with self.db:
            self.db.execute("UPDATE entries SET data=json_set(data,'$.distance',2100)")
        self.runners = {'collection':[{'raceId':202,'runnerId':303,'horseName':'Test Horse','startNumber':7,
                                      'distance':2100,'scratched':False,'ownerHomeTown':'DO NOT STORE',
                                      'latestVaccination':'DO NOT STORE'}]}
        self.pools = {'collection':[{'cardId':101,'poolId':404,'poolType':'VOI','poolStatus':'CONNECTED',
                                    'races':[{'raceId':202,'raceNumber':1}]}]}
        self.odds = {'poolId':404,'poolType':'VOI','updated':int(self.clock()*1000),
                     'odds':[{'runnerNumber':7,'probable':1009,'amount':1600}], 'netPool':16146}
        self.toto_payloads = {'/cards/date/'+DAY:self.cards,'/card/101/races':self.races,
                              '/race/202/runners':self.runners,'/race/202/pools':self.pools,
                              '/pool/404/odds':self.odds}

    def collect(self, **kwargs):
        def fetch(key):
            self.calls.append((key,self.clock()))
            return response(self.toto_payloads[toto.endpoint(key)])
        args = dict(provider='toto',max_requests=20,delay=60,daily_budget=200,fetch=fetch,
                    clock=self.clock,sleep=self.clock.sleep,emit=lambda _:None)
        args.update(kwargs)
        return collector.run(self.db,**args)

    def seed_toto(self, **kwargs):
        with self.db:
            return toto.seed(self.db,DAY,'H',['1'],**kwargs)

    def test_toto_end_to_end_separate_provenance_and_bounded_samples(self):
        self.seed_toto(interval=900)
        self.assertEqual(self.collect(),'idle')
        self.assertEqual(len(self.calls),5)
        result = Archive(self.db).race(DAY,'H','1')['toto']
        self.assertEqual(result['match_status'],'matched')
        self.assertEqual(result['runners'][0]['horse_id'],HORSE_ID)
        self.assertEqual(result['observations'][0]['data']['odds'][0]['probable'],1009)
        self.assertEqual(result['observations'][0]['phase'],'before_scheduled_start')
        self.assertEqual(self.db.execute('select placing from entries').fetchone()[0],'1')
        for i in range(2):
            self.clock.now = self.db.execute("select next_attempt from jobs where kind='toto_odds' and status='pending'").fetchone()[0]
            self.collect()
        self.assertEqual(self.db.execute('select count(*) from toto_observations').fetchone()[0],3)
        self.assertEqual(self.db.execute("select count(*) from jobs where path like 'toto:%' and status='pending'").fetchone()[0],0)
        self.assertEqual(self.seed_toto(),0)
        self.assertTrue(all(b[1]-a[1]>=60 for a,b in zip(self.calls,self.calls[1:])))
        bodies=' '.join(r[0] for r in self.db.execute("select body from snapshots where path like 'toto:%'"))
        self.assertNotIn('DO NOT STORE',bodies)
        self.assertNotIn('ownerHomeTown',bodies)
        self.assertNotIn('latestVaccination',bodies)

    def test_toto_hippos_worker_never_consumes_toto_queue(self):
        self.seed_toto()
        self.assertEqual(self.run_worker(),'idle')
        self.assertEqual(self.calls,[])

    def test_toto_no_name_only_or_partial_field_matches(self):
        self.seed_toto()
        self.runners['collection'][0]['startNumber']=8
        self.collect()
        r=toto.read_race(self.db,DAY,'H','1')
        self.assertEqual(r['match_status'],'unmatched')
        self.assertEqual(len(self.calls),3)
        self.assertEqual(r['observations'],[])

    def test_toto_name_and_distance_disagreement_are_not_merged(self):
        for change in ({'horseName':'Other Horse'},{'distance':2120}):
            r={**self.runners['collection'][0],**change}
            self.assertIsNone(toto.matched_runners(self.db,{'date':DAY,'track':'H','number':'1'},
                              toto.normalize('toto_runners',{'collection':[r]},{'race_id':'202'})))

    def test_toto_missing_or_ambiguous_card_stops_discovery(self):
        self.seed_toto()
        self.cards['collection'].append({**self.cards['collection'][0],'cardId':102})
        self.collect()
        self.assertEqual(len(self.calls),1)
        self.assertEqual(toto.read_race(self.db,DAY,'H','1')['note'],'card')

    def test_toto_changed_hippos_identity_hides_observations(self):
        self.seed_toto()
        self.collect()
        with self.db:
            self.db.execute("INSERT INTO horses VALUES('123','Different Horse',NULL,NULL,0)")
            self.db.execute("UPDATE entries SET horse_id='123'")
        self.assertEqual(toto.read_race(self.db,DAY,'H','1')['observations'],[])
        self.clock.now += 2000
        self.collect()
        self.assertEqual(self.db.execute('select count(*) from toto_observations').fetchone()[0],1)

    def test_toto_closed_historical_sample_is_not_training_input_or_rescheduled(self):
        self.seed_toto()
        self.races['collection'][0]['startTime']=int((self.clock()-10)*1000)
        self.races['collection'][0]['raceStatus']='OFFICIAL'
        self.pools['collection'][0]['poolStatus']='OFFICIAL'
        self.collect()
        self.assertEqual(toto.read_race(self.db,DAY,'H','1')['observations'][0]['phase'],'after_scheduled_start')
        self.assertEqual(toto.coverage(self.db)['pending'],0)

    def test_toto_unknown_pool_status_never_schedules_more_samples(self):
        self.seed_toto()
        self.pools['collection'][0]['poolStatus']='UNKNOWN'
        self.collect()
        self.assertEqual(toto.coverage(self.db)['observations'],1)
        self.assertEqual(toto.coverage(self.db)['pending'],0)

    def test_toto_scratched_runner_can_omit_probable_without_losing_observation(self):
        self.seed_toto(samples=1)
        self.runners['collection'][0]['scratched']=True
        del self.odds['odds'][0]['probable']
        self.assertEqual(self.collect(),'idle')
        result=toto.read_race(self.db,DAY,'H','1')
        self.assertIsNone(result['observations'][0]['data']['odds'][0]['probable'])
        self.assertTrue(result['runners'][0]['scratched'])
        self.assertIsNone(self.db.execute('select paused_reason from control').fetchone()[0])

    def test_toto_invalid_types_ids_units_and_duplicates_fail_closed(self):
        for payload in ({**self.odds,'poolId':405},{**self.odds,'updated':123},
                        {**self.odds,'odds':[{'runnerNumber':7,'probable':True}]},
                        {**self.odds,'odds':[{'runnerNumber':7,'probable':None}]},
                        {**self.odds,'odds':[{'runnerNumber':7,'probable':'1009'}]},
                        {**self.odds,'odds':[{'runnerNumber':7,'probable':-1}]},
                        {**self.odds,'odds':self.odds['odds']*2}):
            with self.subTest(payload=payload),self.assertRaises(api.SchemaError):
                toto.normalize('toto_odds',payload,{'pool_id':'404'})
        r=copy.deepcopy(self.runners);r['collection'][0]['scratched']='false'
        with self.assertRaises(api.SchemaError): toto.normalize('toto_runners',r,{'race_id':'202'})
        c=copy.deepcopy(self.cards);c['collection'][0]['meetDate']='2025-10-21'
        with self.assertRaises(api.SchemaError): toto.normalize('toto_cards',c,{'date':DAY})

    def test_toto_schema_error_pauses_and_preserves_prior_observation(self):
        self.seed_toto(interval=900)
        self.collect()
        self.clock.now+=900
        self.odds['odds'][0]['runnerNumber']=99
        self.assertEqual(self.collect(),'paused')
        self.assertEqual(self.db.execute('select count(*) from toto_observations').fetchone()[0],1)
        self.assertTrue(self.db.execute('select paused_reason from control').fetchone()[0])
        self.assertTrue(toto.read_race(self.db,DAY,'H','1')['collection_failed'])
        self.assertEqual(toto.coverage(self.db)['failed'],1)

    def test_toto_rate_limit_cooldown_and_global_budget(self):
        self.seed_toto()
        self.assertEqual(self.collect(daily_budget=3),'budget') # Hippos fixture used three.
        self.assertEqual(self.calls,[])
        self.assertEqual(self.collect(fetch=lambda _:api.Response(429,headers={'retry-after':'120'})),'paused')
        count=self.db.execute('select count(*) from requests').fetchone()[0]
        self.collect()
        self.assertEqual(self.db.execute('select count(*) from requests').fetchone()[0],count)
        self.assertEqual(self.db.execute('select paused_until from control').fetchone()[0],self.clock()+120)

    def test_toto_daily_cap_counts_research_and_survives_restart(self):
        self.seed_toto()
        with self.db:
            for _ in range(40):self.db.execute("insert into requests(path,started_at,outcome) values('toto-research:/test',?,'research_ok')",(self.clock(),))
        self.assertEqual(self.collect(),'budget')
        self.assertEqual(self.calls,[])

    def test_toto_transient_failure_never_retries_in_same_run(self):
        self.seed_toto()
        self.assertEqual(self.collect(fetch=lambda _:api.Response(503,headers={'retry-after':'180'})),'retry')
        self.assertEqual(self.db.execute("select count(*) from requests where path like 'toto:%'").fetchone()[0],1)
        self.assertEqual(self.collect(),'retry')
        self.assertEqual(self.calls,[])

    def test_toto_limits_and_network_allowlist(self):
        for key in ('https://evil.example/','toto:/wager','toto:/race/1/runners?x=1','toto:/race/../runners'):
            with self.assertRaises(ValueError):toto.endpoint(key)
        with self.assertRaises(ValueError):self.collect(delay=59)
        with self.assertRaises(ValueError):self.collect(daily_budget=201)
        with self.assertRaises(ValueError):self.seed_toto(samples=4)
        with self.assertRaises(ValueError):self.seed_toto(interval=60)


    def test_toto_fetch_is_read_only_uses_shared_header_and_caps_response(self):
        opened = MagicMock()
        reply = opened.open.return_value.__enter__.return_value
        reply.status = 200
        reply.headers = {'Content-Type':'application/json'}
        reply.read.return_value = b'{"collection":[]}'
        with patch('hippos_analyst.toto.build_opener', return_value=opened):
            result = toto.fetch('toto:/race/202/runners@2')
        request = opened.open.call_args.args[0]
        self.assertEqual(request.full_url,'https://www.veikkaus.fi/api/toto-info/v1/race/202/runners')
        self.assertEqual(request.get_method(),'GET')
        self.assertEqual(request.get_header('X-esa-api-key'),'ROBOT')
        self.assertIsNone(request.data)
        self.assertEqual(result.json(),{'collection':[]})
        reply.read.assert_called_once_with(api.MAX_RESPONSE_BYTES+1)
        reply.read.return_value = b'x'*(api.MAX_RESPONSE_BYTES+1)
        with patch('hippos_analyst.toto.build_opener', return_value=opened),self.assertRaises(api.SchemaError):
            toto.fetch('toto:/race/202/runners')

    def test_toto_redirect_and_refusal_persist_global_stop(self):
        for status in (301,302,307,401,403):
            with self.subTest(status=status):
                self.seed_toto()
                self.assertEqual(self.collect(fetch=lambda _:api.Response(status)),'paused')
                self.assertEqual(self.run_worker(),'paused')
                # Independent fixture per status, never clearing a live pause.
                self.tearDown()
                self.setUp()
