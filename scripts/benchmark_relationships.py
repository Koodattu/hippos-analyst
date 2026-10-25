"""Create a separate 10,001-profile synthetic archive; no network or overwrites."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hippos_analyst import api, store
from hippos_analyst.server import Archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    args = parser.parse_args()
    if Path(args.db).exists():
        parser.error('Choose a new file; existing archives are never overwritten')
    db = store.connect(args.db)
    try:
        with db:
            for n in range(10001):
                value = str(100000+n)
                raw = {'id':value,'name':f'Testihevonen {n:05}',
                       'ownerName':f'Testiomistaja Ääni {n % 200:03}' if n else None,
                       'breederName':f'Testikasvattaja {n % 500:03}' if n else None,
                       'sire':{'id':'100000','name':'Testihevonen 00000'} if n else None,
                       'dam':{'name':'Emän nimi ilman tunnusta'} if n else None,
                       'birthDate':'2020-05-01','birthDateAccurate':True,'gender':'O','dead':False}
                records = api.normalize('profile',raw,{'id':value})
                store.enqueue_profile(db,value,0)
                path = api.profile_path(value)
                rid = db.execute('INSERT INTO requests(path,started_at,status) VALUES(?,?,200)',(path,1_700_000_000+n)).lastrowid
                job = db.execute('SELECT * FROM jobs WHERE path=?',(path,)).fetchone()
                store.save_response(db,job,records,rid,1_700_000_000+n)
        owner = Archive(db).parties('owner')['parties'][0]['id']
        reads = {'owners':lambda a:a.parties('owner'),
                 'breeders_page_two':lambda a:a.parties('breeder','',30),
                 'owner_horses_page_two':lambda a:a.party('owner',owner,30),
                 'offspring_page_two':lambda a:a.horse('100000',30)}
        checks = {}
        for name, read in reads.items():
            durations = []
            for _ in range(3):
                start = time.perf_counter()
                result = read(Archive(db))
                body = json.dumps(result,ensure_ascii=False).encode()
                durations.append(time.perf_counter()-start)
            if name == 'owners':
                assert result['total']==200 and len(result['parties'])==30
            elif name == 'breeders_page_two':
                assert result['total']==500 and result['offset']==30 and len(result['parties'])==30
            elif name == 'owner_horses_page_two':
                assert result['total']==50 and result['offset']==30 and len(result['horses'])==20
            else:
                assert result['offspring']['total']==10000 and len(result['offspring']['horses'])==30
                assert result['offspring']['offset']==30
            checks[name] = {'median_ms':statistics.median(durations)*1000,'min_ms':min(durations)*1000,
                            'max_ms':max(durations)*1000,'bytes':len(body),'verified':True}
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        print(json.dumps({'profiles':10001,'owners':200,'breeders':500,'checks':checks},indent=2))
    finally:
        db.close()


if __name__ == '__main__':
    main()
