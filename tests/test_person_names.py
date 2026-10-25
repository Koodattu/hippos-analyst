import json
import unittest

from hippos_analyst import api, browse
from hippos_analyst.person_names import PersonNames
from hippos_analyst.server import Archive
import test_server
from test_server import DAY, HORSE


class PersonNameTests(unittest.TestCase):
    setUp = test_server.ArchiveTests.setUp
    tearDown = test_server.ArchiveTests.tearDown
    save = test_server.ArchiveTests.save

    def test_shared_id_expands_names_everywhere_without_merging_roles_or_sources(self):
        self.save('runners', [{**self.runner, 'driverId': '2576121652984750609',
                              'driverName': 'A Ala-Rantala', 'trainerId': '2576121652984750609',
                              'trainerName': 'Antti Ala-Rantala'}])
        identity = '2576121652984750609'
        before = self.db.execute('SELECT data FROM entries').fetchone()[0]
        archive = Archive(self.db)
        for query in ('Antti', 'A Ala-Rantala'):
            result = archive.people('driver', query)
            self.assertEqual(result['total'], 1)
            self.assertEqual(result['people'][0]['name'], 'Antti Ala-Rantala')
            rows = browse.directory(Archive(self.db), 'people', {'today': DAY, 'q': query})['rows']
            self.assertEqual(rows[0]['name'], 'Antti Ala-Rantala')
        rows = browse.directory(Archive(self.db), 'people', {'today': DAY})['rows']
        self.assertEqual({(r['role'], r['id']) for r in rows}, {('driver', identity), ('trainer', identity)})
        self.assertEqual(archive.person('driver', identity, DAY)['person']['name'], 'Antti Ala-Rantala')
        activity = browse.activity(Archive(self.db), {'today': DAY, 'role': 'driver', 'id': identity})
        self.assertEqual(activity['person']['source_name'], 'A Ala-Rantala')
        self.assertEqual(activity['person']['name'], 'Antti Ala-Rantala')
        entries = [archive.race(DAY, 'H', '1')['entries'][0],
                   archive.horse(HORSE)['starts'][0]['data'],
                   archive.person('driver', identity, DAY)['starts'][0]['data'],
                   activity['rows'][0]['data']]
        for entry in entries:
            self.assertEqual(entry['driverName'], 'Antti Ala-Rantala')
            self.assertEqual(entry['driverSourceName'], 'A Ala-Rantala')
        self.assertEqual(self.db.execute('SELECT data FROM entries').fetchone()[0], before)
        snapshot = json.loads(self.db.execute('SELECT body FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()[0])
        self.assertEqual(snapshot[0]['driverName'], 'A Ala-Rantala')

    def test_explicit_source_names_survive_import_and_resolve_without_trainer_match(self):
        raw = {**self.runner, 'driverId': '295190086041368698', 'driverName': 'T Kylliäinen',
               'driverFirstName': 'Tommi', 'driverLastName': 'Kylliäinen', 'ownerCity': 'Not retained'}
        parsed = api.normalize('runners', [raw], {'date': DAY, 'track': 'H', 'number': '1'})
        self.assertEqual(parsed[0]['driverFirstName'], 'Tommi')
        self.assertEqual(parsed[0]['driverLastName'], 'Kylliäinen')
        self.assertNotIn('ownerCity', parsed[0])
        self.save('runners', parsed)
        self.assertEqual(Archive(self.db).people('driver', 'Tommi')['people'][0]['name'], 'Tommi Kylliäinen')
        self.assertEqual(Archive(self.db).people('trainer')['total'], 0)

    def test_ambiguous_incompatible_missing_and_different_ids_are_not_guessed(self):
        names = PersonNames([
            {'trainerId': '1', 'trainerName': 'Antti Ala-Rantala'},
            {'trainerId': '2', 'trainerName': 'Antti Korpi'},
            {'trainerId': '2', 'trainerName': 'Ari Korpi'},
            {'trainerId': '3', 'trainerName': 'Jussi Hautanen'},
            {'trainerId': '0', 'trainerName': 'Nolla Nimi'},
            {'driverId': '4', 'driverFirstName': 'Matti'},
        ])
        for identity, original in [('01', 'A Ala-Rantala'), ('1', 'J Ala-Rantala'),
                                   ('1', 'A Rantala'), ('2', 'A Korpi'), (None, 'A Ala-Rantala'),
                                   ('0', 'N Nimi'), ('4', 'M Malli')]:
            self.assertEqual(names.resolve(identity, original), original)
        self.assertEqual(names.resolve('1', 'A. Ala-Rantala'), 'Antti Ala-Rantala')
        self.assertEqual(names.resolve('3', 'Ju Hautanen'), 'Jussi Hautanen')

    def test_removed_and_corrected_evidence_invalidates_cache(self):
        self.save('runners', [{**self.runner, 'driverId': '123', 'driverName': 'A Korpi'}])
        self.save('runners', [{**self.runner, 'trainerId': '123', 'trainerName': 'Antti Korpi'}], number='2')
        cache = {}
        def name():
            return browse.directory(Archive(self.db, cache), 'people',
                                    {'today': DAY, 'role': 'driver'})['rows'][0]['name']
        self.assertEqual(name(), 'Antti Korpi')
        self.save('races', self.races[:1])
        self.assertEqual(name(), 'A Korpi')
        self.save('races', self.races)
        self.save('runners', [{**self.runner, 'trainerId': '123', 'trainerName': 'Jukka Korpi'}], number='2')
        self.assertEqual(name(), 'A Korpi')
        self.save('calendar', [])
        self.assertEqual(Archive(self.db, cache).person_names().resolve('123', 'J Korpi'), 'J Korpi')

    def test_hyphenated_initials_match_each_given_name_component(self):
        self.save('runners', [{**self.runner, 'driverId': '7965638283016593584',
                              'driverName': 'A-S Hanttu', 'trainerId': '7965638283016593584',
                              'trainerName': 'Anni-Sofia Hanttu'}])
        archive = Archive(self.db)
        self.assertEqual(archive.people('driver', 'A-S Hanttu')['people'][0]['name'], 'Anni-Sofia Hanttu')
        self.assertEqual(archive.race(DAY, 'H', '1')['entries'][0]['driverName'], 'Anni-Sofia Hanttu')
        names = archive.person_names()
        self.assertEqual(names.resolve('7965638283016593584', 'A.-S. Hanttu'), 'Anni-Sofia Hanttu')
        for identity, original in [('7965638283016593584', 'A-P Hanttu'),
                                   ('7965638283016593584', 'A-S-P Hanttu'),
                                   ('7965638283016593584', 'A- Hanttu'),
                                   ('7965638283016593584', 'A-S Laurila'),
                                   ('other', 'A-S Hanttu')]:
            self.assertEqual(names.resolve(identity, original), original)

    def test_display_names_are_sorted_before_pagination(self):
        self.save('runners', [{**self.runner, 'programNumber': str(n),
                              'driverId': str(n), 'driverName': f'A Surname{n:02}',
                              'trainerId': str(n), 'trainerName': f'Antti Surname{n:02}'}
                             for n in range(1, 36)] +
                             [{**self.runner, 'programNumber': '36', 'driverId': '36',
                               'driverName': 'Aku Zebra'}])
        directory = browse.directory(Archive(self.db), 'people', {'today': DAY, 'role': 'driver'})
        self.assertEqual(directory['total'], 36)
        self.assertEqual(directory['rows'][0]['name'], 'Aku Zebra')
        self.assertEqual(Archive(self.db).people('driver')['people'][0]['name'], 'Aku Zebra')
        activity = browse.activity(Archive(self.db), {'today': DAY, 'role': 'horse', 'id': HORSE,
                                                     'sort': 'driver', 'dir': 'asc'})
        self.assertEqual(activity['rows'][0]['data']['driverName'], 'Aku Zebra')


if __name__ == '__main__':
    unittest.main()
