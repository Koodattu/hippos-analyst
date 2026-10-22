"""Build a separate synthetic archive and measure complete local read responses.

Never contacts Hippos. Refuses to overwrite a database. Run from the repository:
python scripts/benchmark_archive.py --db data/growth-check.sqlite3
"""
import argparse
import json
import statistics
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hippos_analyst import api, store
from hippos_analyst.server import Archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    args = parser.parse_args()
    path = Path(args.db)
    if path.exists():
        parser.error('Choose a new file; existing archives are never overwritten')
    db = store.connect(path)
    def save(kind, path, context, records):
        store.enqueue(db, path, kind, context)
        rid = db.execute('INSERT INTO requests(path,started_at,status) VALUES(?,1,200)', (path,)).lastrowid
        job = db.execute('SELECT * FROM jobs WHERE path=?', (path,)).fetchone()
        store.save_response(db, job, records, rid, 1_700_000_000 + rid)
    try:
        with db:
            for i in range(1000):
                day = (date(2024, 1, 1) + timedelta(days=i)).isoformat()
                context = {'date': day, 'track': 'H'}
                meeting = {'date': day, 'trackCode': 'H', 'name': 'Synthetic benchmark',
                           'formattedTrackName': 'Testirata', 'finnishTrack': True}
                save('calendar', api.calendar_path(day), {'date': day}, [meeting])
                races = [{'date': day, 'trackCode': 'H', 'startNumber': str(n)} for n in range(1, 11)]
                save('races', api.races_path(day, 'H'), context, races)
                for race in races:
                    number = race['startNumber']
                    runners = [{**race, 'programNumber': str(n),
                                'horseId': str(i * 100 + (int(number) - 1) * 10 + n),
                                'horseName': f'Testihevonen {i:04}-{number}-{n}',
                                'absent': False, 'placing': str(n)} for n in range(1, 11)]
                    save('runners', api.runners_path(day, 'H', number),
                         {**context, 'number': number}, runners)
        checks = {}
        reads = {
            'overview': lambda a: a.overview(),
            'archive_first_page': lambda a: a.calendar('2024-01-01', day),
            'archive_last_page': lambda a: a.calendar('2024-01-01', day, offset=990),
            'one_day': lambda a: a.calendar(day, day),
            'race': lambda a: a.race(day, 'H', '1'),
            'horses_first_page': lambda a: a.horses('', 0),
            'horses_last_page': lambda a: a.horses('', 99990),
            'horse_search': lambda a: a.horses('0999-', 0),
        }
        for name, read in reads.items():
            samples = []
            for _ in range(3):
                started = time.perf_counter()
                result = read(Archive(db))
                body = json.dumps(result, ensure_ascii=False).encode('utf-8')
                samples.append(time.perf_counter() - started)
            if name == 'overview':
                assert (result['meeting_count'], result['race_count'], result['horse_count']) == (1000, 10000, 100000)
            elif name.startswith('archive_'):
                expected_offset = 0 if name.endswith('first_page') else 990
                assert (result['total'], result['offset']) == (1000, expected_offset)
                assert len(result['meetings']) == min(30, 1000 - expected_offset)
                assert result['meetings'][0]['date'] == (date(2024, 1, 1) + timedelta(days=expected_offset)).isoformat()
            elif name == 'one_day':
                assert result['total'] == 1 and len(result['meetings']) == 1
            elif name == 'race':
                assert len(result['entries']) == 10 and result['entries'][0]['horseId'] == '99901'
            else:
                assert result['total'] == (100 if name == 'horse_search' else 100000)
                assert len(result['horses']) == (10 if name == 'horses_last_page' else 30)
            checks[name] = {'seconds': {'median': statistics.median(samples), 'min': min(samples), 'max': max(samples)},
                            'bytes': len(body), 'verified': True}
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        print(json.dumps({'fixture': {'meetings': 1000, 'races': 10000, 'entries': 100000, 'horses': 100000},
                          'repetitions': 3, 'boundary': 'read model plus full JSON serialization; no HTTP',
                          'checks': checks}, indent=2))
    finally:
        db.close()


if __name__ == '__main__':
    main()
