"""Create a new, clearly synthetic local archive for product verification; no network."""
import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hippos_analyst import api, store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--today', type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    if Path(args.db).exists():
        parser.error('Choose a new file; existing archives are never overwritten')
    db = store.connect(args.db)
    now = datetime.combine(args.today, datetime.min.time(), timezone.utc).timestamp()
    def save(kind, day, records, track='H', number='1'):
        context = {'date': day}
        path = api.calendar_path(day)
        if kind in ('races', 'runners'):
            context['track'] = track
            path = api.races_path(day, track)
        if kind == 'runners':
            context['number'] = number
            path = api.runners_path(day, track, number)
        store.enqueue(db, path, kind, context)
        rid = db.execute('INSERT INTO requests(path,started_at,status) VALUES(?,?,200)', (path, now)).lastrowid
        job = db.execute('SELECT * FROM jobs WHERE path=?', (path,)).fetchone()
        store.save_response(db, job, records, rid, now)
    try:
        with db:
            for offset in [-28, -21, -14, -7, -3, -1, 0, 2, 4]:
                day = (args.today + timedelta(days=offset)).isoformat()
                base = {'date': day, 'trackCode': 'H', 'finnishTrack': True}
                save('calendar', day, [{**base, 'name': 'Synteettinen harjoitusravipäivä',
                     'formattedTrackName': 'Testirata, Esimerkkikaupunki', 'startTime': '18:00:00',
                     'canceled': offset == 4, 'hasPublishedResults': offset <= 0}])
                races = [{**base, 'startNumber': n, 'baseDistance': '2140', 'startForm': 'RYHMALAHTO',
                          'eventType': 'LAMMINVERISET', 'startType': 'KOE' if n == '21' or offset == -3 else 'TOTO',
                          'plannedTime': '18:10'} for n in ['1', '2', '21']]
                save('races', day, races)
                for race in races:
                    number = race['startNumber']
                    if offset == 4 and number != '1':
                        continue  # Deliberately incomplete future meeting.
                    runners = []
                    for n in range(1, 9):
                        placing = '0' if offset > 0 else ('hll' if n == 3 else '1=' if n <= 2 else str(n))
                        runners.append({**race, 'programNumber': str(n), 'horseId': str(1000 + (int(number) - 1) * 8 + n),
                            'horseName': ['Esimerkin Äänekäs Tähti', 'Pitkän Nimen Testihevonen'][n % 2] + f' {n}',
                            'horseBreed': 'L', 'horseRegistrationCountry': 'FI',
                            'driverId': str(900 + n % 4), 'driverName': f'Testiohjastaja Äänekäs {n % 4}',
                            'trainerId': str(800 + n % 2), 'trainerName': f'Testivalmentaja Pitkä-Nimi {n % 2}',
                            'distance': '2140', 'lane': str(n), 'placing': placing,
                            'shortKilometerTime': '0' if offset > 0 else '16,4a',
                            'price': '0' if offset > 0 else '120', 'absent': n == 8,
                            'shoesFront': 'KEN', 'shoesBack': 'KEN'})
                    save('runners', day, runners, number=number)
            empty_day = (args.today - timedelta(days=2)).isoformat()
            save('calendar', empty_day, [])
            pending_day = (args.today + timedelta(days=5)).isoformat()
            store.enqueue(db, api.calendar_path(pending_day), 'calendar', {'date': pending_day})
        print(f'Synthetic archive ready: {args.db}; reference day {args.today}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
