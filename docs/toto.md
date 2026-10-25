# Veikkaus Toto enrichment

Pilot implemented 25 October 2026. The historical odds omission was fixed and
live-verified later that day; collection was resumed with the owner’s authorization. Hippos remains the primary racing archive. Toto is
an optional, bounded enrichment source for explicitly selected Finnish races.
The browser reads SQLite only and never polls either provider.

## Access and limits

The [official Toto documentation](https://github.com/veikkaus/sport-games-robot#toto-pelit)
documents `X-ESA-API-Key: ROBOT` for automated clients. This shared identifier is
not a personal secret. The calendar, race, participant, pool and odds calls tested
on 25 October worked without account login, cookies or a personal API key.
No evidence establishes that a personal key increases the quota for these
endpoints. The separate developer portal must not be assumed to use the same API
or access agreement. Do not create an account or purchase access just for this pilot.

Official guidance advises against odds polling more frequently than once a minute
and limits parallel processes to four. Those are not a published daily allowance.
Our implementation is deliberately stricter:

- One shared OS worker lock for Hippos and Toto, one shared request ledger and
  global stop/cooldown state in `data/hippos.sqlite3`.
- At least 60 seconds between Toto request starts, persisted across runs.
- At most 40 Toto attempts per UTC day, including the recorded research probes;
  at most 200 combined attempts per UTC day for `run-toto`. The Hippos automation
  also uses the 200-attempt budget. Never raise its budget to get around this cap.
- At most 20 requests in one Toto run; the default is eight. Select at most three
  races per seed and at most three observations per race, at least 15 minutes apart.
- Only five documented GET endpoint families. No wagering, login, redirects,
  arbitrary URLs, cookie sessions, or account credentials.
- HTTP 401/403/429, redirects and schema errors persistently pause collection.
  Retry-After survives restarts. Transient failures stop the run without retrying
  during it. Failed jobs are never requeued automatically. Existing global stops
  also block Toto. Both scheduled workers must honor these controls.

Storage/reuse rights are not established merely by public API access. The reference
implementation's licence is not a general dataset licence; none of its code was
copied. Provider objections or limits stop collection for investigation.

## Commands

Run from the repository root. Seeding is offline and requires the corresponding
Hippos fields to be present already:

```powershell
python -m hippos_analyst seed-toto --date 2026-10-25 --track KU --races 1,9 --samples 3 --interval 900
python -u -m hippos_analyst run-toto --max-requests 8 --delay 60 --daily-budget 200
python -m hippos_analyst status
```

A repeated seed for the same meeting is a no-op, including completed work. This
pilot has no automatic meeting expansion or refresh command. `run` processes only
Hippos jobs; `run-toto` processes only due Toto jobs. Neither bypasses the shared
lock. When only future jobs remain, the command exits instead of keeping a worker
alive. Later invocations pick up those jobs after their persisted due time.

Each successful odds observation may queue the next one, up to the seed's limit,
only when the recorded pool status is OPEN or CONNECTED and its due time is earlier than the
recorded scheduled start. A delayed run can still save an observation after start;
it is explicitly classified as such and schedules no further samples. This is a
snapshot service, not a live race feed. Participant and pool metadata are captured
once per selected race; each quote has its own source-update and collection times.

## Matching and storage

The importer verifies the requested date, Finnish trotting card and matching track
abbreviation, then race number and base distance. It compares the entire runner
field by program number, normalized exact name and participant distance. Only a
complete, unambiguous match links provider runners to the existing Hippos IDs.
It never merges the global horse directory by name. Unsupported track aliases or
field disagreements remain unmatched and do not trigger odds collection.

The separate `toto_targets` table retains provider IDs, matching state, scheduled
start and minimized participant data. `toto_observations` retains each observation
with its request ID, provider pool/race IDs, fetch time, scheduled-start snapshot,
phase and per-runner quotes. Existing Hippos records are not overwritten. Read
models recheck current Hippos identities before exposing stored observations.

The existing `jobs`, `requests` and `snapshots` tables are shared. `toto:` prefixes
separate provider paths; `@1`, `@2`, `@3` identify observations locally and are never
sent to Veikkaus. A repeated identical response can share a content snapshot while
retaining distinct request/observation timestamps. All writes commit atomically.

Only selected identity, distance, scratch, equipment, driver-statistic and odds
fields are retained. Owner hometown, vaccination, free-text comments, betting
accounts and irrelevant nested fields are dropped. Driver statistics remain a
source string with an unknown statistical period; they are not displayed or used
as model features. Previous-start summaries and other betting pools are not part
of this first importer.

## Odds, UI and prediction boundaries

The live win-pool response represents `probable` in hundredths: an observed value
1009 corresponds to 10.09, corroborated by netPool 16146 / runner amount 1600.
The original integer is stored; zero displays as unavailable. Monetary pool values
are not imported, so no euro-unit conversion is assumed.

Racecards show a source-labelled win-odds column. Matched Toto observations take
precedence for that column; a missing quote in a newer observation never silently
revives an old Hippos quote. Otherwise existing Hippos win odds are shown. Source
records remain separate. The horse's inline expansion shows up to three observed
prices with both source-update and collection timestamps and the timing category.
Coverage includes Toto target, match and observation counts. Matching failures
remain visible; an absent enrichment does not imply absent races or odds.

Hippos shoeing and sulky codes now appear under the horse's name. Unknown codes
remain unknown. These describe the timestamped Hippos field, and may disagree
with newer Toto equipment; no source is silently overwritten. Race rows and
expanded observations now flow down the page without nested vertical scrolling;
wide tables retain horizontal scrolling. See [current UI behavior](ui.md).

`before_scheduled_start` means both the local fetch and the provider update precede
the recorded scheduled time. It is not proof of the actual off time. A future model
must apply its own prediction cutoff to both timestamps, enforce a pre-start safety
margin, and split evaluation chronologically. Historical data fetched today must
never be presented as information available to a prediction made last year.

## Historical coverage verified

On 25 October 2026, authenticated-account-free probes returned:

- Kuopio, 25 October 2026: nine Toto races, participants and an open win-odds pool.
  Hippos also includes trial/pony races that Toto's race list omits.
- Vermo, 22 October 2025: ten races marked OFFICIAL, nine participants in race 1,
  a win pool marked FINAL and all nine win-odds entries with an October 2025 source
  update timestamp. Its runner sample lacked the current response's `prevStarts`.

This verifies a historical example, not continuous coverage or the oldest available
record. The documented date lookup does not provide historical odds movements;
those must be observed prospectively unless a separate history feed is verified.

## Verification

Synthetic tests cover the complete Hippos-to-Toto linking path, duplicate seeding,
three-sample bounds, source units, identity/field conflicts, foreign IDs, mismatched
dates, malformed/duplicate odds, historical timing, schema rollback, global and
provider budgets, cooldowns, redirects/refusals, header/path validation and response
size limits. Frontend tests distinguish missing/zero quotes, source identity and
unknown equipment codes. All 78 Python tests and 23 JavaScript tests pass, along
with the module syntax check and whitespace check.


## Live pilot and current stop — 25 October 2026

The single bounded batch exited after 13 requests: 12 saved responses and one
schema failure. All three selected fields matched completely: Kuopio races 1 and
9 (10 and 15 runners), and Vermo 22 October 2025 race 1 (nine runners).
Two immutable odds observations were saved, at approximately 12:52 and 12:55
Helsinki time, both before the respective scheduled starts. The UI displays the
quotes and timestamps in the racecard and inline horse expansion.

The historical pool request returned HTTP 200, but normalization rejected a
`probable` value (`Invalid Toto probable odds`). Its raw body was deliberately
not retained. The earlier minimized research summary retains only two valid
examples, so the exact rejected value/type cannot be established offline.
Historical final-odds access is verified; importing every historical quote is
**not** verified and remains blocked. Do not guess a sentinel or silently drop it.
No retry or pause clearing was performed. A future investigation needs an
explicitly authorized, narrowly scoped diagnostic before any retry/resumption.

The shared persistent stop remains set; the daily `grow-hippos-archive-slowly`
automation was changed to PAUSED. No Toto automation was created. One Toto job is
failed, no Toto jobs are pending, and the three pre-existing Hippos jobs remain
pending. The pilot's current pools returned CONNECTED; the initial worker only
scheduled follow-ups for OPEN, so neither generated another observation. The
code now accepts both observed CONNECTED and OPEN for bounded future sampling,
with a synthetic three-observation regression test. Completed pilot jobs were
not refreshed or retroactively expanded. Unknown pool states never add samples.

There were 125 combined attempts today: 100 Hippos, 12 Toto research and 13 Toto
import requests. Minimum importer request-start spacing was 60.00013 seconds.
No rate limit, redirect or access refusal occurred. The problem is response
compatibility, not an API key or a quota. SQLite integrity is `ok`, with no
foreign-key violations and all 438 stored snapshot hashes verified.

Initial pilot browser checks used the live archive on desktop and at 390×844.
The fixed-height layout measured here was subsequently replaced with natural
page scrolling; see the later verification in [UI documentation](ui.md). The odds column,
source labels, inline observation and historical failure state rendered correctly.
At 1440×1000 a direct race change preserved scroll Y=78, document height=1217 and
panel height=852. At phone width, switching from an enriched to an unenriched
race retained scroll Y=607.33; document height differed by one CSS pixel
(1451 to 1452). This is not a claim of exact pixel equality at every viewport.
The local server was restarted on port 8765 with the new read models.


## Historical parser recovery — 25 October 2026

The owner explicitly authorized diagnosis, repair and resumption. One logged
retry showed that runner 6, scratched in both the stored field and the provider
runner record, **omits** `probable`. This is absence of a quote, not an invalid
negative price. The parser now stores an omitted value as JSON null. Supplied
null, strings, booleans and negative prices remain rejected; no broader relaxation
was made. The UI displays the missing price as unavailable and keeps its source.

The diagnostic used the same collector lock, ledger, spacing and budgets, and
reproduced the persistent schema stop. After the regression passed, only the
identified failed job was requeued and the schema stop cleared under the owner's
explicit authorization. Its live retry succeeded: the historical observation now
contains eight prices and one unavailable quote. There are three stored Toto
observations across three matched fields. This recovery does not authorize future
automatic retries or bypasses. `maintain` schedules Hippos work, not new Toto polls.
