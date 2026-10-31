# Gradual archive backfill

Updated 31 October 2026. The owner requested continued slow collection, broad
historical coverage, UI growth checks, and a stop on crawling limits.

## Scope and progress frontier

The long-term target is all available public Finnish racing calendars, race
lists, participants and results, plus selected horse profiles and bounded ancestry
through the four implemented endpoint families. This does not cover every Heppa
record: complete offspring registers, historical ownership, foreign meetings and
other services still require research. Explicit field allowlists remain in effect. Historical depth and
nationwide completeness are unknown; an empty response is not proof of either.

- Completed first-observation window: **2026-10-01 through 2026-10-31**.
- All 31 October calendars, 31 discovered race lists and 382 discovered fields
  have successful observations. This includes upcoming fields; final results and
  subsequent provider changes are not complete. November 1–2 have observed
  calendars/race lists and all 16 Joensuu / 12 Kaustinen fields, respectively.
  November 3–7 calendars are queued but not yet observed.
  Turku's previously empty 29 October race list now contains 11 races; all their
  fields were collected on 27 October. Empty observations can change later.
- Earlier isolated sample: **2025-10-22**. Do not jump to September 2025 on account
  of this sample; the intervening year has not been collected.
- Historical month now being filled: **September 2026**. Its 30 calendars are
  seeded; September 28–30 have all discovered fields observed. September 27 has
  an observed calendar with three meetings, all 13 PS fields, and the PX race
  list with one of its eight fields. Seven PX fields, the Y race list and
  September 1–26 calendars remain unobserved.
- Contiguous months with all discovered racing jobs observed: **one (October 2026)**.
- Consecutive completely empty historical months: **0**.

Finish unobserved fields before extending the historical window. Once pending
historical work is done and no failed jobs or stop is present, seed one preceding month,
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
uses four wake-ups: **08:00, 12:00, 16:00 and 20:00 Europe/Helsinki**. Each runs:

```powershell
python -u -m hippos_analyst maintain --date YYYY-MM-DD --max-requests 40
```

The date must be the current Helsinki date. One shared worker lock spans all
phases: at most 20 refresh, 10 profile and 10 historical requests, at 30-second
spacing and within the unchanged 200-attempt UTC daily budget. Unused phase shares
are not spent elsewhere. A full wake-up takes about 20 minutes; do not start
another run to consume unused budget.

The rolling refresh window is three days back through seven days ahead. A
successful calendar/list/field becomes eligible again after 24 hours; pending
cooldowns and failures are preserved. Profile discovery adds at most five known
participant roots per Helsinki day once pending profiles finish, with at most
two ancestor generations. Completed profiles are not automatically refreshed.

