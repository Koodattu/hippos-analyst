import json
import tempfile
import unittest
from pathlib import Path

from hippos_analyst import api, collector, store
from hippos_analyst.server import Archive, endpoint
from test_collector import Clock, response


def profile(value='100', name='Testihevonen'):
    return {'id': value, 'name': name, 'ownerName': 'Esimerkin Talli & Kumppanit',
            'breederName': 'Kasvattaja Ääni', 'birthDate': '2020-05-01',
            'birthDateAccurate': True, 'dead': False, 'gender': 'T',
            'sire': {'id': '200', 'name': 'Testi-isä', 'laboratoryNumber': 'DROP'},
            'dam': {'id': '', 'name': 'Nimetty emä'},
            'chipNo': 'DROP', 'latestVaccination': 'DROP', 'description': 'DROP',
            'photo': {'photoUrl': 'DROP'}, 'ownerAddress': 'DROP'}


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'profiles.sqlite3'
        self.db = store.connect(self.path)
        self.clock = Clock()
        self.calls = []

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def collect(self, data, **options):
        def fetch(path):
            self.calls.append(path)
            return response(data[path])
        return collector.run(self.db, max_requests=20, delay=30, daily_budget=200,
                             fetch=fetch, clock=self.clock, sleep=self.clock.sleep, emit=lambda _: None, **options)

    def save(self, payload, remaining=0, refresh=False):
        with self.db:
            store.enqueue_profile(self.db, payload['id'], remaining, refresh=refresh)
        return self.collect({api.profile_path(payload['id']): payload})

    def test_minimized_profile_contract_and_placeholders(self):
        raw = profile('7616196635396808820')
        parsed = api.normalize('profile', raw, {'id': raw['id']})[0]
        self.assertEqual(parsed['id'], raw['id'])
        self.assertNotIn('DROP', json.dumps(parsed))
        self.assertEqual(parsed['sire'], {'id': '200', 'name': 'Testi-isä'})
        self.assertEqual(parsed['dam'], {'id': None, 'name': 'Nimetty emä'})
        raw.update(ownerName='-', breederName=None, sire=None)
        parsed = api.normalize_profile(raw, raw['id'])
        self.assertIsNone(parsed['ownerName'])
        self.assertIsNone(parsed['sire'])
        for change in ({'id': '999'}, {'ownerName': []}, {'dead': 'false'},
                       {'sire': {'id': True}}, {'sire': {'id': raw['id']}}, {'dam': []}):
            with self.subTest(change=change), self.assertRaises(api.SchemaError):
                api.normalize_profile({**raw, **change}, raw['id'])
        for value in ('../1', '0', True, 1.5, '1?x', '1' * 31):
            with self.assertRaises(api.SchemaError):
                api.profile_path(value)

    def test_bounded_ancestor_discovery_and_reuse(self):
        data = {}
        for value, parent in [('100','200'), ('200','300'), ('300','400')]:
            p = profile(value)
            p.update(sire={'id': parent, 'name': 'Isä ' + parent}, dam={'id': parent, 'name': 'Sama esivanhempi'})
            data[api.profile_path(value)] = p
        with self.db:
            store.enqueue_profile(self.db, '100', 2)
        self.assertEqual(self.collect(data), 'idle')
        self.assertEqual(self.calls, ['/horse/100','/horse/200','/horse/300'])
        self.assertIsNotNone(self.db.execute("SELECT 1 FROM horses WHERE id='400'").fetchone())
        self.assertIsNone(self.db.execute("SELECT 1 FROM jobs WHERE path='/horse/400'").fetchone())
        # A former depth-zero ancestor can become an explicit root without refetching it.
        with self.db:
            store.enqueue_profile(self.db, '300', 1)
        self.assertIsNotNone(self.db.execute("SELECT 1 FROM jobs WHERE path='/horse/400'").fetchone())
        self.assertEqual(self.db.execute("SELECT attempts FROM jobs WHERE path='/horse/300'").fetchone()[0], 1)

    def test_profile_correction_replaces_relationships_and_keeps_snapshots(self):
        self.assertEqual(self.save(profile()), 'idle')
        newer = profile()
        newer.update(ownerName='Uusi omistajaryhmä', breederName='-', sire=None, dam=None)
        self.assertEqual(self.save(newer, refresh=True), 'idle')
        self.assertEqual([tuple(r) for r in self.db.execute('SELECT role,label FROM horse_parties')], [('owner','Uusi omistajaryhmä')])
        self.assertEqual(self.db.execute('SELECT count(*) FROM horse_parents').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM snapshots').fetchone()[0], 2)
        self.assertNotIn('DROP', ' '.join(r[0] for r in self.db.execute('SELECT body FROM snapshots')))

    def test_bad_refresh_is_atomic_and_persists_stop(self):
        self.save(profile())
        before = self.db.execute('SELECT data FROM horse_profiles').fetchone()[0]
        bad = profile(); bad['dam'] = {'id': 1.2}
        self.assertEqual(self.save(bad, refresh=True), 'paused')
        self.assertEqual(self.db.execute('SELECT data FROM horse_profiles').fetchone()[0], before)
        self.assertEqual(self.db.execute('SELECT count(*) FROM snapshots').fetchone()[0], 1)
        self.assertTrue(store.status(self.db)['control']['paused_reason'])

    def test_profile_shares_provider_stop_and_daily_budget(self):
        with self.db:
            store.enqueue_profile(self.db, '100', 0)
        outcome = collector.run(self.db, max_requests=2, delay=30, daily_budget=200,
            fetch=lambda _: api.Response(429, headers={'retry-after':'120'}),
            clock=self.clock, sleep=self.clock.sleep, emit=lambda _: None)
        self.assertEqual(outcome, 'paused')
        self.assertEqual(self.collect({}), 'paused')
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 1)

    def test_existing_archive_gets_additive_tables(self):
        with self.db:
            self.db.execute('DROP TABLE horse_parents')
            self.db.execute('DROP TABLE horse_parties')
            self.db.execute('DROP TABLE horse_profiles')
        self.db.close()
        self.db = store.connect(self.path)
        self.save(profile())
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_party_groups_and_pedigree_links(self):
        self.save(profile())
        self.save({**profile('300','Toinen hevonen'), 'sire': {'id':'200','name':'Testi-isä'}})
        owners = Archive(self.db).parties('owner','talli',0)
        self.assertEqual(owners['total'], 1)
        party = Archive(self.db).party('owner', owners['parties'][0]['id'], 0)
        self.assertEqual({h['id'] for h in party['horses']}, {'100','300'})
        horse = Archive(self.db).horse('100')
        self.assertEqual(horse['profile']['data']['ownerName'], profile()['ownerName'])
        self.assertEqual(horse['pedigree']['sire']['id'], '200')
        self.assertIsNone(horse['pedigree']['sire']['fetched_at'])
        self.assertEqual(horse['pedigree']['dam']['name'], 'Nimetty emä')
        parent = Archive(self.db).horse('200')
        self.assertEqual({h['id'] for h in parent['offspring']['horses']}, {'100','300'})
        self.assertIsNone(parent['profile'])
        for params in ({'role':['trainer']}, {'role':['owner'],'offset':['-1']}):
            with self.assertRaises(ValueError):
                endpoint(Archive(self.db), '/api/parties', params)

    def test_party_paging_and_different_labels_do_not_merge(self):
        for n in range(35):
            self.save({**profile(str(1000+n)), 'sire':None, 'ownerName':'Yhteinen nimi'})
        self.save({**profile('9999'), 'sire':None, 'ownerName':'Yhteinen Nimi'})
        data = Archive(self.db).parties('owner','YHTEINEN',0)
        self.assertEqual(data['total'], 2)
        large = next(p for p in data['parties'] if p['horses'] == 35)
        self.assertEqual(len(Archive(self.db).party('owner',large['id'],0)['horses']),30)
        self.assertEqual(len(Archive(self.db).party('owner',large['id'],30)['horses']),5)
        self.assertEqual(Archive(self.db).parties('owner','%',0)['total'],0)

    def test_cycle_is_bounded_and_only_participants_seed_new_roots(self):
        first = profile('100'); first.update(sire={'id':'200','name':'Isä'},dam=None)
        second = profile('200'); second.update(sire={'id':'100','name':'Toistuva'},dam=None)
        with self.db:
            store.enqueue_profile(self.db,'100',2)
        self.assertEqual(self.collect({'/horse/100':first,'/horse/200':second}),'idle')
        self.assertEqual(len(self.calls),2)
        tree = Archive(self.db).horse('100')['pedigree']
        self.assertTrue(tree['sire']['parents']['sire']['cycle'])
        self.assertEqual(tree['sire']['parents']['sire']['parents'],{})
        with self.db:
            self.assertEqual(store.seed_profiles(self.db,5),0)
        for limit, generations in [(0,2),(101,2),(1,3)]:
            with self.assertRaises(ValueError):
                store.seed_profiles(self.db,limit,generations)

    def test_party_removal_hides_old_group_and_offspring_pages_are_bounded(self):
        for n in range(35):
            self.save(profile(str(1000+n)))
        data = Archive(self.db).horse('200',30)['offspring']
        self.assertEqual((data['total'],data['offset'],len(data['horses'])),(35,30,5))
        self.assertEqual(Archive(self.db).horse('200',300)['offspring']['offset'],30)
        old = Archive(self.db).parties('owner')['parties'][0]['id']
        for n in range(35):
            self.save({**profile(str(1000+n)),'ownerName':'-'},refresh=True)
        with self.assertRaises(LookupError):
            Archive(self.db).party('owner',old)

    def test_profile_budget_and_deduplication_do_not_reset_the_ledger(self):
        with self.db:
            store.enqueue_profile(self.db,'100',0)
            self.db.execute("INSERT INTO requests(path,started_at,outcome) VALUES('research:/horse/100',?,'research')",(self.clock(),))
        calls = []
        self.assertEqual(collector.run(self.db,max_requests=1,delay=30,daily_budget=1,
            fetch=lambda path:calls.append(path),clock=self.clock,sleep=self.clock.sleep,emit=lambda _:None),'budget')
        self.assertEqual(calls,[])
        self.assertEqual(self.collect({'/horse/100':profile()}),'idle')
        self.save(profile(),refresh=True)
        self.assertEqual(self.db.execute('SELECT count(*) FROM snapshots').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0],3)
