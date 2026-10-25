# Collection and operations

Run commands from the repository root with Python 3.11+. No installation needed.
`--db` is a global option and must appear before the subcommand. The default is
`data/hippos.sqlite3`, excluded from Git.

The current [backfill policy](backfill.md) uses explicit 30-second spacing,
200 attempts per UTC day and four bounded maintenance wake-ups per day. The CLI defaults
below remain available; historical run notes describe their settings at that time.

Optional [Veikkaus Toto enrichment](toto.md) uses `seed-toto` and `run-toto`.
It shares the same lock, request ledger and global stops, with a 60-second minimum
and 40-request Toto daily cap within the combined 200-request operating budget.
The regular `run` command continues to process only Hippos jobs.

## Small first run

```powershell
python -m hippos_analyst seed --from 2025-10-22 --to 2025-10-22
python -m hippos_analyst run --max-requests 3
python -m hippos_analyst status
python -m hippos_analyst calendar --from 2025-10-22 --to 2025-10-22
python -m hippos_analyst race --date 2025-10-22 --track H --number 1
```

`seed` is offline. The three-request sample imports a calendar, a meeting's race
list and its first queued race field. It intentionally leaves the other race fields
queued. Calling `run` again resumes. Repeating `seed` does not requeue completed work
unless `--refresh` is specified. A seed command accepts up to 366 days.

## Collection limits

- One worker per database; only validated public Hippos racing paths are allowed.
- Default 15 seconds between request starts, including across runs. Minimum 10.
- Default maximum 25 requests per run; default 500 per UTC day, persisted in SQLite.
  Both budgets can be lowered; neither can exceed 500. Use one database for the
  provider so the ledger includes all normal collection work.
- These are project-selected conservative limits, **not Hippos-approved limits**.
- No automatic redirect following, cookies, login, proxy rotation or bypass of blocks.
- Timeout 30 seconds, response cap 8 MiB, expected JSON content type.
- HTTP 401/403/429 or redirects persistently pause collection. `Retry-After` is
  retained and `resume` refuses to clear the stop before it expires.
- Network failures, 408 and 5xx stop the current run and defer retry, beginning at
  one minute with exponential backoff. The cooldown is service-wide, persisted in
  `control.paused_until`, and blocks every queued path across restarts. Server
  retry delays take precedence. A run attempted before expiry exits with code 2
  without reserving or sending a request. Timed cooldowns expire without `resume`;
  five consecutive transient failures instead require an explicit persistent-stop
  recovery after investigation.
- HTTP 404/410 mark a job failed and stop that run, rather than interpreting a missing
  endpoint as a successfully collected empty race. Other unexpected statuses pause.
- Schema errors pause the collector and retain existing normalized data. Failed
  jobs require a deliberate retry after fixing the cause.
  Scratch indicators are required JSON booleans. Supplied cancellation, result,
  monte, Finnish-track, publication, and gallop flags must also be booleans;
  string/numeric/null substitutes are rejected. Optional flags may be omitted.
  Participant numbers must be integer or digit-string identities, never booleans
  or fractional values. Result-code strings, including ties, remain unchanged.

The [API research](api-research.md) records the robots restriction and the owner's
decision to proceed privately. No provider approval is claimed. If Hippos asks us
to stop, use `pause`, leave it paused, and resolve the request before further access.

```powershell
python -m hippos_analyst pause --reason "Provider requested a stop"
```

Pause is checked before each request and during rate-limit waits. An in-flight
request may finish. Ctrl+C also stops a bounded run with its queue intact.

After investigating a temporary problem, these are explicit recovery commands:

```powershell
python -m hippos_analyst retry '/race/2025-10-22/H/start/1'
python -m hippos_analyst resume
```

`retry` only changes a failed job, does not clear a stop and sends no request.
Never automatically resume access refusals or provider objections.

## Gradual historical collection

1. Finish a small historical day and compare meeting/race/participant counts.
2. Seed a month; measure request volume, storage and missing-field rates.
3. Expand to the previous 12 months, then earlier years in bounded batches.
4. Discover horses through race entries. Selected profiles now add owners,
   breeders and bounded pedigree links; see [horse relationships](horse-relationships.md).
   Other profile/history endpoints still require a verified use and contract.