History has a separate queue and request share, so recurring refresh work cannot
starve it. Check its frontier before seeding refresh work. Start at October 2026,
fill missing dates, then step backward one month at a time. All discovered racing
jobs need a successful observation; pending refreshes do not erase earlier
coverage. Stop expansion after twelve consecutive empty months. See
[maintenance details and limitations](collection.md#scheduled-maintenance-25-october-2026).

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

The next daily wake-up must inspect the latest checkpoint, the ledger and current
control state before resuming pending jobs. A status-0 transport failure is not
proof of a provider crawling limit; it still ends the batch. Do not fill the
remaining daily allowance with another run today.

## Checkpoint — 22 October, horse relationships

A later explicit request to investigate and collect owners, breeders and pedigrees
authorized a new bounded feature-verification session after the recorded cooldown.
No persistent stop was cleared. Two public profile probes (requests 194–195)
returned HTTP 200; their bodies were not retained. The normal, tested collector
then saved five profiles at requests 196–200. The exploratory ledger entries were
left unchanged after automatic approval review rejected manual import/replay.

**Today's allowance is now 200/200. No more provider requests today.** The five
request batch exited at its run cap; the shared UTC daily cap is also fully used.
There were no new transport failures, 401/403/429 responses or provider objections.
The daily automation remains active for its next 10:00 local wake-up.

- 200 attempts: 196 saved successful observations, two successful research probes,
  and the two earlier transport failures.
- 15 meetings, 171 races, 1,722 entries, 1,512 horse identities, 196 snapshots.
- Five minimized horse profiles, three owner and three breeder label relationships,
  ten parent links. The horse total includes ten newly identified ancestors.
- 28 pending jobs: 15 calendars, ten fields and three profiles; zero failed jobs,
  no persistent pause, zero consecutive failures. The old cooldown has expired.
- Corazon Combo and Ullabella are the explicit roots. Corazon Combo's existing
  root job was expanded offline to two ancestor generations after the live sample;
  its two parents and Ullabella's dam are queued. This sent no additional request.
- Minimum spacing across requests 194–200: **30.00010 seconds**.
- SQLite integrity `ok`, zero foreign-key violations.

Racing-date coverage and the September 2026 frontier are unchanged. Profile and
pedigree coverage are partial; do not interpret the new links as a complete register.

## Checkpoint — 23 October, 10:52 Helsinki

The scheduled batch exited normally with code 0 at its **100-request run cap**.
Requests 201–300 ran from 10:03:00 to 10:52:30 Helsinki (07:03–07:52 UTC), all
HTTP 200 and successfully saved. Today's shared ledger usage is **100/200**;
the unused allowance will not trigger another batch in this wake-up.

Before collection, the OS worker lock was free, the previous cooldown had
expired, and there were no failed jobs or persistent stops. The queue contained
28 pending jobs, including three profiles, so neither new profile roots nor a
historical month were seeded. The collector used the existing lock, field
allowlists, 30-second delay and 200-attempt UTC daily budget. Its lock was free
again after actual process exit. No stop or budget was cleared or reset.

- **300 total attempts:** 296 saved successful observations, two earlier successful
  research probes and two earlier transport failures. No new failures, redirects,
  access refusals or rate-limit responses occurred.
- **21 meetings, 247 races, 246 collected fields, 2,594 entries, 1,964 horse
  identities and 296 snapshots.** Horse identities include 1,948 race participants
  and 16 ancestors without archived starts.
- **Eight profiles:** two race participants and six ancestors. There are five
  owner-label and three breeder-label relationships, 16 parent links, and ten
  identified ancestor stubs without fetched profiles. Profile coverage remains
  partial; absent labels are not evidence that an owner or breeder does not exist.
- **12 pending jobs:** nine calendars, one field and two profiles. 296 jobs are
  done; none failed. There is no persistent pause or active cooldown, and the
  consecutive-failure count is zero.
- Minimum request-start spacing in this batch: **30.00008 seconds**.
- SQLite `integrity_check`: `ok`; zero foreign-key violations; all 296 minimized
  snapshot hashes match their stored bodies.

The completed observed race/field interval now reaches back through 11 October.
The 10 October Turku meeting still has one pending field; 1–9 October calendars
remain uncollected. The isolated 22 October 2025 sample remains separate. No full
historical month completed, so **September 2026 remains the next month to seed**,
only when a later wake-up finds the existing queue empty before profile seeding.
The consecutive-empty-month count remains zero. Profile completion does not
advance racing coverage.

Local read-model checks passed on the enlarged live archive in a read-only
transaction: overview, calendar, coverage, horse search/page two, driver and
trainer first/last pages and details, all owner/breeder groups, all eight profiles,
parent/offspring backlinks and a newly collected race with strictly earlier form.
Page bounds and linked identities were asserted. Single measurements including
JSON serialization were 20.48 ms for the calendar, 43.07/49.78 ms for driver/trainer
directories, and at most 0.72 ms for each collected profile. These are local smoke
measurements, excluding HTTP/browser overhead, not a capacity benchmark. No
material read-model regression was observed; no application code, dependencies
or UI layout changed, and this wake-up did not repeat browser visual testing.

## Recovered checkpoint — 24 October

The scheduled turn was interrupted before final verification. The ledger checked
on 25 October contains **30 attempts (301–330)** for 24 October, all HTTP 200,
successfully saved and finished, from 09:13:29 to 09:27:59 UTC. Minimum spacing
was **30.00015 seconds**. The previous process's exit code was not captured;
this is not a claim that its 100-request cap was reached. On the next wake-up
the OS worker lock was free, with no failed jobs, unfinished requests, persistent
pause or active cooldown. The preserved queue contained six calendars, one race
list and two profiles. No replacement batch was run on 24 October.

## Latest checkpoint — 25 October, 10:50 Helsinki

The single scheduled batch **exited with code 0 at its 100-request cap**.
Requests 331–430 ran from 08:00:35 to 08:50:05 UTC (10:00–10:50 Helsinki), all
HTTP 200 and successfully saved. Today's ledger usage is **100/200**; no second
batch will consume the remaining allowance in this wake-up. The worker lock was
free before the run and after actual exit. Existing stops and budgets were not
cleared or reset.

The initial queue was nonempty and included two profiles, so no profile roots
or calendar month were seeded. Existing ancestry remains bounded; no completed
profile was refreshed. This batch collected racing data only.

- **430 total attempts:** 426 saved successful observations, two earlier research
  probes and two earlier transport failures. No new failures, provider refusals,
  redirects or rate-limit responses occurred.
- **30 meetings, 359 races, 358 collected fields, 3,799 entries, 2,394 horse
  identities and 426 snapshots.** There are 2,378 race participants and 16
  ancestors without archived starts.
- Profile coverage is unchanged: **eight profiles**, comprising two race
  participants and six ancestors, with five owner-label relationships, three
  breeder-label relationships and 16 parent links. Ten ancestor identities still
  have no fetched profile; these do not become new roots automatically.
- **Three pending jobs:** one 1 October Lahti field and two profiles. 426 jobs
  are done; none failed. No persistent pause or active cooldown; zero consecutive
  failures.
- Minimum request-start spacing today: **30.00005 seconds**.
- SQLite integrity `ok`, zero foreign-key violations and all **426 snapshot
  hashes verified**.

All calendars and race lists for the queued **1–29 October** window are now
observed. Fields are complete against those observations for **2–29 October**;
1 October has 11 of 12 fields saved. October 30–31 remain unqueued, so this is
not a completed calendar month. The isolated 2025 sample remains separate.
September 2026 is still the next historical month, eligible only when a future
wake-up finds the entire existing queue empty before adding profile seeds.
Completed historical months remain zero, as does the consecutive-empty-month
count. Profile completion cannot advance this frontier.

Read-only local UI checks passed for overview, calendar, coverage, horse page two,
driver/trainer first and last pages and details, owner/breeder groups and backlinks,
all eight profiles and parent/offspring links, and a new race's strictly earlier
form. Pagination bounds and identity consistency were asserted. Single read-plus-
JSON measurements: calendar **30.67 ms**, driver directory **64.84 ms**, trainer
directory **76.22 ms**, all checked profiles below **1 ms**. These exclude HTTP
and browser overhead and show no material read-model regression at the current
archive size. No application code or dependencies changed; browser visual tests
were not repeated.

## UI growth verification

See [archive growth verification](archive-growth.md). Synthetic data is kept in a
different database and has never been merged into the live archive.


## 25 October 2026 — optional Toto pilot and persistent stop

See [Toto pilot](toto.md) for endpoint evidence, identity rules and implementation.
The batch exited after 13 requests (12 saved, one historical odds schema error).
Three fields / 34 participants matched existing Hippos identities; two current
odds observations were stored. No extra Hippos collection ran during this pilot.
The archive remains 30 meetings, 359 races, 3,799 entries, 2,394 horse identities,
eight profiles, eight owner/breeder relationships and 16 parent links. Calendar
coverage and the contiguous frontier above are unchanged: October 30–31 are not
queued, and September 2026 remains the next historical month after queue clearance.

Totals are now 455 requests and 438 snapshots; today's 125 attempts comprise
100 Hippos, 12 Toto research and 13 Toto import calls. The importer minimum spacing
was 60.00013 seconds. All 438 snapshot hashes verify, SQLite integrity is `ok`,
and foreign-key violations are zero. Three original Hippos jobs remain pending;
438 jobs are done and one Toto odds job failed. No Toto jobs are pending.

**Collection is paused.** `toto:/pool/226929191/odds@1` returned HTTP 200 but an
unrecognized `probable` value failed validation. The shared stop was preserved,
and `grow-hippos-archive-slowly` was paused in the app. No retry, budget reset,
new month, new profile seed or scheduled Toto follow-up was performed. No provider
refusal, redirect or rate limit occurred. Resolve the historical response contract
before explicitly authorizing any retry or resumption; do not infer approval
from a new daily wake-up. The local UI continues to work from saved data.


## 25 October 2026 — parser repaired and scheduled collection resumed

The owner explicitly authorized the known schema-stop recovery, slow collection
and scheduled refreshes. One bounded diagnostic retry found a missing `probable`
field for a scratched Toto runner. A focused parser fix preserves the missing
quote as null; supplied malformed values still fail closed. The subsequent
one-request retry succeeded. No other failed job was reset and no budget was
cleared. There are now three Toto observations, including the historical final
odds (eight prices and one missing quote). See [recovery evidence](toto.md).

The existing automation is ACTIVE at **08:00, 12:00, 16:00 and 20:00 Helsinki**,
using `maintain` with at most 40 requests per wake-up. No second automation or
background service was installed. The next scheduled wake-up after this check
is 16:00 on 25 October. All future stops still require investigation; this
specific recovery is not permission to clear future stops automatically.

A live `maintain --date 2026-10-25 --max-requests 12` batch exited normally after
**10 successful requests**: six refreshes (Kuopio race list and five fields),
three profiles and the final unobserved 1 October Lahti field. The unused two
historical request slots were not spent. No provider objection, access refusal,
redirect, rate limit, schema error or transient failure occurred in this batch.
Minimum request-start spacing was **30.00023 seconds**.

- 30 meetings, 359 races, **3,808 entries and 2,401 horse identities**.
- **11 detailed profiles**, seven owner and six breeder relationships, 22 parent
  links. Ancestor stubs remain bounded and do not seed roots automatically.
- **467 total attempts and 449 snapshots**. Today's total is **137/200**:
  110 Hippos attempts and 27 Toto/research attempts, including the diagnostic.
- 346 completed jobs, **100 pending refresh jobs and one pending profile**;
  no failed jobs, persistent pause, cooldown or consecutive failure.
- The historical queue is empty, but October 30–31 calendars still need their
  first observation before September is eligible. November 1 is also queued
  for the upcoming window. Current completed historical months: zero.
- All **449 snapshot hashes verified**, SQLite integrity `ok`, zero foreign-key
  violations. The worker released its lock; no collector was left running.

Verification: **89 Python tests and 23 JavaScript tests passed**, plus whitespace
checks. Regression coverage includes omitted scratched-runner odds, malformed
supplied prices, refresh age/idempotence, preserved cooldowns, once-daily bounded
profile seeding, queue fairness, stop propagation, daily budget, contiguous month
expansion, incomplete fields, refreshes preserving prior coverage, and the
12-empty-month boundary. Local read models succeeded for overview, calendar,
current/historical racecards, driver/trainer directories and all 11 horse profiles.
Observed read-plus-JSON times were 1.2–6.2ms for overview/calendar/racecards and
77.6–80.6ms for people directories. These are local single samples, not load tests.

## 25 October 2026 — 16:00 Helsinki scheduled maintenance

The single `maintain --date 2026-10-25 --max-requests 40` command finished normally
at 16:16 Helsinki (14:16 UTC). Preflight found the worker lock free, no failed jobs,
pause or cooldown, and 141 attempts already recorded for this UTC day. Planning
added no work: refreshes and profiles were already pending, and October remained
incomplete. No manual seeds, second batch or Toto requests were made.

- **23 successful requests:** 20 refreshes and three bounded ancestor profiles;
  no historical jobs were due. Unused phase allowances were not borrowed.
- Refreshed Kuopio's 25 October calendar and remaining fields, then Seinäjoki's
  26 October race list and ten fields. **80 refresh jobs remain**: ten calendars,
  six race lists and 64 fields. There are no pending profile or history jobs.
- **30 meetings, 359 races, 3,808 entries and 2,407 horse identities**;
  **14 profiles**, ten owner and nine breeder relationships, and 28 parent links.
  The additional identities include ancestor stubs, not newly collected starts.
- **494 total attempts, 472 snapshots, 164/200 attempts today**, and 369 completed
  jobs. No failed jobs, provider stops, cooldowns or consecutive failures.
- Minimum request-start spacing was **30.00008 seconds**. The command exited and
  released the worker lock; no collector remains running from this wake-up.
- Coverage remains **1–29 October 2026**, plus the isolated 22 October 2025 sample.
  October 30–31 and November 1 calendars still await their first observation;
  all other discovered racing jobs have at least one successful observation.
  No month completed, and September has not been seeded. The contiguous frontier
  and zero consecutive empty historical months are unchanged.
- SQLite integrity `ok`, zero foreign-key violations, and **all 472 snapshot
  hashes verified**.

Read-only UI checks passed for overview, October calendar, current and historical
racecards, both paginated directories and all 14 collected horse profiles. The
directories returned 2,407 horses and 1,868 people/party-role records. Single
in-process read-plus-JSON samples took 1.6–33.4ms for overview/calendar/racecards,
18.0ms for horses and 67.6ms for people; these are smoke checks, not a browser or
load test. No material read-model regression was observed. Existing unrelated
UI edits were left intact.

## 25 October 2026 — evening scheduled maintenance

This wake-up arrived at **22:23 Helsinki (20:23 UTC)**. The Helsinki date was
derived from that trigger time. Preflight found no active worker, failed jobs,
pause or cooldown, with 164 attempts already recorded for the UTC day.
Exactly one `maintain --date 2026-10-25 --max-requests 40` batch ran, finishing
at **22:38 Helsinki**. No extra batch, manual seeds or Toto polling followed.

- **30 successful requests:** 20 refreshes and ten profiles. The command seeded
  five known participant roots under its once-per-day rule, with the existing
  two-generation ancestor bound. History remained `month_pending`, so its unused
  ten-request allowance was not spent.
- Refreshed Seinäjoki's remaining 26 October field and calendar, Pori's 24 October
  race list, all 13 fields and calendar, and Tampere's 27 October race list and
  two fields. **60 refresh jobs remain**: eight calendars, four race lists and
  48 fields. Another **11 profile jobs** are pending; no historical jobs are due.
- **30 meetings, 359 races, 3,808 entries and 2,427 horse identities**, including
  ancestor stubs. There are **24 collected profiles**, 17 owner relationships,
  15 breeder relationships and 48 parent links.
- **524 total attempts, 500 snapshots, 194/200 attempts today**, 399 completed
  jobs and 71 pending jobs. All 30 attempts in this batch succeeded; there were
  no failures, provider stops or cooldowns. Minimum request-start spacing was
  **30.00010 seconds**, and the worker lock was released after exit.
- Observed racing coverage remains **1–29 October 2026**, plus the isolated
  **22 October 2025** sample. October 30–31 and November 1 calendars are still
  unobserved; every other discovered racing job has a successful observation.
  No coverage month completed, September was not seeded, and the consecutive
  empty historical month count remains zero. More profiles do not extend this
  racing-history frontier.
- SQLite integrity `ok`, zero foreign-key violations, and **all 500 snapshot
  hashes verified**.

Local read models passed for overview, calendar, current/historical racecards,
horse and people directories, and all 24 collected horse profiles. Directories
returned 2,427 horses and 1,881 people/party-role records. Single read-plus-JSON
samples took 2.0–36.1ms for overview/calendar/racecards, 19.1ms for horses and
73.0ms for people. These are in-process smoke checks, not browser or load tests;
no material growth regression was observed. No application code was changed.

## 26 October 2026 — morning scheduled maintenance

The wake-up arrived at **09:29 Helsinki (07:29 UTC)**; the current Helsinki date
was derived from that timestamp. Preflight found the worker lock free, no failed
jobs, pause or cooldown, and zero attempts for the new UTC day. Exactly one
`maintain --date 2026-10-26 --max-requests 40` command finished at **09:44 Helsinki**.
No second batch, manual seeds or Toto polling followed.

- **30 successful requests:** 20 refreshes and ten pending profiles. Planning
  added the November 2 calendar for the rolling upcoming window. No new profile
  roots were seeded because existing profile work remained. History reported
  `month_pending`; its unused ten-request allowance was not borrowed.
- Refreshed Tampere's remaining 12 fields and 27 October calendar, then Vermo's
  28 October race list and six fields. **41 refresh jobs remain**: eight calendars,
  three race lists and 30 fields, alongside **seven pending profiles**.
- **30 meetings, 359 races, 3,808 entries and 2,446 horse identities**, including
  ancestor stubs. There are **34 collected profiles**, 22 owner relationships,
  20 breeder relationships and 68 parent links.
- **554 total attempts, 528 snapshots, 30/200 attempts today**, 429 completed
  jobs and 48 pending jobs. No failures, persistent pause or cooldown. Minimum
  request-start spacing was **30.00012 seconds**. The command exited and released
  the worker lock.
- Observed racing coverage remains **1–29 October 2026**, plus **22 October 2025**.
  October 30–31 and November 1–2 calendars await their first observation; all other
  discovered racing jobs have a successful observation. No month completed,
  September was not seeded, and consecutive empty historical months remain zero.
  The additional profiles do not extend racing-history coverage.
- SQLite integrity `ok`, zero foreign-key violations, and **all 528 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current and historical racecards,
horse and people directories, and all 34 collected profiles. Directories returned
2,446 horses and 1,890 people/party-role records. Single in-process read-plus-JSON
samples took 1.4–33.1ms for overview/calendar/racecards, 16.0ms for horses and
66.9ms for people. No material read-model regression was observed; these were
smoke checks, not browser or load tests. No application code was changed.


## 26 October 2026 — requested local startup

Started the local backend with `python -u -m hippos_analyst serve --port 8766`
and verified HTTP 200 for the UI, overview, horse directory (2,446 records) and
people directory (1,890 role records). The UI is available at
http://127.0.0.1:8766/; the existing listener on 8765 was left untouched.

At the owner's request, started one additional
`maintain --date 2026-10-26 --max-requests 40` batch after confirming the shared
worker lock was free, with no failures or stops and 30/200 daily attempts used.
The first two requests succeeded (Vermo 28 October fields 5 and 6). The worker
was still running when this startup check ended; these are startup results,
not a completed-batch report. It retains the 20/10/10 phase shares, 30-second
spacing and 200-attempt UTC daily ceiling. No new service or schedule was added.

Follow-up: that requested batch exited normally at **10:06 Helsinki (08:06 UTC)**
after 30 successful requests: 20 refreshes and ten profiles. Minimum request-start
spacing was **30.00013 seconds**. It left 44 profiles, 555 snapshots, 584 total
attempts and 24 pending jobs, with no stop or failure. Its worker lock was free
before the next scheduled batch below began.

## 26 October 2026 — midday scheduled maintenance

The trigger arrived at **12:04 Helsinki (10:04 UTC)**. Preflight confirmed the
current Helsinki date, no active worker, failed jobs, pause or cooldown, and
60/200 daily attempts. Exactly one
`maintain --date 2026-10-26 --max-requests 40` command finished at **12:16 Helsinki**.
Planning added no refresh jobs or profile roots; history remained `month_pending`.
No second batch, manual seeds or Toto polling followed.

- **25 successful requests:** 20 refresh-queue requests and five profiles. Unused
  profile and history allowances were not borrowed. The older queued Forssa
  22 October calendar, race list and 15 fields were refreshed, followed by the
  first observations of Oulu's 30 October calendar, race list and first field.
- **31 meetings, 370 races, 3,815 entries and 2,476 horse identities**, including
  ancestor stubs. There are **49 collected profiles**, 30 owner relationships,
  29 breeder relationships and 98 parent links.
- **609 total attempts, 580 snapshots, 85/200 attempts today**, 484 completed
  jobs and **13 pending refresh jobs**: three calendars and ten fields.
  No profiles or historical jobs remain pending. No failures, persistent pause
  or cooldown; minimum request-start spacing was **30.00008 seconds**. The worker
  exited and released its lock.
- Calendars and race lists now have observations through **30 October**; complete
  discovered-field observations still end on **29 October**. Oulu has one of 11
  fields collected. October 31 and November 1–2 calendars remain unobserved.
  The isolated 22 October 2025 sample is unchanged. No full month completed,
  September was not seeded, and consecutive empty historical months remain zero.
- SQLite integrity `ok`, zero foreign-key violations, and **all 580 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new/historical racecards,
both directories and all 49 collected profiles. Directories returned 2,476 horses
and 1,907 people/party-role records. Single in-process read-plus-JSON samples took
0.7–35.7ms for overview/calendar/racecards, 20.9ms for horses and 78.1ms for people.
These were smoke checks, not browser or load tests; no material growth regression
was observed. No application code was changed.

## 26 October 2026 — afternoon scheduled maintenance

The wake-up arrived at **15:58 Helsinki (13:58 UTC)**. Preflight confirmed the
current Helsinki date, a free worker lock, no failed jobs, pause or cooldown,
and 85/200 daily attempts. Exactly one
`maintain --date 2026-10-26 --max-requests 40` batch finished at **16:13 Helsinki**.
Planning scheduled six eligible refreshes and five known participant roots for
today, with the existing two-generation ancestry bound. History was `month_pending`.
No second batch, manual seeds or Toto polling followed.

- **30 successful requests:** 20 refresh-queue requests and ten profiles. Refreshed
  Kuopio's 25 October race list and five fields, completed the remaining ten Oulu
  fields for 30 October, and observed Lahti's 31 October calendar, race list and
  two fields. The unused history allowance was not spent.
- **32 meetings, 382 races, 3,948 entries and 2,525 horse identities**, including
  ancestor stubs. There are **59 collected profiles**, 40 owner relationships,
  39 breeder relationships and 118 parent links.
- **639 total attempts, 610 snapshots, 115/200 attempts today**, 508 completed
  jobs and **20 pending jobs**: two calendars, ten fields and eight profiles.
  No failed jobs, persistent pause or cooldown. Minimum request-start spacing
  was **30.00013 seconds**; the command exited and released the worker lock.
- Calendars and race lists now cover **1–31 October**, with all discovered fields
  observed through **30 October**. Lahti has two of 12 fields collected; November
  1–2 calendars remain unobserved. October is not yet complete, September was not
  seeded, and consecutive empty historical months remain zero. The isolated
  22 October 2025 sample does not change that frontier.
- SQLite integrity `ok`, zero foreign-key violations, and **all 610 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new/historical racecards,
both directories and all 59 collected profiles. Directories returned 2,525 horses
and 1,946 people/party-role records. Single in-process read-plus-JSON samples took
1.4–33.1ms for overview/calendar/racecards, 19.1ms for horses and 68.6ms for people.
These were smoke checks, not browser or load tests; no material growth regression
was observed. No application code was changed.

## 26 October 2026 — late evening scheduled maintenance

The trigger arrived at **23:12 Helsinki (21:12 UTC)**; its Helsinki date was
26 October. Preflight found the worker lock free, no failures, pause or cooldown,
and 115/200 daily attempts. Exactly one
`maintain --date 2026-10-26 --max-requests 40` command finished at **23:27 Helsinki**.
Planning queued 40 age-eligible refreshes, no profile roots, and no historical
work because October remained `month_pending`. No second batch, manual seeds or
Toto polling followed.

- **30 successful requests:** 20 refreshes and ten bounded profiles. Refreshed
  Seinäjoki's 26 October calendar, race list and all 12 fields; Tampere's 27 October
  race list and two fields; and three Kuopio fields from 25 October. The unused
  historical allowance was not borrowed.
- **32 meetings, 382 races, 3,948 entries and 2,544 horse identities**, including
  ancestor stubs. There are **69 collected profiles**, 50 owner relationships,
  49 breeder relationships and 138 parent links.
- **669 total attempts, 635 snapshots, 145/200 attempts today**, 498 jobs currently
  marked done and **37 pending jobs**: four calendars, one race list, 27 fields
  and five profiles. The done-job count decreased because completed jobs were
  requeued for refresh; their previous successful observations remain intact.
- No failed jobs, provider stops, pause or cooldown. Minimum request-start
  spacing was **30.00009 seconds**. The worker exited and released its lock.
- Coverage is unchanged: calendars and race lists observed through **31 October**,
  all discovered fields through **30 October**, and two of 12 Lahti fields on
  31 October. November 1–2 calendars are still unobserved. No coverage month
  completed, September was not seeded, and consecutive empty historical months
  remain zero. The isolated 22 October 2025 sample remains separate.
- SQLite integrity `ok`, zero foreign-key violations, and **all 635 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/historical racecards,
both directories and all 69 collected profiles. Directories returned 2,544 horses
and 1,962 people/party-role records. Single in-process read-plus-JSON samples took
1.3–33.1ms for overview/calendar/racecards, 17.7ms for horses and 64.3ms for people.
These were smoke checks, not browser or load tests; no material growth regression
was observed. No application code was changed.

## 27 October 2026 — morning scheduled maintenance

The trigger arrived at **08:54 Helsinki (06:54 UTC)**; the Helsinki date was
derived from that timestamp. Preflight found the worker lock free, no failed
jobs, pause or cooldown, and zero attempts for the new UTC day. Exactly one
`maintain --date 2026-10-27 --max-requests 40` batch finished at **09:08 Helsinki**.
Planning added the November 3 calendar, no profile roots because profiles were
pending, and no historical jobs because October remained `month_pending`.
No second batch, manual seeds or Toto polling followed.

- **29 successful requests:** 20 refreshes and nine bounded profiles. Refreshed
  Kuopio's 25 October calendar and four remaining fields, then Pori's 24 October
  calendar, race list and all 13 fields. Unused phase allowances were not borrowed.
- **32 meetings, 382 races, 3,948 entries and 2,556 horse identities**, including
  ancestor stubs. There are **78 collected profiles**, 59 owner relationships,
  58 breeder relationships and 156 parent links.
- **698 total attempts, 646 snapshots, 29/200 attempts today**, 527 completed
  jobs and **13 pending refresh jobs**: three calendars and ten fields. No profile
  jobs remain pending. Unchanged response bodies reuse existing snapshots.
- No failed jobs, provider stops, persistent pause or cooldown. Minimum
  request-start spacing was **30.00008 seconds**; the worker exited and released
  its lock.
- Coverage remains calendars and race lists through **31 October**, all discovered
  fields through **30 October**, and two of 12 Lahti fields on 31 October.
  November 1–3 calendars are still unobserved. No month completed, September was
  not seeded, and consecutive empty historical months remain zero. The isolated
  22 October 2025 sample remains separate; profiles do not extend racing history.
- SQLite integrity `ok`, zero foreign-key violations, and **all 646 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/historical racecards,
both directories and all 78 collected profiles. Directories returned 2,556 horses
and 1,979 people/party-role records. Single in-process read-plus-JSON samples took
1.8–36.4ms for overview/calendar/racecards, 17.5ms for horses and 66.6ms for people.
These were smoke checks, not browser or load tests; no material growth regression
was observed. No application code was changed.

## 27 October 2026 — midday scheduled maintenance

The trigger arrived at **12:01 Helsinki (10:01 UTC)**; the current Helsinki date
was derived from that timestamp. Preflight found the worker lock free, no failed
jobs, pause or cooldown, and 29/200 daily attempts. Exactly one
`maintain --date 2026-10-27 --max-requests 40` batch finished at **12:15 Helsinki**.
Planning queued 28 age-eligible refreshes and today's five known participant roots,
bounded to two ancestor generations. History remained `month_pending`.
No second batch, manual seeds or Toto polling followed.

- **30 successful requests:** 20 refreshes and ten profiles. Refreshed Tampere's
  27 October calendar and remaining 12 fields, then Vermo's 28 October race list
  and six fields. The unused history allowance was not borrowed.
- **32 meetings, 382 races, 3,948 entries and 2,573 horse identities**, including
  ancestor stubs. There are **88 collected profiles**, 68 owner relationships,
  67 breeder relationships and 176 parent links.
- **728 total attempts, 660 snapshots, 59/200 attempts today**, 529 completed
  jobs and **29 pending jobs**: five calendars, one race list, 15 fields and
  eight profiles. Unchanged response bodies reuse existing snapshots.
- No failed jobs, provider stops, persistent pause or cooldown. Minimum
  request-start spacing was **30.00007 seconds**; the worker exited and released
  its lock.
- Racing coverage remains calendars and race lists through **31 October**, all
  discovered fields through **30 October**, and two of 12 Lahti fields on
  31 October. November 1–3 calendars remain unobserved. No month completed,
  September was not seeded, and consecutive empty historical months remain zero.
  The isolated 22 October 2025 sample remains separate; profiles do not extend
  racing-history coverage.
- SQLite integrity `ok`, zero foreign-key violations, and **all 660 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/historical racecards,
both directories and all 88 collected profiles. Directories returned 2,573 horses
and 1,994 people/party-role records. Single in-process read-plus-JSON samples took
1.9–38.9ms for overview/calendar/racecards, 19.7ms for horses and 67.7ms for people.
These were smoke checks, not browser or load tests; no material growth regression
was observed. No application code was changed.

## 27 October 2026 — afternoon scheduled maintenance

The trigger arrived at **16:04 Helsinki (14:04 UTC)**; the current Helsinki date
was derived from that timestamp. Preflight found the worker lock free, no failed
jobs, pause or cooldown, and 59/200 daily attempts. Exactly one
`maintain --date 2026-10-27 --max-requests 40` batch finished at **16:19 Helsinki**.
Planning queued 17 age-eligible refreshes, no profile roots, and no historical jobs
because October remained `month_pending`. No second batch, manual seeds or Toto
polling followed.

- **30 successful requests:** 20 refresh-queue requests and ten profiles. Refreshed
  Vermo's 28 October calendar and five fields, Turku's 29 October race list and
  calendar, and Kuopio's 25 October race list. Turku's formerly empty race list
  now returned **11 races**; their 11 fields were collected in the same refresh
  allowance, adding **110 entries**. The history allowance was not borrowed.
- **32 meetings, 393 races, 4,058 entries and 2,615 horse identities**, including
  ancestor stubs. There are **98 collected profiles**, 73 owner relationships,
  71 breeder relationships and 196 parent links.
- **758 total attempts, 686 snapshots, 89/200 attempts today**, 542 completed
  jobs and **31 pending jobs**: four calendars, one race list, 24 fields and two
  profiles. Unchanged response bodies reuse existing snapshots.
- No failed jobs, provider stops, persistent pause or cooldown. Minimum
  request-start spacing was **30.00007 seconds**; the worker exited and released
  its lock.
- Calendars and race lists have observations through **31 October**, with all
  discovered fields through **30 October** collected, including the newly
  published Turku fields. Lahti still has two of 12 fields observed on 31 October;
  November 1–3 calendars remain unobserved. No month completed, September was not
  seeded, and consecutive empty historical months remain zero. The isolated
  22 October 2025 sample remains separate.
- SQLite integrity `ok`, zero foreign-key violations, and **all 686 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new/historical racecards,
both directories and all 98 collected profiles. Directories returned 2,615 horses
and 2,014 people/party-role records. Single in-process read-plus-JSON samples took
1.2–51.4ms for overview/calendar/racecards, 21.1ms for horses and 92.4ms for people.
These were smoke checks, not browser or load tests; no material growth regression
was observed. No application code was changed.

## 27 October 2026 — evening scheduled maintenance

The trigger arrived at **19:59 Helsinki (17:59 UTC)**; its Helsinki date was
27 October. Preflight found the worker lock free, no failed jobs, pause or
cooldown, and 89/200 daily attempts. Exactly one
`maintain --date 2026-10-27 --max-requests 40` batch finished at **20:11 Helsinki**.
Planning queued six age-eligible refreshes, no profile roots, and no historical
work because October remained `month_pending`. No second batch, manual seeds or
Toto polling followed.

- **25 successful requests:** 20 refreshes and five bounded profiles. Refreshed
  five Kuopio fields from 25 October, Oulu's 30 October calendar, race list and
  all 11 fields, and Lahti's 31 October race list and first field. Unused profile
  and history allowances were not borrowed.
- **32 meetings, 393 races, 4,058 entries and 2,620 horse identities**, including
  ancestor stubs. There are **103 collected profiles**, 75 owner relationships,
  74 breeder relationships and 206 parent links.
- **783 total attempts, 692 snapshots, 114/200 attempts today**, 561 completed
  jobs and **15 pending refresh jobs**: four calendars and 11 fields. No profiles
  remain pending. Unchanged response bodies reuse existing snapshots.
- No failed jobs, provider stops, persistent pause or cooldown. Minimum
  request-start spacing was **30.00010 seconds**; the worker exited and released
  its lock.
- Coverage is unchanged: calendars and race lists through **31 October**, all
  discovered fields through **30 October**, and two of 12 Lahti fields observed
  on 31 October. November 1–3 calendars remain unobserved. No month completed,
  September was not seeded, and consecutive empty historical months remain zero.
  The isolated 22 October 2025 sample remains separate; profiles do not establish
  additional racing-history coverage.
- SQLite integrity `ok`, zero foreign-key violations, and **all 692 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/historical racecards,
both directories and all 103 collected profiles. Directories returned 2,620 horses
and 2,019 people/party-role records. Single in-process read-plus-JSON samples took
2.3–52.5ms for overview/calendar/racecards, 23.4ms for horses and 91.5ms for people.
These were smoke checks, not browser or load tests; no material growth regression
was observed. No application code was changed.


## 28 October 2026 — morning scheduled maintenance

The trigger arrived at **09:43 Helsinki (07:43 UTC)**; its Helsinki date was
28 October. Preflight found the worker lock free, no failed jobs, pause or
cooldown, and 0/200 daily attempts. Exactly one
`maintain --date 2026-10-28 --max-requests 40` batch finished at **10:00 Helsinki**.
Planning queued 26 age-eligible refreshes and five known participant profile
roots, with ancestry bounded to two generations. History remained `month_pending`
for October. No second batch, manual seeds or Toto polling followed.

- **30 successful requests:** 20 refreshes and ten profiles. Refreshed Tampere's
  27 October race list and two fields, Seinäjoki's 26 October calendar, race list
  and all 12 fields, and three Lahti fields from 31 October. Two Lahti fields
  were newly observed, adding 23 entries. The unused history share was not borrowed.
- **32 meetings, 393 races, 4,081 entries and 2,641 horse identities**, including
  ancestor stubs. There are **113 collected profiles**, 81 owner relationships,
  79 breeder relationships and 226 parent links.
- **813 total attempts, 707 snapshots, 30/200 attempts today**, 566 completed
  jobs and **28 pending jobs**: six calendars, 15 fields and seven profiles.
  Unchanged response bodies reuse existing snapshots.
- No failed jobs, provider stops, persistent pause or cooldown. Minimum
  request-start spacing was **30.00004 seconds**; the worker exited normally
  and released its lock.
- Calendars and race lists remain observed through **31 October**, with all
  discovered fields through **30 October** observed. Lahti now has four of 12
  fields observed on 31 October; eight await their first observation. November
  1–4 calendars remain unobserved. No month completed, September was not seeded,
  and consecutive empty historical months remain zero. The isolated 22 October
  2025 sample remains separate; profiles do not establish racing-history coverage.
- SQLite integrity `ok`, zero foreign-key violations, and **all 707 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new/historical racecards,
both directories and all 113 collected profiles. Directories returned 2,641 horses
and 2,031 people/party-role records. Single in-process read-plus-JSON samples took
1.2–38.6ms for overview/calendar/racecards, 18.9ms for horses and 75.0ms for people.
The initial race smoke call used an integer race number and was corrected to the
read model's string identifier contract; the corrected calls passed. These were
smoke checks, not browser or load tests; no material growth regression was observed.
No application code was changed.


## 28 October 2026 — midday transient stop

The trigger arrived at **12:00 Helsinki (10:00 UTC)**. Preflight found the worker
lock free, no failed jobs, persistent pause or cooldown, and 30/200 daily attempts.
Exactly one `maintain --date 2026-10-28 --max-requests 40` command ran. Planning
added no refreshes, profile roots or history jobs; October remained `month_pending`.

The first request, Lahti's 31 October field 3, encountered a **transient transport
failure** (ledger status 0, `http_error`) after about 21 seconds. The command
stopped with exit code 1 at **12:00:43 Helsinki**, before any profile or history
requests. The pending job retains its attempt and `HTTP 0` error; the shared
cooldown and job's next attempt remain **10:01:43.700 UTC / 12:01:43.700 Helsinki**.
Nothing was cleared or retried during this wake-up. No persistent stop, provider
refusal/rate limit/redirect, schema error or failed-status job was recorded. The
automation remains active for a later scheduled wake-up, subject to its usual
preflight and cooldown checks. The worker exited and released its lock.

- **One attempt, zero successful imports**; 814 total attempts and **31/200 today**.
  Request-start spacing from the previous attempt was **7,169.56 seconds**;
  within-batch spacing is not applicable to a single attempt.
- Counts remain **32 meetings, 393 races, 4,081 entries, 2,641 horse identities,
  113 profiles, 81 owner relationships, 79 breeder relationships and 226 parent
  links**. All 707 snapshots are unchanged.
- Queue remains **566 completed, 28 pending** (six calendars, 15 fields, seven
  profiles), with no failed jobs. Profile and history phases did not run.
- Coverage remains calendars/race lists through 31 October, every discovered
  field through 30 October, and four of 12 Lahti fields on 31 October. Eight
  Lahti fields and November 1–4 calendars await their first observation.
  No month completed, September was not seeded, and consecutive empty months
  remain zero. The isolated October 2025 sample is still separate.
- SQLite integrity `ok`, zero foreign-key violations, all **707 snapshot hashes
  verified**. Read-only overview, calendar, current/historical racecards, horse
  and people directories, and all 113 profile views passed. Directory totals
  remain 2,641 horses and 2,031 people/party-role records. In-process read-plus-JSON
  samples were 1.4–38.7ms for overview/calendar/racecards, 18.5ms for horses and
  73.8ms for people. No material UI read-model regression was observed; these are
  smoke checks, not browser/load tests. No application code changed.


## 28 October 2026 — afternoon scheduled maintenance

The trigger arrived at **15:58 Helsinki (13:58 UTC)**; the Helsinki date was
28 October. Preflight found the worker lock free, no failed-status jobs or
persistent pause, and 31/200 daily attempts. The midday transport cooldown had
expired naturally; its stored timestamp and pending-job state were left intact.
Exactly one `maintain --date 2026-10-28 --max-requests 40` batch finished normally
at **16:13 Helsinki**. Planning queued 20 age-eligible refreshes, no new profile
roots and no history work because October remained `month_pending`.

- **30 successful requests:** 20 refreshes and ten bounded profiles. Refreshed
  Vermo's 28 October race list and six fields, plus Tampere's 27 October calendar
  and 12 fields. The history phase had no due jobs; its allowance was not borrowed.
- **32 meetings, 393 races, 4,081 entries and 2,655 horse identities**, including
  ancestor stubs. There are **123 collected profiles**, 87 owner relationships,
  84 breeder relationships and 246 parent links.
- **844 total attempts, 735 snapshots, 61/200 attempts today**, 576 completed
  jobs and **25 pending jobs**: six calendars, 15 fields and four profiles.
- No new failures, provider stops, persistent pause or active cooldown. The
  collector's consecutive-failure count returned to zero after successful work.
  Lahti field 3 was not selected in this batch and retains its pending status,
  one prior attempt, expired next-attempt timestamp and `HTTP 0` error; it has
  not yet had a successful observation. No failed job was reset or manually retried.
- Minimum request-start spacing was **30.00012 seconds**. The worker exited and
  released its lock; no second batch, manual seeds or Toto polling followed.
- Coverage remains calendars/race lists through **31 October**, all discovered
  fields through **30 October**, and four of 12 Lahti fields on 31 October.
  Eight Lahti fields and November 1–4 calendars await their first observation.
  No month completed, September was not seeded, and consecutive empty historical
  months remain zero. The isolated October 2025 sample remains separate;
  completed profiles do not establish additional racing-history coverage.
- SQLite integrity `ok`, zero foreign-key violations and **all 735 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/historical racecards,
both directories and all 123 collected profiles. Directories returned 2,655 horses
and 2,040 people/party-role records. Single in-process read-plus-JSON samples took
1.5–35.1ms for overview/calendar/racecards, 18.7ms for horses and 72.5ms for people.
These were smoke checks, not browser or load tests; no material growth regression
was observed. No application code changed.


## 29 October 2026 — scheduled maintenance

The trigger arrived at **14:16 Helsinki (12:16 UTC)**; its Helsinki date was
29 October. Preflight found the worker lock free, no failed-status jobs,
persistent pause or active cooldown, and 0/200 daily attempts. Exactly one
`maintain --date 2026-10-29 --max-requests 40` batch finished normally at
**14:30 Helsinki**. Planning queued 55 age-eligible refreshes and no profile
roots because profiles were already pending. History remained `month_pending`
for October. No second batch, manual seeds or Toto polling followed.

- **27 successful requests:** 20 refreshes and seven bounded profiles. Refreshed
  Turku's 29 October calendar, race list and all 11 fields, plus Oulu's 30 October
  race list and six fields. Pending profiles finished; no additional roots were
  seeded mid-run. History had no due jobs, and unused phase shares were not borrowed.
- **32 meetings, 393 races, 4,081 entries and 2,665 horse identities**, including
  ancestor stubs. There are **130 collected profiles**, 91 owner relationships,
  88 breeder relationships and 260 parent links.
- **871 total attempts, 756 snapshots, 27/200 attempts today**, 549 completed
  jobs and **56 pending jobs**: ten calendars, three race lists and 43 fields.
  No profiles remain pending. Completed-job counts can decrease when old
  observations become eligible for refresh; earlier coverage remains observed.
- No new failures, provider stops, persistent pause or active cooldown.
  Lahti's 31 October field 3 was not selected and retains its pending status,
  one prior transport-failure attempt and expired retry timestamp. Nothing was
  manually reset. Minimum request-start spacing was **30.00011 seconds**;
  the worker exited and released its lock.
- Coverage remains calendars/race lists through **31 October**, all discovered
  fields through **30 October**, and four of 12 Lahti fields on 31 October.
  Eight Lahti fields and November 1–5 calendars await their first observation.
  No month completed, September was not seeded, and consecutive empty historical
  months remain zero. The isolated October 2025 sample remains separate;
  completed profiles do not establish additional racing-history coverage.
- SQLite integrity `ok`, zero foreign-key violations and **all 756 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/historical racecards,
both directories and all 130 collected profiles. Directories returned 2,665 horses
and 2,047 people/party-role records. Single in-process read-plus-JSON samples took
1.4–33.5ms for overview/calendar/racecards, 17.2ms for horses and 68.3ms for people.
These were smoke checks, not browser or load tests; no material growth regression
was observed. No application code changed.


## 29 October 2026 — afternoon batch and evening execution block

The **15:59 Helsinki (13:59 UTC)** trigger started exactly one
`maintain --date 2026-10-29 --max-requests 40` batch after a free-lock, healthy
preflight at 27/200 daily attempts. Planning added three age-eligible refreshes
and five known participant roots, bounded to two ancestor generations; October
remained `month_pending`. The ledger records **30 successful requests** from
**16:00:21 to 16:14:52 Helsinki** (IDs 872–901): 20 refreshes and ten profiles.
Refreshes covered Oulu's 30 October calendar and remaining five fields, Vermo's
28 October calendar, race list and all 11 fields, and Lahti's 31 October race list.
No historical requests were recorded; unused shares were not borrowed.

The next trigger arrived at **20:08 Helsinki (18:08 UTC)** while the prior turn's
completion handling was unfinished. Its previous tool session was no longer
available, so an exit code could not be recovered. Read-only checks confirmed
all 30 requests finished successfully and the worker lock was free. An attempted
evening maintenance launch was **rejected before process creation by automatic
approval review**, which treated it as another batch in the same wake-up and
cited the one-batch restriction. No workaround or further launch was attempted;
no evening upstream request was sent. The automation remains active, with no
provider stop or persistent collector pause. The rejection is an execution
approval restriction, not a provider refusal.

- **32 meetings, 393 races, 4,081 entries and 2,680 horse identities**, including
  ancestor stubs; **140 profiles**, 99 owner relationships, 95 breeder
  relationships and 280 parent links.
- **901 total attempts, 781 snapshots and 57/200 attempts today**. Queue:
  **572 completed, 51 pending** (eight calendars, two race lists, 33 fields,
  eight profiles); no failed-status jobs.
- No provider stops or active cooldown; consecutive failures are zero.
  Minimum spacing in the afternoon batch was **30.00010 seconds**. The older
  expired cooldown was not cleared. No manual seeds, job resets or Toto polling.
- Coverage is unchanged: calendars/race lists through **31 October**, all
  discovered fields through **30 October**, and four of 12 Lahti fields on
  31 October. Eight Lahti fields and November 1–5 calendars remain unobserved.
  No month completed, September was not seeded, and empty historical months
  remain zero. The isolated October 2025 sample remains separate.
- Evening verification: SQLite integrity `ok`, zero foreign-key violations,
  all **781 snapshot hashes verified**, and worker lock free. Overview, calendar,
  current/historical racecards, both directories and all 140 profile views passed.
  Directories returned 2,680 horses and 2,061 people/party-role records.
  In-process read-plus-JSON samples took 1.3–34.4ms for overview/calendar/racecards,
  17.5ms for horses and 70.8ms for people. These are smoke checks, not browser/load
  tests; no material read-model regression was observed. No application code changed.


## 30 October 2026 — October first-observation coverage completed

The trigger arrived at **12:04 Helsinki (10:04 UTC)**; its Helsinki date was
30 October. Preflight found the worker lock free, no failed-status jobs,
persistent pause or active cooldown, and 0/200 daily attempts. Exactly one
`maintain --date 2026-10-30 --max-requests 40` command finished with exit code 0
at **12:19 Helsinki**. Planning added 14 age-eligible refreshes and no profile
roots because profiles remained pending. October was `month_pending` at planning
time, so no September jobs were seeded. No second batch or manual seeds followed.

- **30 successful requests:** 20 refresh-queue requests and ten bounded profiles.
  Collected/refreshed all 12 Lahti fields and its 31 October calendar, then the
  November 1 Joensuu calendar, 16-race list and five fields. Eight Lahti fields
  and five Joensuu fields were newly observed, adding **133 entries**. History
  had no due jobs; unused shares were not borrowed. No Toto polling occurred.
- **33 meetings, 409 races, 4,214 entries and 2,714 horse identities**, including
  ancestor stubs; **150 profiles**, 103 owner relationships, 98 breeder
  relationships and 300 parent links.
- **931 total attempts, 806 snapshots and 30/200 attempts today**. Queue:
  **589 completed, 58 pending** (eight calendars, two race lists, 44 fields,
  four profiles). No failed jobs, provider stops or active cooldown.
- Lahti field 3, which had a transient transport error on 28 October, succeeded
  through the ordinary queue after its cooldown. Its job is now done with two
  total attempts. No manual retry/reset or pause clearing was performed.
- Minimum request-start spacing: **30.00012 seconds**. The worker exited and
  released its lock.
- **October now has a successful observation for every currently discovered
  racing job:** 31 calendars, 31 race lists and 382 fields (444 jobs). Pending
  refreshes retain those earlier observations. This is the first contiguous
  month completed under the observation policy, not complete final results:
  some races are still upcoming and source data can change. September remains
  unseeded and is the next historical month for a later wake-up. The isolated
  October 2025 sample does not skip the intervening year; empty historical
  months remain zero. Profiles do not establish racing-history coverage.
- November 1 Joensuu has five of 16 fields observed; 11 fields and November
  2–6 calendars await first observations.
- SQLite integrity `ok`, zero foreign-key violations and **all 806 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new/historical
racecards, both directories and all 150 profile views. Directories returned
2,714 horses and 2,080 people/party-role records. In-process read-plus-JSON
samples took 1.4–37.2ms for overview/calendar/racecards, 18.5ms for horses and
76.1ms for people. These are smoke checks, not browser/load tests; no material
read-model regression was observed. No application code changed.


## 30 October 2026 — afternoon September backfill started

The trigger arrived at **16:00 Helsinki (14:00 UTC)**; its Helsinki date was
30 October. Preflight found the worker lock free, no failed jobs, persistent
pause or active cooldown, and 30/200 daily attempts. Exactly one
`maintain --date 2026-10-30 --max-requests 40` batch exited normally at
**16:18 Helsinki**. Planning seeded September's 30 calendars, queued 21
age-eligible refreshes and no profile roots because profiles remained pending.
No second batch, manual seeds or Toto polling followed.

- **38 successful requests:** 20 refreshes, eight profiles and ten history
  requests. Refreshed Oulu's 30 October race list and seven fields, and Turku's
  29 October race list and all 11 fields. Pending profiles finished; their two
  unused request slots were not borrowed.
- Historical collection observed **30 September's Vermo calendar, 12-race list
  and eight fields**, adding **81 entries**. Four fields on that date and the
  September 1–29 calendars await first observation. September is not complete;
  no earlier month was seeded.
- **34 meetings, 421 races, 4,295 entries and 2,741 horse identities**, including
  ancestor stubs; **158 profiles**, 108 owner relationships, 101 breeder
  relationships and 316 parent links.
- **969 total attempts, 840 snapshots, 68/200 attempts today**. Queue:
  **606 completed, 88 pending** (38 calendars, two race lists and 48 fields).
  No pending profiles, failed jobs, provider stops or active cooldown.
- Minimum request-start spacing was **30.00007 seconds**; the worker exited
  with code 0 and released its lock. No pauses, budgets or failed jobs were reset.
- October retains successful observations for all discovered racing jobs;
  pending refreshes do not erase that coverage or establish final-result
  completeness. November 1 still has five of 16 Joensuu fields observed;
  November 2–6 calendars remain unobserved. One contiguous month is observed,
  consecutive empty historical months remain zero, and the isolated October
  2025 sample does not skip the intervening year.
- SQLite integrity `ok`, zero foreign-key violations and **all 840 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new-historical/older
racecards, both directories and all 158 profile views. Directories returned
2,741 horses and 2,090 people/party-role records. In-process read-plus-JSON
samples took 0.7–36.9ms for overview/calendar/racecards, 22.1ms for horses and
73.2ms for people. These are smoke checks, not browser/load tests; no material
read-model regression was observed. No application code changed.


## 30 October 2026 — evening scheduled maintenance

The trigger arrived at **19:58 Helsinki (17:58 UTC)**; its Helsinki date was
30 October. Preflight found the worker lock free, no failed jobs, persistent
pause or active cooldown, and 68/200 daily attempts. Exactly one
`maintain --date 2026-10-30 --max-requests 40` batch exited with code 0 at
**20:18 Helsinki**. Planning queued 19 age-eligible refreshes and five known
participant profile roots bounded to two generations. Existing September work
kept history at `history_pending`; no additional month was seeded.

- **40 successful requests:** 20 refresh-queue requests, ten profiles and ten
  history requests. Refreshed Oulu's 30 October calendar and four fields,
  Lahti's 31 October race list, Turku's 29 October calendar, and Vermo's
  28 October race list/first field. Collected all 11 remaining Joensuu fields
  for November 1, adding 112 entries; all 16 fields now have observations.
- Historical collection finished the four remaining September 30 Vermo fields
  and observed September 29's Seinäjoki calendar, 12-race list and four fields,
  adding 81 entries. September 29 still has eight unobserved fields; September
  1–28 calendars remain unobserved. September is not complete.
- **35 meetings, 433 races, 4,488 entries and 2,800 horse identities**, including
  ancestor stubs; **168 profiles**, 118 owner relationships, 111 breeder
  relationships and 336 parent links.
- **1,009 total attempts, 878 snapshots, 108/200 attempts today**. Queue:
  **627 completed, 102 pending** (37 calendars, two race lists, 51 fields,
  12 profiles). No failed jobs, provider stops or active cooldown.
- Minimum request-start spacing was **30.00006 seconds**; the worker exited
  and released its lock. No second batch, manual seeds, job resets, pause
  clearing or Toto polling followed.
- October remains the one contiguous month with all currently discovered racing
  jobs observed; this does not establish complete final results. November 1
  now has all discovered racing jobs observed, while November 2–6 calendars
  remain unobserved. No additional month completed. Consecutive empty historical
  months remain zero; the isolated October 2025 sample stays separate.
- SQLite integrity `ok`, zero foreign-key violations and **all 878 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new-historical/older
racecards, both directories and all 168 profile views. Directories returned
2,800 horses and 2,142 people/party-role records. In-process read-plus-JSON
samples took 0.6–40.2ms for overview/calendar/racecards, 21.5ms for horses and
78.5ms for people. These are smoke checks, not browser/load tests; no material
read-model regression was observed. No application code changed.


## 31 October 2026 — morning scheduled maintenance

The trigger arrived at **10:41 Helsinki (08:41 UTC)**; its Helsinki date was
31 October. Preflight found the worker lock free, no failed jobs, persistent
pause or active cooldown, and 0/200 daily attempts. Exactly one
`maintain --date 2026-10-31 --max-requests 40` batch exited with code 0 at
**11:01 Helsinki**. Planning added one refresh calendar and no profile roots
because profiles remained pending. September remained `history_pending`;
no additional month was seeded.

- **40 successful requests:** 20 refresh-queue requests, ten profiles and ten
  history requests. Collected November 2's Kaustinen calendar, 12-race list
  and all 12 fields (**144 entries**), and refreshed six Vermo fields from
  October 28. History finished the eight remaining September 29 Seinäjoki
  fields (**103 entries**) and observed September 28's Pori calendar and
  13-race list. All 13 Pori fields await first observation.
- **37 meetings, 458 races, 4,735 entries and 2,874 horse identities**, including
  ancestor stubs; **178 profiles**, 127 owner relationships, 120 breeder
  relationships and 356 parent links.
- **1,049 total attempts, 913 snapshots, 40/200 attempts today**. Queue:
  **667 completed, 95 pending** (36 calendars, two race lists, 50 fields,
  seven profiles). No failed jobs, provider stops or active cooldown.
- Minimum request-start spacing was **30.00012 seconds**; the worker exited
  and released its lock. No second batch, manual seeds, job resets, pause
  clearing or Toto polling followed.
- October remains the one contiguous month with all currently discovered racing
  jobs observed. September 29–30 now have all discovered fields observed;
  September 28's fields and September 1–27 calendars remain unobserved.
  November 1–2 have all discovered fields observed; November 3–7 calendars
  remain unobserved. No additional month completed. Observations do not establish
  complete final results or complete horse histories; the isolated October
  2025 sample remains separate. Consecutive empty historical months remain zero.
- SQLite integrity `ok`, zero foreign-key violations and **all 913 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new/historical/older
racecards, both directories and all 178 profile views. Directories returned
2,874 horses and 2,192 people/party-role records. In-process read-plus-JSON
samples took 0.5–41.7ms for overview/calendar/racecards, 22.4ms for horses and
78.8ms for people. These are smoke checks, not browser/load tests; no material
read-model regression was observed. No application code changed.


## 31 October 2026 — midday scheduled maintenance

The trigger arrived at **11:55 Helsinki (09:55 UTC)**; its Helsinki date was
31 October. Preflight found the worker lock free, no failed jobs, persistent
pause or active cooldown, and 40/200 daily attempts. Exactly one
`maintain --date 2026-10-31 --max-requests 40` batch exited with code 0 at
**12:15 Helsinki**. Planning added no refreshes or profile roots; existing
September work remained `history_pending`. No additional month was seeded.

- **40 successful requests:** 20 refreshes, ten profiles and ten history requests.
  Refreshed Vermo's 28 October calendar and four fields, plus Tampere's
  27 October race list and all 14 fields. Those Tampere jobs were already queued
  before leaving the current rolling window. History collected ten September 28
  Pori fields, adding **112 entries**; fields 7–9 remain unobserved.
- **37 meetings, 458 races, 4,847 entries and 2,920 horse identities**, including
  ancestor stubs; **188 profiles**, 136 owner relationships, 129 breeder
  relationships and 376 parent links.
- **1,089 total attempts, 933 snapshots, 80/200 attempts today**. Queue:
  **707 completed, 60 pending** (35 calendars, one race list, 22 fields,
  two profiles). No failed jobs, provider stops or active cooldown.
- Minimum request-start spacing was **30.00016 seconds**; the worker exited
  and released its lock. No second batch, manual seeds, job resets, pause
  clearing or Toto polling followed.
- October remains the one contiguous month with all currently discovered racing
  jobs observed. September 29–30 are observed; September 28 has ten of 13 fields,
  and September 1–27 calendars remain unobserved. November 1–2 have all discovered
  fields observed; November 3–7 calendars remain unobserved. No additional month
  completed, and consecutive empty historical months remain zero. Observations
  do not establish complete final results or horse histories; the isolated
  October 2025 sample remains separate.
- SQLite integrity `ok`, zero foreign-key violations and **all 933 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new-historical/older
racecards, both directories and all 188 profile views. Directories returned
2,920 horses and 2,231 people/party-role records. In-process read-plus-JSON
samples took 0.7–42.8ms for overview/calendar/racecards, 19.4ms for horses and
81.9ms for people. These are smoke checks, not browser/load tests; no material
read-model regression was observed. No application code changed.


## 31 October 2026 — afternoon scheduled maintenance

Heartbeat at 14:04:51 UTC (16:04 Helsinki); the client date in Helsinki was
**2026-10-31**. Preflight found the worker lock free, no persistent stop, failed
jobs or active cooldown, and **80/200** attempts used that UTC day. The previous
wake-up's batch had exited at 10:15 UTC. Ran exactly one approved command:
`python -u -m hippos_analyst maintain --date 2026-10-31 --max-requests 40`.

- Planning queued 33 refresh jobs, no new profile roots and no historical month
  because history was pending. The batch completed **32 successful requests**:
  20 refresh, two remaining profiles and ten history requests. The unused eight
  profile requests were not borrowed. Request IDs **1090–1121** ran from
  **14:06:30 to 14:22:00 UTC**; the command exited successfully.
- Refresh observed all 12 Lahti October 31 fields and its calendar, plus the
  November 1 Joensuu race list, five fields and calendar. Other queued refreshes
  remain pending; this is not a guarantee that all upcoming data is current.
- History finished September 28 Pori's final three fields, observed September
  27's three-meeting calendar, then the PS race list and five fields. The archive
  gained **77 entries**. September 27 still needs eight PS fields and the PX/Y
  race lists; September 1–26 calendars remain unobserved.
- **40 meetings, 471 races, 4,924 entries and 2,941 horse identities**, including
  ancestor stubs; **190 profiles**, 138 owner relationships, 131 breeder
  relationships and 380 parent links. No profiles remain pending.
- **1,121 total attempts, 961 snapshots, 112/200 attempts today**. Queue:
  **706 completed, 77 pending** (34 calendars, five race lists, 38 fields).
  No failed jobs, provider stops or active cooldown. The expired cooldown value
  was preserved. Minimum request-start spacing was **30.00012 seconds** and the
  worker released its lock. No second batch, manual seeds, resets or Toto polling.
- October remains the one contiguous month with all 31 calendars, 31 discovered
  race lists and 382 fields observed. No additional month completed; consecutive
  empty historical months remain zero. November 1–2 have all discovered fields
  observed, while November 3–7 calendars remain unobserved. The isolated October
  2025 sample remains separate. Observations do not establish complete final
  results or complete horse histories.
- SQLite integrity `ok`, zero foreign-key violations and **all 961 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new-historical/older
racecards, both directories and all 190 profile views. Directories returned
2,941 horses and 2,252 people/party-role records. In-process read-plus-JSON samples
took 0.4–44.1ms for overview/calendar/racecards, 22.6ms for horses and 92.3ms for
people. These are smoke checks, not browser/load tests; no material read-model
regression was observed. No application code changed.


## 31 October 2026 — evening scheduled maintenance

Heartbeat at 17:56:24 UTC (19:56 Helsinki); the date derived from the current
client timestamp in Europe/Helsinki was **2026-10-31**. Preflight found a free
worker lock, no persistent stop, failed jobs or active cooldown, and **112/200**
attempts used that UTC day. The previous batch had exited at 14:22 UTC. Ran
exactly one approved command:
`python -u -m hippos_analyst maintain --date 2026-10-31 --max-requests 40`.

- Planning queued seven refresh jobs and five known-participant profile roots,
  bounded to two ancestor generations. No profiles were pending at preflight;
  the persisted seed day was October 30. No new historical month was seeded
  because history was pending.
- **40 successful requests**: 20 refresh, ten profiles and ten history.
  Request IDs **1122–1161** ran from **17:56:46 to 18:16:16 UTC**; the command
  exited successfully. Refresh covered the October 30 Oulu race list and seven
  fields, plus the October 29 Turku race list and all 11 fields. Remaining
  refresh work stays queued; this is not a live feed or freshness guarantee.
- History finished September 27's eight remaining PS fields, then collected
  the PX eight-race list and its first field, adding **66 entries**. Seven PX
  fields and the Y race list remain unobserved on September 27. September
  1–26 calendars remain unobserved; September 28–30 retain full first-observation
  coverage of their discovered fields.
- **40 meetings, 479 races, 4,990 entries and 2,979 horse identities**, including
  ancestor stubs; **200 profiles**, 148 owner relationships, 141 breeder
  relationships and 400 parent links.
- **1,161 total attempts, 989 snapshots, 152/200 attempts today**. Queue:
  **739 completed, 73 pending** (34 calendars, two race lists, 26 fields and
  11 profiles). No failed jobs, provider stops or active cooldown; the expired
  cooldown value was preserved. Minimum request-start spacing was
  **30.00011 seconds**. The worker released its lock; no second batch, manual
  seeds, resets, completed-profile refreshes or Toto polling followed.
- October remains the one contiguous observed month: all 31 calendars,
  31 discovered race lists and 382 fields have successful observations.
  November 1–2 retain all discovered fields observed; November 3–7 calendars
  remain unobserved. No additional month completed and consecutive empty
  historical months remain zero. The isolated October 2025 sample remains
  separate. Observations do not establish complete final results or horse histories.
- SQLite integrity `ok`, zero foreign-key violations and **all 989 snapshot
  hashes verified**.

Read-only UI checks passed for overview, calendar, current/new-historical/older
racecards, both directories and all 200 profile views. Directories returned
2,979 horses and 2,291 people/party-role records. In-process read-plus-JSON samples
took 0.3–43.7ms for overview/calendar/racecards, 20.3ms for horses and 82.4ms for
people. These are smoke checks, not browser/load tests; no material read-model
regression was observed. No application code changed.
