import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from hippos_analyst import api, collector, store
from hippos_analyst.__main__ import main


# Synthetic records shaped like the observed API, not downloaded personal data.
DAY = "2025-10-22"
HORSE_ID = "7616196635396808820"
CALENDAR = [{"raceDate": DAY, "events": [{
    "date": DAY, "trackCode": "H", "finnishTrack": True, "trackCity": "Helsinki",
    "startTime": "18:00:00", "name": "Test meeting", "canceled": False,
}]}]
RACES = [{"race": {"date": DAY, "trackCode": "H", "startNumber": "1",
                      "eventType": "LAMMINVERISET", "baseDistance": "2100"}}]
RUNNERS = [{"date": DAY, "trackCode": "H", "startNumber": "1", "programNumber": "7",
            "horseId": HORSE_ID, "horseName": "Test Horse", "horseBreed": "L",
            "placing": "1", "kilometerTime": "1.17.8", "price": "2000", "absent": False,
            "ownerName": "Do not retain", "chipNo": "Do not retain", "commentText": "Do not retain"}]


class Clock:
    def __init__(self):
        self.now = 1761177600.0
        self.waits = []

    def __call__(self):
        return self.now

    def sleep(self, delay):
        self.waits.append(delay)
        self.now += delay


def response(payload):
    return api.Response(200, json.dumps(payload).encode(), {"content-type": "application/json;charset=UTF-8"})


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.sqlite3"
        self.db = store.connect(self.path)
        self.clock = Clock()
        self.calls = []
        self.payloads = {
            api.calendar_path(DAY): CALENDAR,
            api.races_path(DAY, "H"): RACES,
            api.runners_path(DAY, "H", "1"): RUNNERS,
        }
        self.seed()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def seed(self, refresh=False):
        with self.db:
            return store.enqueue(self.db, api.calendar_path(DAY), "calendar", {"date": DAY}, refresh=refresh)

    def fetch(self, path):
        self.calls.append((path, self.clock()))
        return response(self.payloads[path])

    def run_worker(self, **kwargs):
        options = dict(max_requests=10, delay=15, daily_budget=500, fetch=self.fetch,
                       clock=self.clock, sleep=self.clock.sleep, emit=lambda _: None)
        options.update(kwargs)
        return collector.run(self.db, **options)

    def test_end_to_end_discovery_and_string_ids(self):
        self.assertEqual(self.run_worker(), "idle")
        self.assertEqual(len(self.calls), 3)
        counts = store.status(self.db)["counts"]
        self.assertEqual((counts["meetings"], counts["races"], counts["entries"], counts["horses"]), (1, 1, 1, 1))
        row = self.db.execute("SELECT horse_id,placing,kilometer_time,prize FROM entries").fetchone()
        self.assertEqual(tuple(row), (HORSE_ID, "1", "1.17.8", "2000"))
        for before, after in zip(self.calls, self.calls[1:]):
            self.assertGreaterEqual(after[1] - before[1], 15)

    def test_archives_exclude_irrelevant_personal_fields(self):
        self.run_worker()
        bodies = " ".join(row[0] for row in self.db.execute("SELECT body FROM snapshots"))
        self.assertNotIn("Do not retain", bodies)
        self.assertNotIn("ownerName", bodies)
        self.assertIn("Test Horse", bodies)

    def test_restart_resumes_without_redownloading_done_jobs(self):
        self.run_worker(max_requests=1)
        self.db.close()
        self.db = store.connect(self.path)
        self.assertEqual(self.seed(), 0)
        self.run_worker()
        self.assertEqual(len(self.calls), 3)
        self.run_worker()
        self.assertEqual(len(self.calls), 3)

    def test_refresh_deduplicates_snapshots_but_records_each_observation(self):
        self.run_worker()
        self.seed(refresh=True)
        self.run_worker()
        counts = store.status(self.db)["counts"]
        self.assertEqual(counts["snapshots"], 3)
        self.assertEqual(counts["requests"], 6)
        self.assertEqual(counts["entries"], 1)

    def test_correction_preserves_old_snapshot(self):
        self.run_worker()
        changed = copy.deepcopy(RUNNERS)
        changed[0]["placing"] = "2"
        self.payloads[api.runners_path(DAY, "H", "1")] = changed
        self.seed(refresh=True)
        self.run_worker()
        self.assertEqual(self.db.execute("SELECT placing FROM entries").fetchone()[0], "2")
        bodies = [json.loads(row[0]) for row in self.db.execute("SELECT body FROM snapshots WHERE path=? ORDER BY id", (api.runners_path(DAY, "H", "1"),))]
        self.assertEqual([body[0]["placing"] for body in bodies], ["1", "2"])

    def test_removed_participant_is_not_left_in_current_field(self):
        self.run_worker()
        self.payloads[api.runners_path(DAY, "H", "1")] = []
        self.seed(refresh=True)
        self.run_worker()
        self.assertEqual(self.db.execute("SELECT count(*) FROM entries").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 4)

    def test_daily_budget_survives_restart_and_resets_next_utc_day(self):
        self.assertEqual(self.run_worker(daily_budget=1), "budget")
        self.db.close()
        self.db = store.connect(self.path)
        self.assertEqual(self.run_worker(daily_budget=1), "budget")
        self.assertEqual(len(self.calls), 1)
        self.clock.now += 86400
        self.run_worker(daily_budget=1)
        self.assertEqual(len(self.calls), 2)

    def test_rate_limit_pauses_across_runs_and_keeps_retry_after(self):
        def limited(path):
            self.calls.append(path)
            return api.Response(429, headers={"retry-after": "120"})
        self.assertEqual(self.run_worker(fetch=limited), "paused")
        self.assertEqual(self.run_worker(fetch=limited), "paused")
        self.assertEqual(len(self.calls), 1)
        state = self.db.execute("SELECT * FROM control").fetchone()
        self.assertEqual(state["paused_until"], self.clock() + 120)

    def test_access_denial_stops_before_other_jobs(self):
        self.assertEqual(self.run_worker(fetch=lambda _: api.Response(403)), "paused")
        self.assertEqual(self.db.execute("SELECT count(*) FROM requests").fetchone()[0], 1)

    def test_transient_failure_retries_later_and_opens_circuit(self):
        for attempt in range(5):
            self.assertEqual(self.run_worker(fetch=lambda _: api.Response(503)), "retry")
            due = self.db.execute("SELECT next_attempt FROM jobs").fetchone()[0]
            self.assertGreater(due, self.clock())
            self.clock.now = due
        self.assertEqual(self.run_worker(), "paused")
        self.assertEqual(len(self.calls), 0)

    def test_service_cooldown_blocks_other_jobs_after_restart(self):
        for header in ('120', 'Thu, 23 Oct 2025 00:02:00 GMT'):
            with self.subTest(header=header):
                with self.db:
                    store.enqueue(self.db, api.calendar_path('2025-10-21'), 'calendar', {'date': '2025-10-21'})
                started = self.clock()
                self.assertEqual(self.run_worker(fetch=lambda _: api.Response(503, headers={'retry-after': header})), 'retry')
                self.db.close()
                self.db = store.connect(self.path)
                reserved = self.db.execute('SELECT count(*) FROM requests').fetchone()[0]
                self.clock.now += 119
                self.assertEqual(self.run_worker(), 'retry')
                self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0], reserved)
                self.assertEqual(self.calls, [])
                self.clock.now = started + 120
                self.assertEqual(self.run_worker(max_requests=1), 'limit')
                self.assertEqual(len(self.calls), 1)
                # A fresh fixture for the alternative header form.
                with self.db:
                    self.db.execute('DELETE FROM requests')
                    self.db.execute('DELETE FROM jobs')
                    self.db.execute('UPDATE control SET last_request_at=0,paused_until=0,consecutive_failures=0')
                self.clock = Clock()
                self.calls.clear()
                self.seed()

    def test_transient_backoff_is_service_wide_without_retry_after(self):
        with self.db:
            store.enqueue(self.db, api.calendar_path('2025-10-21'), 'calendar', {'date': '2025-10-21'})
        self.assertEqual(self.run_worker(fetch=lambda _: api.Response(0)), 'retry')
        self.clock.now += 59
        self.assertEqual(self.run_worker(), 'retry')
        self.assertEqual(self.calls, [])

    def test_semantic_type_drift_is_rejected(self):
        context = {'date': DAY, 'track': 'H', 'number': '1'}
        for change in ({'absent': 'false'}, {'absent': 0}, {'absent': None},
                       {'monte': 'false'}, {'programNumber': True}, {'programNumber': 1.5},
                       {'programNumber': ''}, {'startNumber': True}, {'horseId': False}):
            with self.subTest(change=change), self.assertRaises(api.SchemaError):
                api.normalize('runners', [{**RUNNERS[0], **change}], context)
        missing_absent = {k:v for k,v in RUNNERS[0].items() if k != 'absent'}
        with self.assertRaises(api.SchemaError):
            api.normalize('runners', [missing_absent], context)
        for key in ('canceled', 'hasPublishedResults'):
            event = {**CALENDAR[0]['events'][0], key: 'false'}
            with self.subTest(key=key), self.assertRaises(api.SchemaError):
                api.normalize('calendar', [{'raceDate': DAY, 'events': [event]}], {'date': DAY})
        # Optional booleans can be absent, but a supplied value must be boolean.
        clean = api.normalize('runners', [dict(RUNNERS[0], programNumber=7, placing='1=')], context)
        self.assertEqual((clean[0]['programNumber'], clean[0]['placing']), ('7', '1='))

    def test_bad_scratch_refresh_pauses_and_preserves_previous_field(self):
        self.run_worker()
        before = [tuple(r) for r in self.db.execute('SELECT data FROM entries')]
        snapshots = self.db.execute('SELECT count(*) FROM snapshots').fetchone()[0]
        self.seed(refresh=True)
        self.payloads[api.runners_path(DAY, 'H', '1')] = [dict(RUNNERS[0], absent='false')]
        self.assertEqual(self.run_worker(), 'paused')
        self.assertEqual([tuple(r) for r in self.db.execute('SELECT data FROM entries')], before)
        self.assertEqual(self.db.execute('SELECT count(*) FROM snapshots').fetchone()[0], snapshots)
        self.assertEqual(self.db.execute('SELECT outcome FROM requests ORDER BY id DESC LIMIT 1').fetchone()[0], 'schema_error')

    def test_schema_change_does_not_erase_previous_data(self):
        self.run_worker()
        self.seed(refresh=True)
        self.payloads[api.runners_path(DAY, "H", "1")] = {"error": "not a field"}
        self.assertEqual(self.run_worker(), "paused")
        self.assertEqual(self.db.execute("SELECT count(*) FROM entries").fetchone()[0], 1)
        self.assertEqual(store.status(self.db)["jobs"]["failed"], 1)

    def test_mid_response_invalid_record_is_atomic(self):
        broken = copy.deepcopy(RUNNERS)
        broken.append(dict(RUNNERS[0], horseId="invalid", programNumber="8"))
        self.payloads[api.runners_path(DAY, "H", "1")] = broken
        self.assertEqual(self.run_worker(), "paused")
        self.assertEqual(self.db.execute("SELECT count(*) FROM entries").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM horses").fetchone()[0], 0)

    def test_interrupted_request_remains_pending_and_counts_against_budget(self):
        def interrupted(_):
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_worker(fetch=interrupted)
        self.assertEqual(self.db.execute("SELECT status FROM jobs").fetchone()[0], "pending")
        self.assertEqual(self.run_worker(daily_budget=1), "budget")

    def test_manual_pause_while_waiting_sends_nothing_more(self):
        self.run_worker(max_requests=1)
        def stop(delay):
            self.clock.sleep(delay)
            with self.db:
                collector.pause(self.db, "Provider requested a stop")
        self.assertEqual(self.run_worker(sleep=stop), "paused")
        self.assertEqual(len(self.calls), 1)

    def test_worker_lock_prevents_second_worker(self):
        with collector.worker_lock(self.path):
            with self.assertRaises(RuntimeError):
                with collector.worker_lock(self.path):
                    pass
        with collector.worker_lock(self.path):
            pass

    def test_cli_seed_is_offline_and_rejects_reversed_dates(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--db", str(self.path), "seed", "--from", DAY, "--to", DAY]), 0)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--db", str(self.path), "seed", "--from", DAY, "--to", "2025-10-21"]), 2)
        self.assertEqual(self.db.execute("SELECT count(*) FROM requests").fetchone()[0], 0)

    def test_cli_local_reads_and_resume_respects_server_cooldown(self):
        self.run_worker()
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--db", str(self.path), "race", "--date", DAY, "--track", "H", "--number", "1"]), 0)
        self.assertEqual(json.loads(output.getvalue())["entries"][0]["data"]["horseId"], HORSE_ID)
        with self.db:
            collector.pause(self.db, "HTTP 429", 9999999999)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--db", str(self.path), "resume"]), 2)
        self.assertIsNotNone(self.db.execute("SELECT paused_reason FROM control").fetchone()[0])

    def test_html_error_with_status_200_pauses_without_archiving(self):
        html = api.Response(200, b"<html>Access limited</html>", {"content-type": "text/html"})
        self.assertEqual(self.run_worker(fetch=lambda _: html), "paused")
        self.assertEqual(self.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 0)

    def test_missing_endpoint_is_failed_not_an_empty_success(self):
        self.assertEqual(self.run_worker(fetch=lambda _: api.Response(404)), "failed")
        self.assertEqual(store.status(self.db)["jobs"], {"failed": 1})
        self.assertEqual(self.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 0)

    def test_incomplete_http_transfer_is_a_transient_transport_failure(self):
        with patch("hippos_analyst.api.build_opener") as opener:
            opener.return_value.open.side_effect = IncompleteRead(b"partial")
            self.assertEqual(api.fetch(api.calendar_path(DAY)).status, 0)

    def test_http_error_preserves_retry_delay_and_closes_response(self):
        body = io.BytesIO(b"not archived")
        error = HTTPError(api.BASE_URL, 429, "Limited", {"Retry-After": "120"}, body)
        with patch("hippos_analyst.api.build_opener") as opener:
            opener.return_value.open.side_effect = error
            result = api.fetch(api.calendar_path(DAY))
        self.assertEqual(result.status, 429)
        self.assertEqual(result.headers["retry-after"], "120")
        self.assertEqual(result.body, b"")
        self.assertTrue(body.closed)

    def test_cli_emits_finnish_text_as_utf8_in_pipes(self):
        calendar = copy.deepcopy(CALENDAR)
        calendar[0]["events"][0]["name"] = "Tähtihevosen lähtö"
        self.payloads[api.calendar_path(DAY)] = calendar
        self.run_worker(max_requests=1)
        result = subprocess.run([sys.executable, "-m", "hippos_analyst", "--db", str(self.path),
                                 "calendar", "--from", DAY, "--to", DAY], capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))[0]["name"], "Tähtihevosen lähtö")

    def test_fetch_rejects_unrelated_endpoints_before_network_access(self):
        with patch("hippos_analyst.api.build_opener") as opener:
            for path in ("https://example.com/", "/person/123", "/race/../../private", "/race/2025-10-22/H/start/1?extra=1"):
                with self.assertRaises(ValueError):
                    api.fetch(path)
            opener.assert_not_called()

    def test_retains_tied_placings_and_disqualification_codes(self):
        records = [dict(RUNNERS[0], programNumber=str(i), horseId=str(i), placing=placing)
                   for i, placing in enumerate(["1", "1", "hll"], 1)]
        cleaned = api.normalize("runners", records, {"date": DAY, "track": "H", "number": "1"})
        self.assertEqual([r["placing"] for r in cleaned], ["1", "1", "hll"])

    def test_foreign_meetings_are_not_queued(self):
        self.payloads[api.calendar_path(DAY)] = [{"raceDate": DAY, "events": [dict(CALENDAR[0]["events"][0], finnishTrack=False)]}]
        self.run_worker()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM meetings").fetchone()[0], 0)

    def test_http_date_retry_after_and_invalid_value(self):
        self.assertEqual(collector.retry_after({"retry-after": "Thu, 23 Oct 2025 00:02:00 GMT"}, self.clock()), self.clock() + 120)
        self.assertEqual(collector.retry_after({"retry-after": "invalid"}, self.clock()), self.clock())

    def test_mismatched_race_and_duplicate_program_number_are_rejected(self):
        context = {"date": DAY, "track": "H", "number": "1"}
        for records in ([dict(RUNNERS[0], trackCode="T")], RUNNERS + RUNNERS):
            with self.assertRaises(api.SchemaError):
                api.normalize("runners", records, context)


if __name__ == "__main__":
    unittest.main()
