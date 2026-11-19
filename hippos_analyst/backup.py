"""Create a compressed, restorable backup of the runtime archive."""

import argparse
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from .prediction_store import path_for


def backup(database, destination, *, model=None, keep=None):
    if keep is not None and keep < 1:
        raise ValueError('Keep at least one completed backup')
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = destination / f'hippos-{stamp}-{uuid4().hex[:8]}.zip'
    with TemporaryDirectory(dir=destination) as staging:
        bundle = Path(staging) / 'backup.zip'
        with ZipFile(bundle, 'x', ZIP_DEFLATED, compresslevel=1) as output:
            # Archive observations referenced by saved forecasts must already exist.
            prediction_db = path_for(database)
            sources = [prediction_db, database] if prediction_db.exists() else [database]
            for source in sources:
                copy = Path(staging) / source.name
                with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as live:
                    with closing(sqlite3.connect(copy)) as snapshot:
                        live.backup(snapshot, pages=256)
                        if snapshot.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                            raise ValueError(f'Integrity check failed for {source.name}')
                output.write(copy, source.name)
                copy.unlink()
            if model is not None:
                for name in ('model.cbm', 'report.json'):
                    output.write(model / name, f'models/{model.name}/{name}')
        bundle.replace(target)
    if keep is not None:
        pattern = r'hippos-\d{8}T\d{12}Z-[0-9a-f]{8}\.zip'
        generations = sorted(p for p in destination.glob('hippos-*.zip') if re.fullmatch(pattern, p.name))
        for expired in generations[:-keep]:
            expired.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path('data/hippos.sqlite3'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', type=Path, help='Also include this deployed model and its report')
    parser.add_argument('--keep', type=int, help='Number of completed generations to retain in output')
    args = parser.parse_args()
    model = args.model
    if model is None and os.environ.get('HIPPOS_MODEL'):
        model = args.db.parent / 'models' / os.environ['HIPPOS_MODEL']
    if model is None and (args.db.parent / 'models' / 'active').is_dir():
        model = args.db.parent / 'models' / 'active'
    print(backup(args.db, args.output, model=model, keep=args.keep))


if __name__ == '__main__':
    main()
