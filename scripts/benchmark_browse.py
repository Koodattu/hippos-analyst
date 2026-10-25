"""Measure directory reads on a disposable copy; never modify the source archive."""

import argparse
import json
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hippos_analyst import browse, store
from hippos_analyst.server import Archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--today', default='2026-10-25')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / 'benchmark.sqlite3'
        source = sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True)
        copy = sqlite3.connect(target)
        source.backup(copy)
        source.close()
        copy.close()
        db = store.connect(target)
        try:
            archive = Archive(db)
            expected = {
                'horses': archive.horses('', 0)['total'],
                'people': sum(archive.people(role)['total'] for role in ('driver', 'trainer'))
                          + sum(archive.parties(role)['total'] for role in ('owner', 'breeder')),
            }
            report = {'entries': db.execute('SELECT count(*) FROM entries').fetchone()[0],
                      'boundary': 'read model plus JSON serialization; no HTTP/browser; cold means empty application cache',
                      'repetitions': 3, 'checks': {}}
            for kind in ('horses', 'people'):
                cache = {}
                for state in ('cold', 'warm'):
                    samples = []
                    for _ in range(3):
                        if state == 'cold':
                            cache.clear()
                        start = time.perf_counter()
                        result = browse.directory(Archive(db, cache), kind,
                                                  {'today': args.today, 'sort': 'name', 'dir': 'desc'})
                        body = json.dumps(result, ensure_ascii=False).encode('utf-8')
                        samples.append((time.perf_counter() - start) * 1000)
                        assert result['total'] == expected[kind]
                        assert len(result['rows']) == min(30, expected[kind])
                        names = [browse.name_key(row['name']) for row in result['rows']]
                        assert names == sorted(names, reverse=True)
                    report['checks'][kind + '_' + state] = {
                        'milliseconds': {key: round(fn(samples), 2)
                                         for key, fn in [('median', statistics.median), ('min', min), ('max', max)]},
                        'total': result['total'], 'rows': len(result['rows']), 'bytes': len(body), 'verified': True}
            print(json.dumps(report, indent=2))
        finally:
            db.close()


if __name__ == '__main__':
    main()