```powershell
python -m hippos_analyst seed --from 2025-10-01 --to 2025-10-31
python -m hippos_analyst run --max-requests 25 --daily-budget 100
```

The run returns when no jobs are due, a stop/error occurs, or a budget is reached.
It is not an always-on daemon. Jobs with lower priority numbers run first; dates
are newest first within a priority.

For an intentional refresh, requeue the daily calendars with `--refresh`.
Processing those calendars requeues completed dependent race-list and field jobs.

```powershell
python -m hippos_analyst seed --from 2026-10-22 --to 2026-11-05 --priority 10 --refresh
```

Proposed future cadence: daily upcoming-calendar updates, additional selected
pre-race field snapshots, results the following day, and a correction check about
a week later. No such refresh schedule is currently configured. It must share the
same budget as the [active historical backfill](backfill.md).

At 500 requests/day, 20,000 requests need at least 40 days, plus ongoing updates
and retries. This is arithmetic, not an estimate of the unmeasured Hippos archive.

## Verification

Profile seeding is offline and bounded: `seed-profiles --limit 5 --generations 2
--priority 90`. Explicit `--id` selection must reference a horse already in this
archive; `--refresh` is allowed only with that explicit selection. Profile jobs
use the ordinary collector and its shared limits, never a separate request budget.
The daily schedule's profile policy and current allowance are in [backfill](backfill.md).

```powershell
python -m unittest discover -s tests -v
```

Tests use synthetic API-shaped fixtures and temporary SQLite files; they make no
external requests. They cover discovery, persistence, repeated imports, corrections,
field removals, pauses, retry delays, daily budgets, interruption, foreign meetings,
identifier precision, privacy filtering and malformed responses.

Exit codes: 0 for normal completion/idle/local budget limits; 2 for failures,
provider stops or deferred retries; 130 for Ctrl+C. Inspect `status` before running
again after a nonzero exit.

### Initial verified run — 22 October 2026

- `python -m unittest discover -s tests -v`: 27 tests passed.
- A bounded live run of 13 requests imported the Finnish meeting on 2025-10-22:
  Helsinki/Vermo (`H`), 11 races, 108 entries and 108 distinct horse IDs.
- All 13 responses were HTTP 200 and all 13 jobs completed. No failed or pending
  jobs remained. The fields included race numbers 1–10 and 21.
- Minimum measured request-start spacing: 15.0001 seconds.
- SQLite `integrity_check`: `ok`; `foreign_key_check`: no issues.
- Local calendar output was verified, including Finnish Unicode through Windows
  pipes. The database is ignored by Git; local documentation links resolve.

This verifies that specific meeting, not historical completeness or any prediction
quality. The live process exited; no unattended worker or schedule remains active.

### UI sample expansion — 22 October 2026

Seeded 2026-10-21 through 2026-10-23 with priority 10, then ran
`python -u -m hippos_analyst run --max-requests 60` using the default 15-second delay.
The worker exited normally after 42 requests when the queue became empty.

- All 42 new responses were HTTP 200; no rate limit, access refusal or failed jobs.
- Minimum measured spacing within the run: 15.00014 seconds.
- Total archive: 4 meetings, 47 races, 468 entries, 456 distinct horse IDs,
  55 snapshots and 55 successful requests. All 55 jobs are done.
- New meetings: Helsinki/Vermo (21 October), Forssa/Pilvenmäki (22 October), and
  Lappeenranta/Lappee (23 October). The earlier 2025-10-22 sample remains.
- SQLite integrity and foreign-key checks passed after collection.
- Today's fields are snapshots taken during the meeting; later results are not
  automatically collected. Tomorrow's fields may also change before race start.

The collector is stopped. The local UI can remain running without sending any
upstream requests. Refreshes and broader backfills still require explicit runs.

### Larger sample and workspace pass — 22 October 2026

Queued 2026-10-08 through 2026-10-29 at priority 20; 19 new daily calendars were
added because previously collected dates were already present. Started a bounded
`python -u -m hippos_analyst run --max-requests 80` with the same 15-second spacing
and 500-request daily ceiling. Newest dates are processed first.

