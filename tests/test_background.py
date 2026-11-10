import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from hippos_analyst import api, background, collector, maintenance, store
from test_collector import Clock, response


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'archive.sqlite3'
        self.db = store.connect(self.path)
        self.clock = Clock()
        self.clock.now = datetime.fromisoformat('2026-11-02T22:30:00+00:00').timestamp()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def run_worker(self, fetch=None):
        return background.run(self.path, clock=self.clock, sleep=self.clock.sleep,
                              fetch=fetch or (lambda _: response([])), emit=lambda _: None)

    def test_real_pass_uses_helsinki_date_spacing_and_writes_status(self):
        self.assertEqual(self.run_worker(), 'limit')
        days = [json.loads(r[0])['date'] for r in self.db.execute(
            "SELECT context FROM jobs WHERE json_extract(context,'$.refresh_after') IS NOT NULL")]
        self.assertEqual((min(days), max(days)), ('2026-10-31', '2026-11-10'))
        starts = [r[0] for r in self.db.execute('SELECT started_at FROM requests ORDER BY id')]
        self.assertLessEqual(len(starts), 40)
        self.assertTrue(all(b-a >= 30 for a, b in zip(starts, starts[1:])))
        status = json.loads(self.path.with_suffix('.background.json').read_text(encoding='utf-8'))
        self.assertEqual(status['integrity'], 'ok')
        self.assertEqual(status['counts']['requests'], len(starts))
        with collector.worker_lock(self.path):
            pass

    def test_second_process_cannot_collect_while_lock_held(self):
        with collector.worker_lock(self.path):
            result = subprocess.run([sys.executable, '-m', 'hippos_analyst.background',
                                     '--db', str(self.path)], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 0)
        self.assertIn('another collector', self.path.with_suffix('.background.log').read_text())

    def test_daily_budget_sends_nothing_and_does_not_reset_ledger(self):
        with self.db:
            for _ in range(200):
                self.db.execute("INSERT INTO requests(path,started_at) VALUES('test',?)", (self.clock(),))
        self.assertEqual(self.run_worker(lambda _: self.fail('Budget exceeded')), 'budget')
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 200)
        self.assertEqual(self.db.execute('SELECT count(*) FROM jobs').fetchone()[0], 0)

    def test_two_thousand_attempt_cap_is_enforced_across_restarts(self):
        with self.db:
            for _ in range(1999):
                self.db.execute("INSERT INTO requests(path,started_at) VALUES('test',?)", (self.clock(),))
        calls = []
        options = dict(delay=15, daily_budget=2000, clock=self.clock,
                       sleep=self.clock.sleep, emit=lambda _: None)
        result = background.run(self.path, fetch=lambda path: (calls.append(path) or response([])), **options)
        self.assertEqual(result, 'budget')
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 2000)
        self.assertEqual(background.run(self.path, fetch=lambda _: self.fail('Cap bypassed'), **options), 'budget')
        self.clock.now += 86400
        self.assertEqual(background.run(self.path, fetch=lambda _: api.Response(403), **options), 'paused')
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 2001)

    def test_budget_ceiling_and_toto_limits_remain_bounded(self):
        for call in [lambda: background.run(self.path, daily_budget=5001),
                     lambda: maintenance.run(self.db, '2026-11-03', daily_budget=5001),
                     lambda: collector.run(self.db, daily_budget=5001),
                     lambda: collector.run(self.db, provider='toto', delay=60,
                                           max_requests=1, daily_budget=2000)]:
            with self.assertRaises(ValueError):
                call()
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 0)

    def test_five_thousand_cap_preserves_all_prior_attempts(self):
        with self.db:
            self.db.executemany("INSERT INTO requests(path,started_at) VALUES('test',?)",
                                [(self.clock(),)]*4999)
        calls=[]
        opts=dict(delay=10,daily_budget=5000,clock=self.clock,sleep=self.clock.sleep,emit=lambda _:None)
        self.assertEqual(background.run(self.path,fetch=lambda path:(calls.append(path) or response([])),**opts),'budget')
        self.assertEqual(len(calls),1)
        self.assertEqual(background.run(self.path,fetch=lambda _:self.fail('Cap bypassed'),**opts),'budget')
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0],5000)

    def test_refusal_and_schema_stop_future_invocations(self):
        for status, payload in [(403, None), (429, None), (302, None), (200, {})]:
            with self.subTest(status=status):
                # Each case has its own archive; never reset a real stop.
                path = Path(self.temp.name) / f'case-{status}.sqlite3'
                kwargs = dict(clock=self.clock, sleep=self.clock.sleep, emit=lambda _: None)
                result = background.run(path, fetch=lambda _: response(payload) if status == 200
                                        else api.Response(status), **kwargs)
                self.assertEqual(result, 'paused')
                self.assertEqual(background.run(path, fetch=lambda _: self.fail('Stop bypassed'), **kwargs), 'paused')

    def test_failed_job_blocks_and_is_not_retried(self):
        self.assertEqual(self.run_worker(lambda _: api.Response(404)), 'failed')
        self.assertEqual(self.run_worker(lambda _: self.fail('Failed job retried')), 'failed')
        self.assertEqual(self.db.execute("SELECT count(*) FROM jobs WHERE status='failed'").fetchone()[0], 1)

    def test_transient_ends_pass_and_preserves_retry_after(self):
        result = self.run_worker(lambda _: api.Response(503, headers={'retry-after': '7200'}))
        self.assertEqual(result, 'retry')
        deadline = self.db.execute('SELECT paused_until FROM control').fetchone()[0]
        self.assertEqual(deadline, self.clock()+7200)
        self.clock.now += 3600
        self.assertEqual(self.run_worker(lambda _: self.fail('Retry-After bypassed')), 'retry')
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 1)
        self.assertEqual(self.db.execute('SELECT paused_until FROM control').fetchone()[0], deadline)

    def test_unexpected_local_error_persists_stop_preserving_cooldown(self):
        with self.db:
            self.db.execute('UPDATE control SET paused_until=123')
        with patch('hippos_analyst.background.maintenance.run', side_effect=RuntimeError('local bug')):
            with self.assertRaisesRegex(RuntimeError, 'local bug'):
                self.run_worker()
        state = self.db.execute('SELECT * FROM control').fetchone()
        self.assertIn('Background worker error', state['paused_reason'])
        self.assertEqual(state['paused_until'], 123)
        self.assertEqual(self.run_worker(lambda _: self.fail('Error stop bypassed')), 'paused')

    def test_continuous_crosses_pass_boundaries_with_ten_second_spacing(self):
        calls = []
        def fetch(path):
            calls.append(self.clock())
            return api.Response(403) if len(calls) == 45 else response([])
        result = background.run(self.path, continuous=True, delay=10, daily_budget=500,
                                clock=self.clock, sleep=self.clock.sleep, fetch=fetch, emit=lambda _: None)
        self.assertEqual(result, 'paused')
        self.assertEqual(len(calls), 45)
        self.assertTrue(all(10 <= b-a < 11 for a,b in zip(calls,calls[1:])))

    def test_continuous_budget_wait_keeps_lock_and_obeys_manual_pause(self):
        with self.db:
            for _ in range(499):
                self.db.execute("INSERT INTO requests(path,started_at) VALUES('test',?)", (self.clock(),))
        def sleep(seconds):
            self.assertLessEqual(seconds, 30)
            with self.assertRaisesRegex(RuntimeError, 'Another collector'):
                with collector.worker_lock(self.path):
                    pass
            checkpoint = self.path.with_suffix('.background.json')
            if checkpoint.exists() and json.loads(checkpoint.read_text())['outcome'] == 'budget':
                with self.db:
                    collector.pause(self.db, 'Operator stop during budget wait')
            self.clock.sleep(seconds)
        result = background.run(self.path, continuous=True, delay=15, daily_budget=500,
                                clock=self.clock, sleep=sleep, fetch=lambda _: response([]), emit=lambda _: None)
        self.assertEqual(result, 'paused')
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 500)
        checkpoint = json.loads(self.path.with_suffix('.background.json').read_text())
        self.assertEqual(checkpoint['outcome'], 'budget')

    def test_continuous_retry_waits_for_retry_after_before_next_pass(self):
        calls = []
        def fetch(path):
            calls.append(self.clock())
            return api.Response(503, headers={'retry-after': '7200'}) if len(calls)==1 else api.Response(429)
        result = background.run(self.path, continuous=True, delay=10, daily_budget=500,
                                clock=self.clock, sleep=self.clock.sleep, fetch=fetch, emit=lambda _: None)
        self.assertEqual(result, 'paused')
        self.assertEqual(len(calls), 2)
        self.assertGreaterEqual(calls[1]-calls[0], 7200)

    def test_invalid_limits_do_not_pause_or_schedule(self):
        with self.assertRaises(ValueError):
            background.run(self.path, continuous=True, delay=1)
        self.assertIsNone(self.db.execute('SELECT paused_reason FROM control').fetchone()[0])
        self.assertEqual(self.db.execute('SELECT count(*) FROM jobs').fetchone()[0], 0)

    def test_continuous_budget_resumes_at_utc_midnight_without_resetting_ledger(self):
        self.clock.now = datetime.fromisoformat('2026-11-02T23:59:45+00:00').timestamp()
        with self.db:
            for _ in range(500):
                self.db.execute("INSERT INTO requests(path,started_at) VALUES('test',?)", (self.clock(),))
        calls = []
        def fetch(path):
            calls.append(self.clock())
            return api.Response(403)
        result = background.run(self.path, continuous=True, delay=10, daily_budget=500,
                                clock=self.clock, sleep=self.clock.sleep, fetch=fetch, emit=lambda _: None)
        self.assertEqual(result, 'paused')
        self.assertEqual(calls, [datetime.fromisoformat('2026-11-03T00:00:00+00:00').timestamp()])
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], 501)
