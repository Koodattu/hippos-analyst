# Gradual archive backfill

Updated 22 October 2026. The owner requested continued slow collection, broad
historical coverage, UI growth checks, and a stop on crawling limits.

## Scope and progress frontier

The long-term target is all available public Finnish racing calendars, race
lists, participants and results accessible through the three implemented paths.
This does not yet cover every Heppa record: profiles, pedigree, offspring,
registration data, foreign meetings and other services require separate research
and importers. Existing field allowlists remain in effect. Historical depth and
nationwide completeness are unknown; an empty response is not proof of either.

- Current contiguous window being filled: **2026-10-01 through 2026-10-29**.
- Earlier isolated sample: **2025-10-22**. Do not jump to September 2025 on account
  of this sample; the intervening year has not been collected.
- Next historical month after the pending queue finishes: **September 2026**.
- Contiguous completed historical months: **none yet**.
- Consecutive completely empty historical months: **0**.

Finish discovered fields before extending the window. Once all pending work is
done and no failed jobs or stop is present, seed one preceding calendar month,
at priority 100, and move the frontier only when its calendar/race/field jobs
complete. Existing jobs deduplicate the isolated sample. Continue backward month
by month. After twelve consecutive empty historical months, stop expansion and
investigate archive depth rather than crawling indefinitely into empty years.
Report coverage as observed snapshots, never a verified copy of the provider.

## Active operating policy

Use the same live database, `data/hippos.sqlite3`, and a single worker. Requests
start at least **30 seconds apart**, with at most **200 attempts per UTC day**
shared by historical collection, refreshes, failures and interrupted requests.
These are our ceilings, not provider-approved limits. The underlying CLI defaults
remain unchanged; use the explicit arguments below for this backfill policy.

The chat automation **Grow Hippos archive slowly** (`grow-hippos-archive-slowly`)
is active, daily at **10:00 local time**. It runs one batch of at most 100 requests:

```powershell
python -u -m hippos_analyst run --max-requests 100 --delay 30 --daily-budget 200
```

It checks for an existing worker and never starts another concurrently. It must
wait for the batch to finish before recording final counts. A full batch takes
about 50 minutes. No additional run is started to consume unused daily budget.
Local scheduled work requires the computer on, the app running, and this folder
available, as described in the [official scheduled-task documentation](https://learn.chatgpt.com/docs/automations?surface=app).
Network approval remains subject to the normal execution controls. A scheduled
run requiring unavailable approval may stop without collecting; it is not a
standalone Windows service or a guarantee of uninterrupted daily operation.

Provider objections, 401/403/429, redirects and schema changes stop collection;
the automation must pause itself for investigation. Never automatically clear
the persistent collector stop or retry failed jobs. Transient transport/408/5xx
failures end the current run and wake-up, preserving the service cooldown and
Retry-After; no same-wake-up retry. The local daily ceiling is a normal stop and
does not justify raising or resetting the limit. See [collection operations](collection.md).

The schedule fills history; it does not currently refresh upcoming fields or
revisit finished races for corrections. Those need a separately measured cadence
sharing this budget. Future calendar dates beyond 29 October are not yet queued.

## Final checkpoint — 22 October, 21:46 Helsinki

Seven offline calendar seeds extended the queued range back to 1 October. The
network-disabled attempt 136 recorded a local transport failure; its cooldown
was respected before the approved network-capable run started at request 137.

The 64-request batch **ended automatically at request 193**, before its cap:
56 HTTP 200 responses saved, then one transient transport failure (status 0).
The last request was the Pori 16 October field 2. No HTTP 401/403/429 or other
provider limit was observed, and no persistent stop was cleared. No further run
was started in this wake-up. Its retry is pending for a later scheduled run,
subject to the recorded cooldown and unchanged request budgets.

- 193 attempts overall: 191 successful responses and two transport failures.
- 15 meetings, 171 races, 1,722 entries, 1,502 horses, 191 snapshots.
- 25 pending jobs, zero failed jobs, no persistent pause.
- Minimum start spacing in the network-capable run: **30.00010 seconds**.
- SQLite integrity: `ok`; zero foreign-key violations.
- Calendar span includes the original isolated 22 October 2025 sample and the
  current October 2026 backfill. The span is not continuous coverage.

The next daily wake-up must inspect this checkpoint, the ledger and current
control state before resuming pending jobs. A status-0 transport failure is not
proof of a provider crawling limit; it still ends the batch. Do not fill the
remaining daily allowance with another run today.

## UI growth verification

See [archive growth verification](archive-growth.md). Synthetic data is kept in a
different database and has never been merged into the live archive.
