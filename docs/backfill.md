# Gradual archive backfill

Updated 25 October 2026. The owner requested continued slow collection, broad
historical coverage, UI growth checks, and a stop on crawling limits.

## Scope and progress frontier

The long-term target is all available public Finnish racing calendars, race
lists, participants and results, plus selected horse profiles and bounded ancestry
through the four implemented endpoint families. This does not cover every Heppa
record: complete offspring registers, historical ownership, foreign meetings and
other services still require research. Explicit field allowlists remain in effect. Historical depth and
nationwide completeness are unknown; an empty response is not proof of either.

- Current contiguous window being filled: **2026-10-01 through 2026-10-31**.
- Observed calendars and race lists now cover **1–29 October 2026**. All discovered
  fields for **1–29 October** now have successful observations. October 30–31
  and November 1 calendars are queued but not yet observed.
  The empty 29 October race list is an
  observation, not a guarantee that no races will be published later.
- Earlier isolated sample: **2025-10-22**. Do not jump to September 2025 on account
  of this sample; the intervening year has not been collected.
- Next historical month after the pending queue finishes: **September 2026**.
- Contiguous completed historical months: **none yet**.
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
