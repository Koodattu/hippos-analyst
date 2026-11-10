# Result parsing and repair — 10 November 2026

The runner importer now retains `disqualifiedCode`. Previously it discarded this
companion code, displayed `106` as a placing, omitted zero-placing disqualifications
from histories and rejected affected fields for modelling.

## Confirmed meanings

A fresh, ledger-accounted observation of Jokimaa, 9 November 2026, race 2 confirmed
Blackriver Get On's `placing: "106"`, `disqualifiedCode: "hlo"` and Like Your Victory's
`placing: "0"`, `disqualifiedCode: "hpl"`. The official frontend formats the first
pair as **hlo6**: a disqualification with a recorded would-have-been sixth place,
not an official sixth. `hpl` means disqualification for a long gallop.
See [Hippos's guide](https://www.hippos.fi/raviurheilu/ravikilpailusaannot/juoksun-hylkaamisen-syyt/).

Source codes remain unchanged in SQLite. Unknown codes stay visible and block
model scoring. Legacy numeric codes without a companion are displayed as `[106]`,
not guessed. Zero-placing disqualifications count as results in horse/person
histories, not upcoming starts. Wins and numeric placing sorts exclude them.

## Fields and provenance

Runner parser **version 4** also retains original-driver identifiers/names,
owner name, car-record fields, `winOdds2`, `finishing`, `placementExpectations`,
`hasEquipmentChanges` and `equipmentChangesText`. Unverified units and meanings
are preserved without using them as model features. No owner/person enumeration
was introduced.

Successful responses inventory received field names in `source_fields`, recording
whether they are retained and their first/last observation. This stores names,
not unreviewed values. At verification the only observed unretained names were
`commentText`, `commentUpdateTime` and `ownerCity`: free-text comments, their
timestamp and owner location remain outside the reviewed racing-field allowlist.
This explicit exclusion is not a claim to store every provider property.

Snapshots record parser versions. New normalized snapshots never overwrite or
relabel older evidence, even when their bodies are identical or empty.

## Refetch operation

```powershell
python -m hippos_analyst repair-results
python -m hippos_analyst repair-results --enqueue
```

The first command reports progress without fetching. The second requires the
shared worker lock and requeues previously observed fields with an older parser.
It is idempotent, prioritizes special numeric results, preserves attempts and
queue context, and refuses pauses, cooldowns or failed jobs. Do not enqueue while
the continuous worker holds the lock; the repair was already queued on 10 November.

All **3,212 previously observed fields** were included: lost codes can accompany
zero as well as 100-series placings. The continuous collector consumes them through
its existing refresh/profile/history shares, ledger and lock at **15-second spacing
and 2,000 attempts per UTC day**. No second collector, extra Toto polling, budget
reset or automatic failed-job retry was introduced. This takes multiple days;
see [backfill progress](backfill.md).

## Model and verification

Known disqualified/nonfinishing starters remain in the field as non-winners.
Their times are excluded from comparable ordinary performances; gallop codes
also inform prior history when the separate gallop flag is false. Unknown
outcomes remain excluded from evaluation. Target-race and same-day/future outcomes
remain excluded from features. Monté remains unsupported pending separate validation.

The current artifact is `data/models/20261110T145450Z-d6e5c544`, feature version 2.
Old artifacts remain unchanged and cannot generate new predictions through the
changed pipeline. Training/tuning/calibration/test used 990/239/155/220 races.
The chronological test (12 October–9 November) selected 59 winners (26.8%), with
log loss 2.0175 and Brier score 0.8374. The unfinished refetch and changed cohort
prevent claiming complete recovery or a controlled improvement over older reports.

**159 Python and 36 JavaScript tests passed**, covering codes, zero-placing history,
winners/sorts, repair idempotency, provenance, field inventory, stops/cooldowns and
real CatBoost train/save/load. Live HTTP/browser checks confirmed Jokimaa race 2's
`hlo6`, `hpl`, scratch and seven probabilities summing to one. SQLite integrity and
foreign-key checks passed. The server remains on port 8766; collection and the
new model's forecast watcher run without Windows sign-in hooks or services.
