"""Conservative display names for Hippos's shared person IDs."""

import json

from . import api


def visible_entries(db):
    # Read list heads together: resolving one race must not issue a query per
    # unrelated archived day. Removed meetings/races cannot supply name evidence.
    heads = {row[0]: json.loads(row[1]) for row in db.execute("""
        SELECT r.path,s.body FROM requests r JOIN snapshots s ON s.id=r.snapshot_id
        WHERE r.id IN (SELECT max(id) FROM requests WHERE outcome='ok'
            AND (path LIKE '/race/search/%' OR path LIKE '%/races') GROUP BY path)""")}
    keys = {(meeting['date'], str(meeting['trackCode']), str(race['startNumber']))
            for path, meetings in heads.items() if path.startswith('/race/search/')
            for meeting in meetings
            for race in heads.get(api.races_path(meeting['date'], str(meeting['trackCode'])), [])}
    for row in db.execute('SELECT date,track,race_number,data FROM entries'):
        if tuple(row[:3]) in keys:
            yield json.loads(row[3])


def full_driver_name(entry):
    parts = [entry.get('driverFirstName'), entry.get('driverLastName')]
    if all(isinstance(part, str) and part.strip() for part in parts):
        return ' '.join(part.strip() for part in parts)
    return None


def compatible(short, full):
    """Accept a given-name prefix only with the complete, matching surname."""
    short_parts = short.casefold().split(maxsplit=1)
    full_parts = full.casefold().split(maxsplit=1)
    if len(short_parts) != 2 or len(full_parts) != 2:
        return False
    if short_parts[1] != full_parts[1]:
        return False
    given = short_parts[0].rstrip('.')
    if '-' not in given:
        return bool(given) and full_parts[0].startswith(given)
    initials = [part.rstrip('.') for part in given.split('-')]
    names = full_parts[0].split('-')
    return len(initials) == len(names) and all(
        initial and name.startswith(initial) for initial, name in zip(initials, names))


class PersonNames:
    def __init__(self, entries):
        candidates = {}
        for entry in entries:
            for identity, name in ((entry.get('driverId'), full_driver_name(entry)),
                                   (entry.get('trainerId'), entry.get('trainerName'))):
                if identity is None or str(identity) in ('', '0') or not isinstance(name, str):
                    continue
                name = ' '.join(name.split())
                parts = name.split(maxsplit=1)
                if len(parts) == 2 and len(parts[0]) > 1 and not parts[0].endswith('.'):
                    candidates.setdefault(str(identity), {}).setdefault(name.casefold(), name)
        # Conflicting full names require review, even if an initial matches both.
        self.names = {identity: next(iter(names.values())) for identity, names in candidates.items()
                      if len(names) == 1}

    def resolve(self, identity, original):
        candidate = self.names.get(str(identity)) if identity is not None else None
        if candidate and (not original or compatible(original, candidate)):
            return candidate
        return original

    def entry(self, entry):
        # Keep source names available in the response as well as in stored snapshots.
        for role in ('driver', 'trainer'):
            original = entry.get(f'{role}Name')
            name = self.resolve(entry.get(f'{role}Id'), original)
            if name != original:
                entry[f'{role}SourceName'] = original
                entry[f'{role}Name'] = name
        return entry
