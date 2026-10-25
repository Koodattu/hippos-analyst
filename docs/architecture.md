# Architecture and data decisions

## First implementation

Python 3.11+ and its standard library: `urllib`, `sqlite3`, `argparse`, and
`unittest`. No production dependencies or package installation are required.

The data path is calendar -> Finnish meetings -> races -> participants/results.
Horse identities are discovered from participants and verified parent references.
Selected participant profiles can discover at most two ancestor generations.
No horse-register enumeration, unbounded pedigree crawl, account login or write
API is used.

The web UI reads a local application API backed by SQLite. UI
navigation does not trigger provider requests. The optional `toto.py` importer
adds Veikkaus observations through the shared collector lock, budget ledger and
stop state, with a separate queue selection and stricter limits. See [Toto](toto.md).
Weather remains planned; there is no generic provider/plugin framework.

`server.py` serves vanilla ES modules and CSS using a standard-library HTTP server
bound to `127.0.0.1`. Each API request opens SQLite in read-only mode and holds a
read transaction for a consistent view while a collector writes. Static files are
explicitly allowlisted; the database itself is not served. No npm packages or
frontend build pipeline are needed. Finnish strings live in `web/locales/fi.mjs`.
This is a local development app, not an internet deployment configuration.

## Storage

- `jobs`: persistent discovery queue with attempts, priority, retry time and errors.
- `requests`: every attempted request, including interrupted ones; UTC timestamps,
  HTTP outcome and the associated snapshot. This is also the persistent budget ledger.
- `snapshots`: deduplicated, validated, minimized source records with a content hash
  and parser version. Repeated observations reference the same snapshot via requests.
- `meetings`, `races`, `horses`, `entries`: queryable latest observed records.
  Results are currently columns of `entries`, rather than a second redundant table.
- `control`: persistent operator/provider pause, cooldown and failure counter.
- `maintenance_state`: the last Helsinki day on which profile roots were seeded.
  `maintenance.py` plans age-gated refreshes and contiguous history under the shared
  lock; queue shares prevent refreshes from starving profiles and older history.
  A future `paused_until` blocks every path even without a persistent pause reason;
  this preserves transient service backoff and Retry-After across restarts.

Snapshot and normalized updates, job completion, and discovery of dependent jobs
commit atomically. HTTP work happens outside transactions. A crash leaves the
job pending; its request reservation still counts against the budget. A per-database
OS lock prevents two collectors running simultaneously and releases on process exit.

SQLite uses foreign keys, short transactions and WAL. Keep the database on a local
disk, not a shared/network filesystem. Use SQLite's backup facility for a live backup;
do not copy only the main file while WAL writes are active. See [SQLite WAL](https://www.sqlite.org/wal.html).

## Data boundaries

Source snapshots are **not unrestricted raw responses**. The explicit allowlists
in `api.py` retain race facts, horse identifiers and public driver/trainer competition
names. Profile collection additionally retains owner/breeder display labels and
sire/dam IDs and names. Contact information, microchips, vaccination information,
free-text comments, cookies and response error pages are not archived. Unknown
fields are dropped; unexpected structures in retained fields pause collection.
Behavioral boolean fields are type-checked, including a required scratch flag;
optional flags may be omitted but cannot be supplied as null/string/number values.
Participant identifiers reject booleans and fractional numbers. These checks run
before the transaction that replaces a field. All 135 existing snapshots were
revalidated unchanged after adding the stricter checks.

The private database and runtime files live under ignored `data/`. Do not put
downloaded records or credentials in Git. The repository's Apache software licence
does not grant rights to upstream datasets.

Dates are source calendar dates; request times are UTC epoch seconds. API local
start-time strings are preserved. The UI formats dates and observation timestamps
using Europe/Helsinki, with tested midnight/DST boundaries. Daily collection budgets
use UTC to avoid platform timezone-data dependencies.

Horse IDs are TEXT. Preserve numeric-looking race fields and result codes in
source form; the first implementation does not invent conversions or calculate
features. A later normalization layer must test units, missing values, ties,
scratches, disqualifications and breed/start-type differences.

Current tables represent latest observations, not historical knowledge. Old
responses remain queryable through timestamped snapshots. Backfilled data fetched
today cannot prove exactly what was available before a past race. Predictions must
record their model version, input cutoff and creation time before race start.

## Current limitations

- Bounded, minimized horse profiles and pedigree links are implemented; there is
  no full-register, odds or weather importer, or prediction model yet.
- History coverage is bounded by explicitly seeded dates; no claim of total archive
  completeness. `status` shows pending/failed jobs, including unfinished race fields.
- An entry refresh replaces the current field, preserving previous snapshots.
  Meeting and race tables retain previously observed records if omitted from a later
  list. The web API reconciles visibility against the latest successful calendar and
  race-list observations, including when a deduplicated old snapshot is seen again.
  Removed items are hidden from the calendar and current horse history; old snapshots
  remain available for research. The original CLI queries still expose retained rows.
- Calendar and meeting reads filter by date/track in SQL before expanding race
  details. A partial `requests(path,id DESC)` index on successful observations
  supports latest-snapshot lookup. `store.connect` adds it idempotently to existing
  version-1 archives; no racing records or snapshots are rewritten. The normal CLI
  startup, including `serve`, applies it before read-only HTTP connections open.
- Overview counts use calendar/race-list membership without decoding runner
  snapshots. Overview work still grows with the number of meetings. Calendar reads
  now page 30 visible meetings before expanding fields, returning `total`, `offset`
  and `limit`; coverage-day metadata still spans the requested range. See the
  [growth verification](archive-growth.md) and earlier
  [read-path comparison](audit-fixes-2026-10-22.md#performance-verification).
  This is not a claim of unlimited archive capacity.
- Snapshot schema version 1 stores selected records, not all outer response fields.
  Additional fields may require new observations; dropped data cannot be recovered
  from the archive.
- A bounded command runs only while the computer is awake. A daily chat automation
  now continues [historical backfill](backfill.md); no Windows service is installed.

## Local explorer additions

`/api/race` adds up to five visible earlier starts per runner; the strict date
cutoff excludes the selected day. `/api/saved?ids=...&from=YYYY-MM-DD` accepts up
to 100 decimal string IDs and returns their records plus visible starts on/after
the date and missing IDs. `/api/coverage?offset=0` returns 30 queued calendar dates
with collection metadata. Neither endpoint writes SQLite or contacts Hippos.
All participate in the existing per-request SQLite read transaction. No migration
or production dependency was introduced. Browser-local saved preferences are a
separate store; future entries and historical results are split in the frontend.

People directories and profiles now read the driver/trainer IDs already in entry
JSON. Role-scoped identity, source-membership reconciliation, bounded history
pages and API contracts are documented in [people and relationships](people.md).
There is no new identity table or upstream importer; aggregation cost still grows
with visible entries even though responses contain at most 30 rows.

Owner/breeder source-label groups and parent relationships now use additive
`horse_profiles`, `horse_parties` and `horse_parents` tables. Ancestor identities
may have no local race history. See [horse relationships](horse-relationships.md)
for contracts, atomic refresh semantics, depth bounds and verification.
