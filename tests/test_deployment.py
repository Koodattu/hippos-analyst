import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

from hippos_analyst import backup, prediction_store, server, store


class DeploymentTests(unittest.TestCase):
    def test_host_health_methods_and_asset_revalidation(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'archive.sqlite3'
            app = server.application(db, ['hippos.example'])

            def request(path, host='hippos.example:443', method='GET', **headers):
                response = Mock()
                body = b''.join(app(dict(PATH_INFO=path, REQUEST_METHOD=method, HTTP_HOST=host,
                                         **headers), response))
                status, fields = response.call_args.args
                return int(status[:3]), dict(fields), body

            self.assertEqual(request('/healthz')[0], 503)
            self.assertFalse(db.exists())
            store.connect(db).close()
            self.assertEqual(request('/healthz')[2], b'ok')
            self.assertEqual(request('/healthz', host='other.example', HTTP_X_FORWARDED_HOST='localhost')[0], 403)
            self.assertEqual(request('/healthz', method='POST')[0], 405)
            status, headers, body = request('/app.mjs')
            self.assertEqual(status, 200)
            self.assertEqual(request('/app.mjs', HTTP_IF_NONE_MATCH=headers['ETag'])[0], 304)
            status, head, empty = request('/app.mjs', method='HEAD')
            self.assertEqual((status, int(head['Content-Length']), empty), (200, len(body), b''))

    def test_live_backup_restores_archive_predictions_model_and_retains_complete_sets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, dest = root / 'hippos.sqlite3', root / 'backups'
            model = root / 'v3'
            model.mkdir()
            (model / 'model.cbm').write_bytes(b'model')
            (model / 'report.json').write_text('{}')
            with closing(store.connect(path)) as archive, closing(prediction_store.connect(path)) as predictions:
                with archive, predictions:
                    archive.execute("UPDATE control SET paused_reason='transfer'")
                    predictions.execute("INSERT INTO models VALUES('v3',1,'local','{}')")
                first = backup.backup(path, dest, model=model, keep=1)
                with self.assertRaises(FileNotFoundError):
                    backup.backup(path, dest, model=root / 'missing', keep=1)
                self.assertEqual(list(dest.iterdir()), [first])
                bundle = backup.backup(path, dest, model=model, keep=1)
                self.assertEqual(list(dest.iterdir()), [bundle])
            restored = root / 'restored'
            with ZipFile(bundle) as z:
                self.assertIsNone(z.testzip())
                z.extractall(restored)
            self.assertEqual((restored / 'models/v3/model.cbm').read_bytes(), b'model')
            with closing(sqlite3.connect(restored / path.name)) as db:
                self.assertEqual(db.execute('SELECT paused_reason FROM control').fetchone(), ('transfer',))
            with closing(sqlite3.connect(restored / prediction_store.path_for(path).name)) as db:
                self.assertEqual(db.execute('SELECT id FROM models').fetchone(), ('v3',))
