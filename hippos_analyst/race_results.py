"""Interpret source results without confusing disqualification with finishing place."""

import re

# Official Hippos result abbreviations. Unknown codes remain visible, not inferred.
DISQUALIFIED = frozenset(('hel','hkä','hll','hlo','hpl','hrp','hva','hyl','hml','hrl'))
NONFINISH = frozenset(('k',))
VERSION = 2


def outcome(entry):
    if entry.get('absent'):
        return {'kind':'scratched', 'place':None, 'code':None}
    raw = str(entry.get('placing') or '').strip()
    code = str(entry.get('disqualifiedCode') or '').strip().lower()
    if code:
        kind = 'disqualified' if code in DISQUALIFIED else 'nonfinish' if code in NONFINISH else 'unknown'
        position = int(raw)-100 if code == 'hlo' and re.fullmatch(r'1\d{2}',raw) and int(raw)>100 else None
        return {'kind':kind, 'place':None, 'code':code, 'recorded_position':position}
    if re.fullmatch(r'[1-9]\d?=?',raw):
        return {'kind':'placed', 'place':int(raw.rstrip('=')), 'code':None}
    if raw == '0':
        return {'kind':'unplaced', 'place':None, 'code':None}
    return {'kind':'unknown', 'place':None, 'code':None}


def winner(entry):
    value = outcome(entry)
    return value['kind'] == 'placed' and value['place'] == 1


def has_result(entry):
    return not entry.get('absent') and (bool(str(entry.get('disqualifiedCode') or '').strip()) or
                                      str(entry.get('placing') or '').strip() not in ('','0'))


def galloped(entry):
    # Hippos's flag can mean an earlier gallop; hpl/hll need not set that flag.
    return entry.get('gallop') is True or str(entry.get('disqualifiedCode') or '').strip().lower() in ('hlo','hpl','hll','hml')


def register_sql(db):
    def entry(absent, placing, code):
        return {'absent':absent,'placing':placing,'disqualifiedCode':code}
    db.create_function('result_known',3,lambda a,p,c:has_result(entry(a,p,c)),deterministic=True)
    db.create_function('result_win',3,lambda a,p,c:winner(entry(a,p,c)),deterministic=True)
    db.create_function('result_place',3,lambda a,p,c:outcome(entry(a,p,c))['place'],deterministic=True)
