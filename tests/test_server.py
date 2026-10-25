import json
import tempfile
import threading
import unittest
from datetime import date, timedelta
from http.client import HTTPConnection
from pathlib import Path

from hippos_analyst import api, store
from hippos_analyst.server import Archive, endpoint, make_server

DAY = "2026-10-23"
HORSE = "7616196635396808820"


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "sample.sqlite3"
        self.db = store.connect(self.path)
        self.time = 100
        self.meeting = {"date": DAY, "trackCode": "H", "trackCity": "Helsinki", "name": "Test", "canceled": False}
        self.races = [{"date": DAY, "trackCode": "H", "startNumber": n} for n in ("1", "10", "2")]
        self.runner = {"date": DAY, "trackCode": "H", "startNumber": "1", "programNumber": "7", "horseId": HORSE,
                       "horseName": "Äänekäs", "placing": "0", "absent": False, "price": "0"}
        self.save("calendar", [self.meeting])
        self.save("races", self.races)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def save(self, kind, records, day=DAY, track='H', number='1'):
        self.time += 10
        context = {"date": day}
        path = api.calendar_path(day)
        if kind in ("races", "runners"):
            context["track"] = track
            path = api.races_path(day, track)
        if kind == "runners":
            context["number"] = number
            path = api.runners_path(day, track, number)
        with self.db:
            store.enqueue(self.db, path, kind, context, refresh=True)
            request_id = self.db.execute("INSERT INTO requests(path,started_at,status) VALUES(?,?,200)", (path, self.time)).lastrowid
            store.save_response(self.db, self.db.execute("SELECT * FROM jobs WHERE path=?", (path,)).fetchone(), records, request_id, self.time)

    def test_saved_horses_are_bounded_and_return_only_current_or_future_entries(self):
        self.save("runners", [self.runner])
        data = endpoint(Archive(self.db), '/api/saved', {'ids': [HORSE + ',999'], 'from': [DAY]})
        self.assertEqual(data['horses'][0]['horse']['id'], HORSE)
        self.assertEqual(len(data['horses'][0]['starts']), 1)
        self.assertEqual(data['missing'], ['999'])
        self.assertEqual(Archive(self.db).saved([HORSE], '2026-10-24')['horses'][0]['starts'], [])
        for ids in ['x', ','.join(str(n) for n in range(101))]:
            with self.assertRaises(ValueError):
                endpoint(Archive(self.db), '/api/saved', {'ids': [ids], 'from': [DAY]})
        self.assertEqual(Archive(self.db).saved([], DAY), {'horses': [], 'missing': []})

    def test_people_search_identity_and_latest_names(self):
        runners = [{**self.runner, 'programNumber': str(n), 'horseId': str(n),
                    'driverId': str(n), 'driverName': 'Ääni %' if n < 3 else f'Ohjastaja {n:02}',
                    'trainerId': '1', 'trainerName': 'Eri roolin nimi'} for n in range(1, 36)]
        self.save('runners', runners)
        first = Archive(self.db).people('driver', '', 0)
        last = Archive(self.db).people('driver', '', 30)
        self.assertEqual((first['total'], len(first['people']), len(last['people'])), (35, 30, 5))
        self.assertFalse({p['id'] for p in first['people']} & {p['id'] for p in last['people']})
        self.assertEqual(Archive(self.db).people('driver', 'ääNI %', 0)['total'], 2)
        self.assertEqual(Archive(self.db).people('driver', '_', 0)['total'], 0)
        trainer = Archive(self.db).people('trainer', '', 0)['people'][0]
        self.assertEqual((trainer['name'], trainer['horses'], trainer['entries']), ('Eri roolin nimi', 35, 35))
        self.save('runners', [{**runners[0], 'driverName': 'Uusi nimi'}], number='2')
        self.assertEqual(Archive(self.db).people('driver', 'Uusi', 0)['people'][0]['id'], '1')
        self.assertEqual(Archive(self.db).people('driver', 'ääNI %', 0)['total'], 1)

    def test_people_visibility_corrections_and_missing_ids(self):
        self.save('runners', [{**self.runner, 'driverId': '123', 'driverName': 'Nimi'},
                              {**self.runner, 'programNumber': '8', 'driverName': 'Nimi'}])
        self.assertEqual(Archive(self.db).people('driver', '', 0)['total'], 1)
        self.save('races', self.races[1:])
        self.assertEqual(Archive(self.db).people('driver', '', 0)['total'], 0)
        with self.assertRaises(LookupError):
            Archive(self.db).person('driver', '123', DAY)
        self.save('races', self.races)
        self.save('runners', [{**self.runner, 'driverId': '456', 'driverName': 'Korjattu'}])
        self.assertEqual(Archive(self.db).people('driver', '', 0)['people'][0]['id'], '456')
        self.save('calendar', [])
        self.assertEqual(Archive(self.db).people('driver', '', 30)['offset'], 0)

    def test_person_results_upcoming_and_bounded_pages(self):
        rows = [{**self.runner, 'programNumber': str(n), 'horseId': str(n),
                 'driverId': '123', 'driverName': 'Ohjastaja', 'trainerId': '456',
                 'trainerName': 'Valmentaja', 'placing': '0'} for n in range(1, 36)]
        rows.extend([{**rows[0], 'programNumber': '36', 'placing': '1='},
                     {**rows[0], 'programNumber': '37', 'placing': 'hll'},
                     {**rows[0], 'programNumber': '38', 'placing': '1', 'absent': True}])
        self.save('runners', rows)
        data = Archive(self.db).person('driver', '123', DAY)
        self.assertEqual(data['summary'], {'entries': 38, 'horses': 35, 'results': 2, 'wins': 1, 'upcoming': 36})
        self.assertEqual((data['period'], data['total'], len(data['starts'])), ('upcoming', 36, 30))
        self.assertEqual(data['starts'][0]['data']['trainerId'], '456')
        last = Archive(self.db).person('driver', '123', DAY, 'upcoming', 30)
        self.assertEqual(len(last['starts']), 6)
        history = Archive(self.db).person('driver', '123', DAY, 'history')
        self.assertEqual([s['data']['placing'] for s in history['starts']], ['1=', 'hll'])
        past = Archive(self.db).person('driver', '123', '2026-10-24')
        self.assertEqual((past['period'], past['total']), ('history', 38))
        with self.assertRaises(LookupError):
            Archive(self.db).person('trainer', '123', DAY)

    def test_people_endpoint_validation(self):
        for path, params in [('/api/people', {'role': ['owner']}),
                             ('/api/people', {'role': ['driver'], 'offset': ['-1']}),
                             ('/api/people', {'role': ['driver'], 'q': ['a' * 201]}),
                             ('/api/person', {'role': ['trainer'], 'id': ['1'], 'from': [DAY], 'period': ['invalid']}),
                             ('/api/person', {'role': ['driver'], 'id': ['1'], 'from': ['bad']})]:
            with self.subTest(params=params), self.assertRaises(ValueError):
                endpoint(Archive(self.db), path, params)

    def test_coverage_distinguishes_missing_empty_partial_and_complete_days(self):
        self.save('runners', [self.runner])
        empty_day = '2026-10-24'
        pending_day = '2026-10-25'
        self.save('calendar', [], day=empty_day)
        with self.db:
            store.enqueue(self.db, api.calendar_path(pending_day), 'calendar', {'date': pending_day})
        data = Archive(self.db).coverage()
        self.assertEqual(data['total'], 3)
        pending, empty, partial = data['days']
        self.assertIsNone(pending['fetched_at'])
        self.assertEqual(empty['meetings'], 0)
        self.assertIsNotNone(empty['fetched_at'])
        self.assertEqual((partial['fields'], partial['races'], partial['missing_lists']), (1, 3, 0))
        self.save('runners', [], number='2')
        self.save('runners', [], number='10')
        complete = Archive(self.db).coverage()['days'][2]
        self.assertEqual(complete['fields'], complete['races'])
        for n in range(35):
            day = (date(2026, 8, 1) + timedelta(days=n)).isoformat()
            self.save('calendar', [], day=day)
        self.assertEqual(len(Archive(self.db).coverage()['days']), 30)
        page = Archive(self.db).coverage(30)
        self.assertEqual(len(page['days']), 8)
        self.assertTrue(all(d['date'] < '2026-09-01' for d in page['days']))

    def test_calendar_filters_and_coverage(self):
        data = Archive(self.db).calendar(DAY, DAY)
        self.assertEqual(len(data["days"]), 1)
        self.assertEqual(data["meetings"][0]["race_count"], 3)
        self.assertEqual(data["meetings"][0]["collected_races"], 0)
        self.assertEqual(Archive(self.db).calendar(DAY, DAY, "LA")["meetings"], [])
        self.assertEqual(Archive(self.db).calendar("2026-10-24", "2026-10-25")["days"], [])
        with self.assertRaises(ValueError):
            Archive(self.db).calendar("2026-10-25", DAY)

    def test_uncollected_empty_and_upcoming_are_distinct(self):
        self.assertIsNone(Archive(self.db).race(DAY, "H", "1")["race"]["field_fetched_at"])
        self.save("runners", [])
        empty = Archive(self.db).race(DAY, "H", "1")
        self.assertIsNotNone(empty["race"]["field_fetched_at"])
        self.assertEqual(empty["entries"], [])
        self.save("runners", [self.runner])
        upcoming = Archive(self.db).race(DAY, "H", "1")
        self.assertFalse(upcoming["race"]["has_results"])
        self.assertEqual(upcoming["entries"][0]["horseId"], HORSE)
        self.runner["placing"] = "1="
        self.save("runners", [self.runner])
        self.assertTrue(Archive(self.db).race(DAY, "H", "1")["race"]["has_results"])

    def test_races_sort_numerically(self):
        self.assertEqual([r["number"] for r in Archive(self.db).meeting(DAY, "H")["races"]], ["1", "2", "10"])

    def test_race_form_is_five_visible_starts_before_the_meeting_day(self):
        self.save('runners', [self.runner])
        for offset in range(1, 8):
            day = (date.fromisoformat(DAY) - timedelta(days=offset)).isoformat()
            self.save('calendar', [{**self.meeting, 'date': day}], day=day)
            self.save('races', [{**self.races[0], 'date': day}], day=day)
            self.save('runners', [{**self.runner, 'date': day, 'placing': str(offset)}], day=day)
        self.save('calendar', [], day='2026-10-22')
        form = Archive(self.db).race(DAY, 'H', '1')['form'][HORSE]
        self.assertEqual([s['date'] for s in form], ['2026-10-21','2026-10-20','2026-10-19','2026-10-18','2026-10-17'])
        self.assertEqual([s['data']['placing'] for s in form], ['2','3','4','5','6'])
        self.assertEqual(Archive(self.db).race('2026-10-16', 'H', '1')['form'][HORSE], [])
        self.assertEqual(len(Archive(self.db).horse(HORSE)['starts']), 7)

    def test_scoped_reads_do_not_expand_with_unrelated_history(self):
        self.save('runners', [self.runner])
        def measured(read):
            queries = []
            self.db.set_trace_callback(queries.append)
            try:
                result = read(Archive(self.db))
            finally:
                self.db.set_trace_callback(None)
            return result, len(queries)
        reads = [lambda a: a.calendar(DAY, DAY, 'H'), lambda a: a.race(DAY, 'H', '1')]
        before = [measured(read) for read in reads]
        for offset in range(1, 41):
            day = (date.fromisoformat(DAY) - timedelta(days=offset)).isoformat()
            self.save('calendar', [{**self.meeting, 'date':day}], day=day)
            self.save('races', [{**self.races[0], 'date':day}], day=day)
            self.save('runners', [{**self.runner, 'date':day, 'horseId':str(offset)}], day=day)
        # Also exclude another track on the requested day.
        self.save('calendar', [self.meeting, {**self.meeting, 'trackCode':'T'}])
        calendar_time = self.time
        self.save('races', [{**self.races[0], 'trackCode':'T'}], track='T')
        # Only the source observation timestamp changed on the target calendar.
        for read, (expected, count) in zip(reads, before):
            actual, new_count = measured(read)
            if 'days' in actual:
                expected['days'][0]['fetched_at'] = calendar_time
                expected['meetings'][0]['fetched_at'] = calendar_time
            else:
                expected['meeting']['fetched_at'] = calendar_time
            self.assertEqual(actual, expected)
            self.assertLessEqual(new_count, count + 2)

    def test_overview_counts_latest_membership_without_loading_fields(self):
        self.save('runners', [self.runner])
        for races, expected in [(self.races, 3), (self.races[1:], 2), (self.races, 3)]:
            self.save('races', races)
            archive = Archive(self.db)
            overview = archive.overview()
            self.assertEqual((overview['meeting_count'], overview['race_count']), (1, expected))
            self.assertFalse(any('/start/' in path for path in archive.heads))
        self.save('calendar', [])
        self.assertEqual(Archive(self.db).overview()['race_count'], 0)
        self.save('calendar', [self.meeting])
        self.assertEqual(Archive(self.db).overview()['race_count'], 3)

    def test_existing_database_gets_latest_success_lookup_index(self):
        # Simulate reopening a v1 archive created before the additive index.
        with self.db:
            self.db.execute('DROP INDEX IF EXISTS requests_path_success')
        self.db.close()
        self.db = store.connect(self.path)
        plan = ' '.join(r[3] for r in self.db.execute("EXPLAIN QUERY PLAN SELECT s.body,r.finished_at FROM requests r JOIN snapshots s ON s.id=r.snapshot_id WHERE r.path=? AND r.outcome='ok' ORDER BY r.id DESC LIMIT 1", (api.calendar_path(DAY),)))
        self.assertIn('requests_path_success', plan)
        self.assertNotIn('SCAN r', plan)
        self.assertEqual(len(Archive(self.db).calendar(DAY,DAY)['meetings']), 1)

    def test_calendar_includes_races_for_direct_navigation_without_runner_payloads(self):
        self.save("runners", [self.runner])
        races = Archive(self.db).calendar(DAY, DAY)["meetings"][0]["races"]
        self.assertEqual([r["number"] for r in races], ["1", "2", "10"])
        self.assertEqual(races[0]["entry_count"], 1)
        self.assertIsNone(races[1]["entry_count"])
        self.assertNotIn(HORSE, json.dumps(races))

    def test_calendar_pages_visible_meetings_before_expanding_fields(self):
        for offset in range(1, 65):
            day = (date.fromisoformat(DAY) - timedelta(days=offset)).isoformat()
            self.save('calendar', [{**self.meeting, 'date': day}], day=day)
            self.save('races', [{**self.races[0], 'date': day}], day=day)
        # A removed calendar must not consume a page slot.
        self.save('calendar', [], day='2026-10-01')
        pages = []
        for offset in (0, 30, 60):
            archive = Archive(self.db)
            page = archive.calendar('2026-01-01', DAY, 'H', offset)
            self.assertEqual((page['total'], page['offset'], page['limit']), (64, offset, 30))
            self.assertLessEqual(len(page['meetings']), 30)
            fields = [p for p in archive.heads if '/start/' in p]
            self.assertLessEqual(len(fields), 32)  # Last day has three races.
            pages.extend(m['date'] for m in page['meetings'])
        self.assertEqual(len(set(pages)), 64)
        self.assertEqual(pages, sorted(pages))
        self.assertNotIn('2026-10-01', pages)
        # A stale URL after membership removal lands on the last available page.
        self.assertEqual(Archive(self.db).calendar('2026-01-01', DAY, 'H', 90)['offset'], 60)
        empty = Archive(self.db).calendar('2026-01-01', DAY, 'M', 30)
        self.assertEqual((empty['offset'], empty['total'], empty['meetings']), (0, 0, []))
        via_http = endpoint(Archive(self.db), '/api/calendar', {'from': ['2026-01-01'], 'to': [DAY], 'offset': ['30']})
        self.assertEqual(via_http['offset'], 30)
        for offset in ('-1', 'x', '10000001'):
            with self.assertRaises(ValueError):
                endpoint(Archive(self.db), '/api/calendar', {'from': ['2026-01-01'], 'to': [DAY], 'offset': [offset]})

    def test_removed_meeting_is_hidden_and_restored_snapshot_is_current(self):
        self.save("runners", [self.runner])
        self.save("calendar", [])
        self.assertEqual(Archive(self.db).calendar(DAY, DAY)["meetings"], [])
        self.assertEqual(Archive(self.db).horse(HORSE)["starts"], [])
        with self.assertRaises(LookupError):
            Archive(self.db).race(DAY, "H", "1")
        self.save("calendar", [self.meeting])  # Reuses an older deduplicated snapshot.
        self.assertEqual(len(Archive(self.db).horse(HORSE)["starts"]), 1)
        self.assertEqual(len(Archive(self.db).calendar(DAY, DAY)["meetings"]), 1)

    def test_removed_race_is_hidden_without_deleting_archive(self):
        self.save("runners", [self.runner])
        self.save("races", self.races[1:])
        self.assertEqual(Archive(self.db).calendar(DAY, DAY)['meetings'][0]["race_count"], 2)
        self.assertEqual(Archive(self.db).horse(HORSE)["starts"], [])
        self.assertEqual(self.db.execute("SELECT count(*) FROM entries").fetchone()[0], 1)
        with self.assertRaises(LookupError):
            Archive(self.db).race(DAY, "H", "1")

    def test_finnish_casefold_literal_search_and_pagination(self):
        self.save("runners", [self.runner])
        self.assertEqual(Archive(self.db).horses("ääNE", 0)["horses"][0]["id"], HORSE)
        self.assertEqual(Archive(self.db).horses("%", 0)["total"], 0)
        self.assertEqual(Archive(self.db).horses("_", 0)["total"], 0)
        with self.db:
            self.db.executemany("INSERT INTO horses VALUES(?,?,'L','FI',100)", [(str(i), f"Horse {i:02}") for i in range(35)])
        first = Archive(self.db).horses("Horse", 0)
        last = Archive(self.db).horses("Horse", 30)
        self.assertEqual((first["total"], len(first["horses"]), len(last["horses"])), (35, 30, 5))
        self.assertFalse({h["id"] for h in first["horses"]} & {h["id"] for h in last["horses"]})

    def test_invalid_and_missing_requests(self):
        for path, params in [("/api/calendar", {"from": ["20261023"], "to": [DAY]}),
                             ("/api/horses", {"offset": ["-1"]}),
                             ("/api/horses", {"offset": ["999999999999999999999999999"]}),
                             ("/api/horse", {})]:
            with self.subTest(path=path, params=params), self.assertRaises(ValueError):
                endpoint(Archive(self.db), path, params)
        with self.assertRaises(LookupError):
            Archive(self.db).horse("missing")

    def test_http_contract_and_no_database_exposure(self):
        self.save("runners", [self.runner])
        before = store.status(self.db)
        server = make_server(self.path, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            def get(path, host=None):
                client = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                client.request("GET", path, headers={"Host": host} if host else {})
                response = client.getresponse()
                data = response.read()
                result = response.status, response.getheader("Content-Type"), data
                client.close()
                return result
            status, content_type, body = get("/")
            self.assertEqual(status, 200)
            self.assertIn("text/html", content_type)
            self.assertIn(b'lang="fi"', body)
            self.assertEqual(get("/app.mjs")[0], 200)
            status, _, body = get("/api/horse?id=" + HORSE)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["horse"]["name"], "Äänekäs")
            self.assertEqual(json.loads(body)["horse"]["id"], HORSE)
            for path, expected in [("/api/horse?id=missing", 404), ("/api/calendar", 400),
                                   ("/../data/hippos.sqlite3", 404), ("/data/hippos.sqlite3", 404),
                                   ("/api/unknown", 404)]:
                self.assertEqual(get(path)[0], expected, path)
            self.assertEqual(get("/api/overview", "untrusted.example")[0], 403)
            self.assertEqual(store.status(self.db), before)
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