Checkpoint after 46 new requests (22 October, approximately 20:32 Helsinki time):

- All 46 were HTTP 200 and saved successfully, with no failed jobs or provider stop.
- Total archive: 9 meetings, 84 races, 867 entries and 813 distinct horses.
- Minimum measured request-start spacing in this batch: 15.00008 seconds.
- SQLite integrity and foreign-key checks passed during collection.
- New upcoming meetings include Turku, Helsinki, Tampere and Seinäjoki. Turku's
  29 October race list was empty at observation time; the UI shows that explicitly.

This is an **in-progress checkpoint**, not the final batch count. The bounded worker
was left running while handing over the UI, and will stop at 80 requests, an empty
due queue, the daily budget, or the existing error/access/rate-limit conditions.
No recurring scheduler was added. Check `python -m hippos_analyst status` before
starting a subsequent run; remaining dates and discovered fields stay queued.
Never resume a provider refusal automatically.

### Larger sample completed — 22 October 2026

The 80-request batch above subsequently exited normally at its run limit. All
80 requests succeeded; minimum request-start spacing was 15.000082 seconds.
Final totals: 11 meetings, 120 races, 113 collected fields, 1,195 entries,
1,126 horses, and 135 snapshots/successful requests. There are 19 pending jobs
and no failed jobs. SQLite integrity, foreign keys, snapshot hashes, and current
field/snapshot comparisons passed. No new batch or recurring schedule was started.

The [end-to-end audit](audit-2026-10-22.md) records the detailed checks and a
synthetically reproduced 503 Retry-After cooldown defect. That defect and the
other seven findings are now [fixed and verified](audit-fixes-2026-10-22.md).
No live provider error or cooldown occurred in this sample. The fix pass did not
start a new collection run; 19 jobs remain queued.


## Scheduled maintenance (25 October 2026)

`python -u -m hippos_analyst maintain --date 2026-10-25 --max-requests 40`

Pass the current **Europe/Helsinki** date; the example date is not a permanent
schedule argument. The command holds the existing worker lock through planning
and all three collection phases. It has no background subprocesses and does not
clear pauses, reset budgets or retry failed jobs. Its limits are fixed at 30-second
spacing and 200 combined attempts per UTC day. Any failed job now blocks both
ordinary providers and maintenance until investigated.

Each wake-up permits at most 20 refresh, 10 profile and 10 historical requests.
Unused shares are not borrowed, so maintenance cannot consume extra requests just
because one queue is empty. `--max-requests` may be 4–40; smaller runs divide their
allowance in the same 1/2, 1/4, remainder proportions. A provider stop, schema
error, failure, cooldown or daily-budget stop prevents later phases from running.

Refresh planning covers Helsinki today minus three days through today plus seven.
Calendars, known race lists and fields are eligible when their last successful
observation is at least 24 hours old. Children discovered by a refreshed parent
inherit this age check. Unfinished jobs keep their attempts and Retry-After;
failed jobs are never reset. Old snapshots remain available when current fields
change. This updates scratches, entrants, times and published results, subject
to queue capacity. It is not a live feed or a guaranteed 24-hour completion SLA.
Corrections published after the recent three-day window are not automatically
revisited by this policy.

At most five new known participant roots are seeded per Helsinki day, only after
pending profiles finish. A persisted `maintenance_state.profile_seed_day` prevents
duplicate batches across restarts. Two ancestor generations remain the maximum;
completed profiles are not automatically refreshed and ancestor stubs do not
become new roots.

History gets its own request share. Starting from October 2026, planning fills
missing calendar days, then walks backward one month at a time. Every discovered
calendar/race/field must have a successful observation before that month establishes
the frontier. A pending refresh does not erase earlier coverage. The isolated
October 2025 sample cannot skip intervening months. Pending historical work blocks
another month's seeds; twelve consecutive observed empty months stop expansion
for investigation. Profile completion never establishes racing-history coverage.

The existing chat automation uses this command at 08:00, 12:00, 16:00 and 20:00
Europe/Helsinki. It remains local: the computer and Codex app must be running and
network approval must be available. No separate Toto polling or new Toto targets
are scheduled by `maintain`; explicit bounded Toto jobs use `run-toto`.
