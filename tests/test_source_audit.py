import unittest
import json
import tempfile
from pathlib import Path

from hippos_analyst import api,collector,store,photos
from test_collector import CALENDAR, RACES, RUNNERS,Clock,response
from test_profiles import profile
from test_photos import JPEG


class SourceAuditTests(unittest.TestCase):
    def test_race_game_types_and_intermediate_times_are_retained(self):
        raw={'race':{**RACES[0]['race'],'totoTypes':['VOITTAJA','SIJA']},
             'gameTypes':['VOITTAJA','SIJA','KAKSARI'],'intermediateTime':'14,5 15,5 16,5'}
        parsed=api.normalize('races',[raw],{'date':raw['race']['date'],'track':'H'})[0]
        self.assertEqual(parsed['totoTypes'],['VOITTAJA','SIJA'])
        self.assertEqual(parsed['gameTypes'],raw['gameTypes'])
        self.assertEqual(parsed['intermediateTime'],raw['intermediateTime'])
        raw['race']['totoTypes']=['SIJA',{}]
        with self.assertRaises(api.SchemaError):
            api.normalize('races',[raw],{'date':raw['race']['date'],'track':'H'})

    def test_all_endpoint_shapes_inventory_kept_and_omitted_names(self):
        for kind,payload,kept in [('calendar',CALENDAR,'events.trackCode'),
                                  ('races',RACES,'race.startNumber'),
                                  ('runners',RUNNERS,'horseId'),
                                  ('profile',profile(),'sire.id')]:
            with self.subTest(kind=kind):
                fields=api.source_field_inventory(kind,payload)
                self.assertEqual(fields[kept],1)
                self.assertNotIn('DROP',str(fields))
        raw=profile()
        raw['photo']['credit']='Do not copy unreviewed text'
        fields=api.source_field_inventory('profile',raw)
        self.assertEqual(fields['photo.photoUrl'],1)
        self.assertEqual(fields['photo.credit'],0)
        self.assertEqual(fields['ownerAddress'],0)
        self.assertNotIn('Do not copy',str(fields))
        parsed=api.normalize_profile(raw,raw['id'])
        self.assertNotIn('credit',parsed['photo'])

    def test_photo_metadata_validated_without_loading_urls(self):
        for photo in ([],{'photoExist':'true'},{'photoUrl':{}}):
            raw=profile();raw['photo']=photo
            with self.subTest(photo=photo),self.assertRaises(api.SchemaError):
                api.normalize_profile(raw,raw['id'])

    def test_hippos_photo_is_queued_metered_cached_and_not_refetched(self):
        with tempfile.TemporaryDirectory() as temp:
            db=store.connect(Path(temp)/'test.sqlite3');clock=Clock();calls=[]
            raw={'id':'123','name':'Test horse','photo':{'photoExist':True,
                 'photoUrl':api.BASE_URL+'/images/horse/photo/123','lastModified':'123456'}}
            def fetch(path):
                calls.append(path)
                return response(raw) if path=='/horse/123' else api.Response(200,JPEG,{'content-type':'image/jpeg'})
            try:
                with db:store.enqueue_profile(db,'123',0)
                opts=dict(max_requests=5,delay=10,daily_budget=5000,clock=clock,sleep=clock.sleep,fetch=fetch,emit=lambda _:None)
                self.assertEqual(collector.run(db,queue='profiles',**opts),'idle')
                self.assertEqual(calls,['/horse/123','/images/horse/photo/123'])
                starts=[r[0] for r in db.execute('SELECT started_at FROM requests ORDER BY id')]
                self.assertEqual(starts[1]-starts[0],10)
                cached=photos.get(db,'horse','123')
                self.assertEqual(cached['provider'],'hippos')
                self.assertEqual(cached['license'],'')
                self.assertEqual(photos.image(db,cached['url']),JPEG)
                with db:store.enqueue_profile(db,'123',0,refresh=True)
                collector.run(db,queue='profiles',**opts)
                self.assertEqual(calls.count('/images/horse/photo/123'),1)
                self.assertEqual(db.execute("SELECT retained FROM source_fields WHERE kind='profile' AND name='photo.lastModified'").fetchone()[0],1)
            finally:db.close()

    def test_photo_url_cannot_change_host_or_horse_identity(self):
        for url in ('http://heppa.hippos.fi/heppa2_backend/images/horse/photo/123',
                    'https://example.org/heppa2_backend/images/horse/photo/123',
                    api.BASE_URL+'/images/horse/photo/456',
                    api.BASE_URL+'/images/horse/photo/123?token=anything'):
            with self.subTest(url=url),self.assertRaises(api.SchemaError):
                api.horse_photo_path('123',url)

    def test_bad_photo_stops_collector_without_publishing_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            db=store.connect(Path(temp)/'test.sqlite3');clock=Clock()
            try:
                with db:store.enqueue(db,'/images/horse/photo/123','horse_photo',{'id':'123','name':'Test'})
                outcome=collector.run(db,max_requests=2,clock=clock,sleep=clock.sleep,
                         fetch=lambda _:api.Response(200,b'<html>not an image</html>',{'content-type':'text/html'}),emit=lambda _:None)
                self.assertEqual(outcome,'paused')
                self.assertEqual(db.execute('SELECT count(*) FROM photo_assets').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0],1)
            finally:db.close()
