import unittest

from hippos_analyst import browse
from hippos_analyst.server import Archive, endpoint
import test_server
from test_server import DAY, HORSE


class BrowseTests(unittest.TestCase):
    setUp = test_server.ArchiveTests.setUp
    tearDown = test_server.ArchiveTests.tearDown
    save = test_server.ArchiveTests.save

    def read(self, path, **params):
        return endpoint(Archive(self.db), '/api/' + path,
                        {key: [str(value)] for key, value in {'today': DAY, **params}.items()})

    def field(self, count=35):
        self.save('runners', [{**self.runner, 'horseId': str(n), 'horseName': f'Hevonen {n:02}',
            'programNumber': str(n), 'driverId': str(n), 'driverName': f'Nimi {n:02}',
            'trainerId': str(n), 'trainerName': f'Nimi {n:02}', 'distance': str(2100+n),
            'placing': str(n), 'kilometerTime': f'{n},5', 'price': str(n*10)} for n in range(1,count+1)])

    def test_directory_sort_and_filter_before_pagination(self):
        self.field()
        first = self.read('directory/horses', sort='name', dir='desc')
        second = self.read('directory/horses', sort='name', dir='desc', offset=30)
        self.assertEqual(first['rows'][0]['id'], '35')
        self.assertEqual(second['rows'][-1]['id'], '1')
        self.assertEqual((first['total'], len(first['rows']), len(second['rows'])), (35,30,5))
        self.assertEqual(self.read('directory/horses', q='HEVONEN 35', offset=30)['offset'], 0)
        self.assertEqual(self.read('directory/horses', q='%')['total'], 0)
        self.assertEqual(self.read('directory/horses', min_age=1)['total'], 0)
        self.assertEqual(self.read('directory/horses', upcoming=1)['total'], 0)

    def test_people_union_preserves_role_id_and_name_group_identity(self):
        self.field(2)
        self.db.execute("INSERT INTO horse_profiles VALUES('1','{}',100)")
        for role in ('owner','breeder'):
            self.db.execute('INSERT INTO horse_parties VALUES(?,?,?,?)', ('1',role,'Nimi 01','a'*64))
        data = self.read('directory/people', q='nimi 01')
        self.assertEqual(data['total'],4)
        self.assertEqual({(r['role'],r['id']) for r in data['rows']},
                         {('driver','1'),('trainer','1'),('owner','a'*64),('breeder','a'*64)})
        self.assertEqual(self.read('directory/people',role='owner')['total'],1)
        self.assertIsNone(next(r for r in data['rows'] if r['role']=='owner')['entries'])

    def test_dates_distinguish_past_from_future_and_removed_membership(self):
        self.save('runners',[{**self.runner,'driverId':'123','driverName':'Ääni'}])
        data=self.read('directory/people',role='driver',q='ÄÄNI')
        self.assertIsNone(data['rows'][0]['last_date'])
        self.assertEqual(data['rows'][0]['next_date'],DAY)
        self.assertEqual(self.read('directory/people',activity='past')['total'],0)
        self.save('races',[])
        self.assertEqual(self.read('directory/people')['total'],0)
        self.assertEqual(self.read('directory/horses')['rows'][0]['entries'],0)

    def test_activity_global_numeric_sort_and_stale_page(self):
        self.field()
        # One trainer is associated with all runners; the driver IDs remain distinct.
        self.db.execute("UPDATE entries SET data=json_set(data,'$.trainerId','777')")
        result=self.read('activity',role='trainer',id='777',period='history',sort='placing',dir='desc')
        self.assertEqual(result['rows'][0]['placing'],'35')
        self.assertEqual(result['summary']['entries'],35)
        self.assertEqual(self.read('activity',role='trainer',id='777',period='history',offset=999)['offset'],30)
        horses=self.read('activity',role='trainer',id='777',period='horses',sort='name',dir='desc')
        self.assertEqual(horses['total'],35)
        self.assertEqual(horses['rows'][0]['id'],'35')

    def test_preview_is_bounded_and_excludes_selected_day(self):
        self.save('runners',[self.runner])
        for n in range(1,8):
            day=f'2026-10-{n:02}'
            self.save('calendar',[{**self.meeting,'date':day}],day=day)
            self.save('races',[{**self.races[0],'date':day}],day=day)
            self.save('runners',[{**self.runner,'date':day,'placing':'1'}],day=day)
        result=self.read('preview',kind='horse',id=HORSE,before='2026-10-07')
        self.assertEqual(result['starts'],[])
        self.assertEqual(result['pedigree'],{})
        self.assertEqual(len(result['activity']['rows']),5)
        self.assertEqual(result['activity']['rows'][0]['date'],'2026-10-06')
        self.assertTrue(all(r['date']<'2026-10-07' for r in result['activity']['rows']))
        profile=self.read('horse',id=HORSE,section='activity')
        self.assertEqual(profile['starts'],[])

    def test_invalid_filters_and_sorts_are_rejected(self):
        for path,params in [('directory/horses',{'sort':'name; DELETE FROM horses'}),
                            ('directory/horses',{'dir':'sideways'}),
                            ('directory/horses',{'min_age':'-1'}),
                            ('directory/people',{'role':'person'}),
                            ('directory/people',{'activity':'yesterday'}),
                            ('activity',{'role':'owner','id':'1'}),
                            ('preview',{'kind':'unknown','id':'1'})]:
            with self.subTest(path=path,params=params),self.assertRaises(ValueError):
                self.read(path,**params)
        self.assertIsNone(browse.numeric('hyl'))
        self.assertEqual(browse.numeric('14,5a'),14.5)
        self.assertEqual(browse.numeric('1='),1)

    def test_directory_cache_refreshes_with_observations_and_does_not_merge_searches(self):
        self.field(2)
        cache = {}
        params = {'today':DAY}
        self.assertEqual(browse.directory(Archive(self.db,cache),'people',params)['total'],4)
        self.assertEqual(browse.directory(Archive(self.db,cache),'people',{**params,'q':'01'})['total'],2)
        self.save('runners',[{**self.runner,'driverId':'9','driverName':'Uusi'}])
        result = browse.directory(Archive(self.db,cache),'people',params)
        self.assertEqual(result['total'],1)
        self.assertEqual(result['rows'][0]['name'],'Uusi')
        self.assertEqual(browse.directory(Archive(self.db,cache),'people',{**params,'q':'01'})['total'],0)

    def test_finnish_order_and_missing_values_remain_last(self):
        self.save('runners',[{**self.runner,'horseId':str(n),'programNumber':str(n),'horseName':name}
                             for n,name in enumerate(['Ö','Ä','Å','Z'],1)])
        rows = self.read('directory/horses')['rows']
        self.assertEqual([r['name'] for r in rows],['Z','Å','Ä','Ö'])
        self.db.execute("INSERT INTO horse_profiles VALUES('1',?,100)", ('{"birthDate":"2020-01-01","gender":"T"}',))
        for direction in ('asc','desc'):
            rows = self.read('directory/horses',sort='age',dir=direction)['rows']
            self.assertEqual(rows[0]['id'],'1')
            self.assertTrue(all(r['age'] is None for r in rows[1:]))

    def test_completed_today_is_latest_activity_not_an_upcoming_entry(self):
        self.save('runners',[{**self.runner,'placing':'1','driverId':'1','driverName':'Ohjastaja'}])
        for kind in ('horses','people'):
            row=self.read('directory/'+kind)['rows'][0]
            self.assertEqual(row['last_date'],DAY)
            self.assertIsNone(row['next_date'])

    def test_relationship_tables_sort_across_pages(self):
        self.field()
        for n in range(1,36):
            self.db.execute('INSERT INTO horse_profiles VALUES(?,?,?)',(str(n),'{}',n))
            self.db.execute('INSERT INTO horse_parties VALUES(?,?,?,?)',(str(n),'owner','Omistaja','a'*64))
            if n>1:
                self.db.execute('INSERT INTO horse_parents VALUES(?,?,?,?)',(str(n),'sire','1','Hevonen 01'))
        party=self.read('party',role='owner',id='a'*64,sort='name',dir='desc')
        self.assertEqual(party['horses'][0]['id'],'35')
        party=self.read('party',role='owner',id='a'*64,sort='observed',dir='asc',offset=30)
        self.assertEqual(party['horses'][0]['id'],'31')
        children=self.read('horse',id='1',section='family',sort='name',dir='desc',offspring_offset=30)['offspring']
        self.assertEqual((children['total'],children['horses'][-1]['id']),(34,'2'))


if __name__ == '__main__':
    unittest.main()
