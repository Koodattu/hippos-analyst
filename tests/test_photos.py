import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import Mock

from hippos_analyst import photos, store
from hippos_analyst.server import Archive, endpoint, make_server
import test_server as server_tests

# Synthetic JPEG markers: dimensions are parsed without decoding pixels.
JPEG = bytes.fromhex('ffd8 ffc0 000b 08 0064 00c8 01 011100 ffda 0002 ffd9')


def payload():
    return {'query': {'pages': {'12': {'pageid': 12, 'ns': 6, 'title': 'File:Subject.jpg',
        'imagerepository': 'local', 'imageinfo': [{'mime': 'image/jpeg',
        'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Subject.jpg',
        'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Subject.jpg',
        'extmetadata': {key: {'value': value} for key, value in {
            'Artist': '<b>Photographer &amp; colleague</b>', 'LicenseShortName': 'CC BY-SA 4.0',
            'LicenseUrl': 'https://creativecommons.org/licenses/by-sa/4.0',
            'ImageDescription': '<div>A known subject</div>', 'Credit': 'Own work'}.items()}}]}}}}


class PhotoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'photos.sqlite3'
        self.db = store.connect(self.path)
        with self.db:
            self.db.executemany('INSERT INTO horses VALUES(?,?,NULL,NULL,0)', [('123', 'Subject'), ('456', 'Subject')])

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def importer(self, data=None, body=JPEG, **overrides):
        getter = Mock(side_effect=[json.dumps(data or payload()).encode(), body])
        args = {'db': self.db, 'kind': 'horse', 'entity_id': '123', 'expected_name': 'Subject',
                'title': 'File:Subject.jpg', 'identity_note': 'Reviewed caption and pedigree against the exact horse ID.',
                'fetcher': getter, **overrides}
        return photos.import_commons(**args), getter

    def test_explicit_id_assignment_and_local_only_read(self):
        result, getter = self.importer()
        self.assertEqual(getter.call_count, 2)
        self.assertEqual((result['width'], result['height']), (200, 100))
        self.assertEqual(result['author'], 'Photographer & colleague')
        self.assertEqual(Archive(self.db).horse('123')['photo'], result)
        self.assertIsNone(Archive(self.db).horse('456')['photo'])
        self.assertIsNone(photos.get(self.db, 'driver', '123'))
        self.assertEqual(photos.image(self.db, result['url']), JPEG)
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 0)
        # Store startup is idempotent; imports survive a restart.
        other = store.connect(self.path)
        self.assertEqual(photos.get(other, 'horse', '123'), result)
        other.close()

    def test_invalid_identity_and_existing_photo_do_not_fetch(self):
        getter = Mock()
        for kind, identity, name in [('owner', '123', 'Subject'), ('horse', '../123', 'Subject'),
                                     ('horse', 123, 'Subject'), ('horse', '123', 'Wrong'),
                                     ('horse', '999', 'Subject'), ('trainer', '999', 'Subject')]:
            with self.subTest(kind=kind, identity=identity), self.assertRaises(ValueError):
                self.importer(kind=kind, entity_id=identity, expected_name=name, fetcher=getter)
        self.importer()
        with self.assertRaises(ValueError):
            self.importer(fetcher=getter)
        getter.assert_not_called()

    def test_refused_or_malformed_import_preserves_existing_photo(self):
        original, _ = self.importer()
        for field, value in [('LicenseShortName', 'All rights reserved'), ('LicenseUrl', 'https://example.org'),
                             ('Artist', ''), ('Restrictions', 'Editorial only')]:
            data = payload()
            data['query']['pages']['12']['imageinfo'][0]['extmetadata'][field] = {'value': value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.importer(data=data, replace=True)
            self.assertEqual(photos.get(self.db, 'horse', '123'), original)
        with self.assertRaises(ValueError):
            self.importer(body=b'<html>not an image</html>', replace=True)
        with self.assertRaises(OSError):
            self.importer(fetcher=Mock(side_effect=OSError('HTTP 429')), replace=True)
        self.assertEqual(photos.get(self.db, 'horse', '123'), original)

    def test_metadata_rejects_foreign_urls_and_missing_files(self):
        for url in ['http://upload.wikimedia.org/a.jpg', 'https://example.com/a.jpg',
                    'https://upload.wikimedia.org@localhost/a.jpg', 'https://upload.wikimedia.org:8000/a.jpg']:
            data = payload()
            data['query']['pages']['12']['imageinfo'][0]['url'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.importer(data=data)
        for data in [None, [], {}, {'query': {'pages': {'-1': {'missing': ''}}}}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                photos.commons_metadata(data)

    def test_jpeg_bounds(self):
        for body in [JPEG[:-2], b'\x89PNG', b'\xff\xd8\xff\xd9',
                     JPEG.replace(b'\x00\xc8', b'\xff\xff'), JPEG + b'x' * photos.MAX_BYTES]:
            with self.assertRaises(ValueError):
                photos.jpeg_size(body)

    def test_shared_asset_removal_and_explicit_replacement(self):
        first, _ = self.importer()
        self.importer(entity_id='456')
        self.assertEqual(self.db.execute('SELECT count(*) FROM photo_assets').fetchone()[0], 1)
        second, _ = self.importer(body=JPEG.replace(b'\x00\xc8', b'\x00\xc9'), replace=True)
        self.assertNotEqual(first['url'], second['url'])
        self.assertEqual(photos.image(self.db, first['url']), JPEG)
        self.assertEqual(photos.remove(self.db, 'horse', '456'), 1)
        with self.assertRaises(LookupError):
            photos.image(self.db, first['url'])
        self.assertEqual(photos.remove(self.db, 'horse', '123'), 1)
        self.assertEqual(photos.remove(self.db, 'horse', '123'), 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM photo_assets').fetchone()[0], 0)

    def test_http_serves_only_imported_bytes_and_correct_mime(self):
        photo, _ = self.importer()
        server = make_server(self.path, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection('127.0.0.1', server.server_port)
            connection.request('GET', photo['url'])
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader('Content-Type'), 'image/jpeg')
            self.assertIn("img-src 'self' data:", response.getheader('Content-Security-Policy'))
            self.assertEqual(response.read(), JPEG)
            for path in ['/media/../../README.md', '/media/' + 'a' * 64 + '.jpg']:
                connection.request('GET', path)
                response = connection.getresponse()
                self.assertEqual(response.status, 404)
                response.read()
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class PersonPhotoTests(unittest.TestCase):
    def test_browse_preview_and_legacy_person_use_role_specific_assignment(self):
        fixture = server_tests.ArchiveTests()
        fixture.setUp()
        try:
            fixture.save('runners', [{**fixture.runner, 'driverId': '123', 'driverName': 'Driver',
                                     'trainerId': '123', 'trainerName': 'Trainer'}])
            result = photos.import_commons(fixture.db, 'driver', '123', 'Driver', 'File:Subject.jpg',
                'The caption identifies the driver in this race.', fetcher=Mock(side_effect=[json.dumps(payload()).encode(), JPEG]))
            for path, params in [('/api/person', {'role': ['driver'], 'id': ['123'], 'from': [server_tests.DAY]}),
                                 ('/api/activity', {'role': ['driver'], 'id': ['123'], 'today': [server_tests.DAY]}),
                                 ('/api/preview', {'kind': ['driver'], 'id': ['123'], 'today': [server_tests.DAY]})]:
                with self.subTest(path=path):
                    self.assertEqual(endpoint(Archive(fixture.db), path, params)['photo'], result)
            self.assertIsNone(Archive(fixture.db).person('trainer', '123', server_tests.DAY)['photo'])
        finally:
            fixture.tearDown()
