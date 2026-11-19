"""Conservative display names for Hippos's shared person IDs."""

import json
from itertools import chain


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
    @classmethod
    def from_archive(cls, db, entry_filter):
        # The indexes cover the name fields. Only distinct names cross
        # into Python, even when a driver has appeared in thousands of races.
        drivers = (dict(driverId=row[0], driverFirstName=row[1], driverLastName=row[2])
                   for row in db.execute(f"""SELECT DISTINCT CAST(json_extract(data,'$.driverId') AS TEXT),
                       nullif(json_extract(data,'$.driverFirstName'),''),nullif(json_extract(data,'$.driverLastName'),'')
                       FROM entries INDEXED BY entries_driver_names WHERE {entry_filter}"""))
        trainers = (dict(trainerId=row[0], trainerName=row[1])
                    for row in db.execute(f"""SELECT DISTINCT CAST(json_extract(data,'$.trainerId') AS TEXT),
                        nullif(json_extract(data,'$.trainerName'),'') FROM entries INDEXED BY entries_trainer_names
                        WHERE {entry_filter}"""))
        profiles = (json.loads(row[0]) for row in db.execute(
            "SELECT data FROM horse_profiles WHERE json_extract(data,'$.trainerId') IS NOT NULL"))
        return cls(chain(drivers, trainers, profiles))

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
        if candidate and (not original or original.casefold() == candidate.casefold() or compatible(original, candidate)):
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
