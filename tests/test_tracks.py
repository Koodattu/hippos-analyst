import json
import tempfile
import threading
import unittest
from datetime import date, timedelta
from http.client import HTTPConnection
from pathlib import Path

from hippos_analyst import api, store, tracks
from hippos_analyst.server import Archive, endpoint, make_server


class TrackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'tracks.sqlite3'
        self.db = store.connect(self.path)
        self.now = 100

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def save(self, records, day='2026-10-25'):
        self.now += 1
        path = api.calendar_path(day)
        with self.db:
            store.enqueue(self.db, path, 'calendar', {'date': day}, refresh=True)
            request = self.db.execute('INSERT INTO requests(path,started_at,status) VALUES(?,?,200)', (path,self.now)).lastrowid
            job = self.db.execute('SELECT * FROM jobs WHERE path=?', (path,)).fetchone()
            store.save_response(self.db, job, records, request, self.now)

    def get(self, path='/api/tracks', **params):
        return endpoint(Archive(self.db), path, {key:[str(value)] for key,value in {'today':'2026-10-25',**params}.items()})

    def test_catalog_is_available_without_collection_and_searches_finnish_names(self):
        self.assertEqual(self.get()['total'], 17)
        row = self.get(q='ÄIMÄ')['rows'][0]
        self.assertEqual(row['code'], 'O')
        self.assertEqual(row['meeting_count'], 0)
        self.assertIsNone(row['coordinates'])
        self.assertEqual(self.get(q='Espoo')['rows'][0]['code'], 'H')
        self.assertEqual(self.get(q='not a track',offset=30)['offset'], 0)

    def test_observations_keep_identity_location_and_conditions_separate(self):
        self.save([{'date':'2026-10-25','trackCode':'H','trackCity':'Helsinki',
                    'trackNumber':'1','latitude':'60.216332','longitude':'24.839744',
                    'trackCondition':'Muddy','temperature':4,'name':'Race-day title'}])
        data = self.get('/api/track',id='hippos-H')
        row = data['track']
        self.assertEqual((row['name'],row['city'],row['racing_city']), ('Vermo Areena','Espoo','Helsinki'))
        self.assertEqual(row['coordinates']['latitude'],60.216332)
        self.assertEqual(row['provider_ids']['hippos']['number'],'1')
        self.assertEqual(data['rows'][0]['track_id'],row['id'])
        self.assertNotIn('trackCondition',row['observed'])
        self.assertNotIn('temperature',row['observed'])
        self.assertEqual(data['rows'][0]['data']['trackCondition'],'Muddy')
        self.assertEqual(self.get(q='Helsinki')['rows'][0]['id'],'hippos-H')

    def test_new_codes_are_discovered_without_name_merging_and_bad_coordinates_are_hidden(self):
        self.save([{'date':'2026-10-25','trackCode':code,'trackShortname':'Same name',
                    'latitude':'NaN','longitude':'24'} for code in ('XX','YY')])
        rows = self.get(q='Same name')['rows']
        self.assertEqual({r['id'] for r in rows},{'hippos-XX','hippos-YY'})
        self.assertTrue(all(r['coordinates'] is None and r['image'] is None for r in rows))
        for latitude,longitude in [('91','0'),('60','181'),('60',None),('inf','0')]:
            self.assertIsNone(tracks.coordinates({'latitude':latitude,'longitude':longitude}))

    def test_corrected_calendar_hides_meetings_but_retains_venue(self):
        self.save([{'date':'2026-10-25','trackCode':'XX','trackShortname':'Venue'}])
        self.save([])
        data = self.get('/api/track',id='hippos-XX')
        self.assertEqual((data['meeting_count'],data['rows']),(0,[]))
        self.assertEqual(data['track']['name'],'Venue')

    def test_meetings_filter_and_page_before_loading_races(self):
        for index in range(35):
            day = (date(2026,10,1)+timedelta(days=index)).isoformat()
            self.save([{'date':day,'trackCode':'H','canceled':index==25}],day)
        data = self.get('/api/track',id='hippos-H',today='2026-10-01')
        self.assertEqual((data['total'],len(data['rows'])),(35,30))
        last = self.get('/api/track',id='hippos-H',today='2026-10-01',offset=9999)
        self.assertEqual((last['offset'],len(last['rows'])),(30,5))
        history = self.get('/api/track',id='hippos-H',period='history')
        self.assertEqual(history['total'],24)
        self.assertEqual(history['rows'][0]['date'],'2026-10-24')
        upcoming = self.get('/api/track',id='hippos-H')
        self.assertEqual(upcoming['total'],11)
        self.assertTrue(any(m['canceled'] for m in upcoming['rows']))

    def test_additive_backfill_is_idempotent_and_newer_observations_win(self):
        self.save([{'date':'2026-10-25','trackCode':'ZZ','trackShortname':'Newest'}])
        with self.db:
            tracks.observe(self.db,{'date':'2020-01-01','trackCode':'ZZ','trackShortname':'Old'},1)
            self.db.execute('DELETE FROM tracks')
            self.db.execute("DELETE FROM maintenance_state WHERE name='tracks_backfilled_v1'")
        self.db.close()
        self.db = store.connect(self.path)
        self.assertEqual(self.get('/api/track',id='hippos-ZZ')['track']['name'],'Newest')
        before = self.db.execute('SELECT * FROM tracks ORDER BY id').fetchall()
        tracks.initialize(self.db)
        self.assertEqual(before,self.db.execute('SELECT * FROM tracks ORDER BY id').fetchall())
        with self.db:
            tracks.observe(self.db,{'date':'2020-01-01','trackCode':'ZZ','trackShortname':'Old'},1)
        self.assertEqual(self.get('/api/track',id='hippos-ZZ')['track']['name'],'Newest')

    def test_api_validation_and_missing_venue(self):
        for params in ({'today':'yesterday'},{'offset':-1},{'q':'x'*201}):
            with self.assertRaises(ValueError): self.get(**params)
        with self.assertRaises(ValueError): self.get('/api/track',id='hippos-H',period='unknown')
        with self.assertRaises(LookupError): self.get('/api/track',id='hippos-unknown')

    def test_local_images_credits_and_http_reads_are_self_contained(self):
        images = [item['image'] for item in tracks.FACTS.values() if item.get('image')]
        self.assertEqual(len(images),17)
        for image in images:
            if image['path'] == '/images/track-y.jpg':
                self.assertEqual(image['rights_status'],'not-specified')
                self.assertEqual(image['publisher'],'Suomen Hippos')
                self.assertTrue(image['source'].startswith('https://www.hippos.fi/'))
                self.assertNotIn('license',image)
            else:
                self.assertIn(image['license'],('CC BY-SA 3.0','CC BY-SA 4.0','CC BY 4.0','CC0'))
                self.assertTrue(image['source'].startswith('https://commons.wikimedia.org/'))
                self.assertTrue(image['author'])
                self.assertTrue(image['license_url'])
            self.assertGreater(image['width'],0)
            self.assertGreater(image['height'],0)
        before = self.db.total_changes
        server = make_server(self.path,0)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            client = HTTPConnection('127.0.0.1',server.server_port)
            for path in ['/api/tracks?today=2026-10-25','/api/track?id=hippos-T&today=2026-10-25',
                         *[image['path'] for image in images]]:
                client.request('GET',path)
                response = client.getresponse()
                body = response.read()
                self.assertEqual(response.status,200,path)
                if path.startswith('/images/'):
                    self.assertTrue(body.startswith(b'\xff\xd8'))
                else:
                    self.assertIsInstance(json.loads(body),dict)
            client.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()
        self.assertEqual(self.db.total_changes,before)
