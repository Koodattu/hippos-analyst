# Autonomous product improvement state

Started 22 October 2026. Single-agent implementation and self-review; no independent
review or user interviews are claimed. Authority: the user's attached autonomous
product/UX/engineering brief, including commit, normal push and established deployment.

## Starting state and release boundary

- HEAD: `97f3fe6f32ad1d5221a8aaca65dddb19414dd450` (Initial commit), branch `main`.
- Remote: `https://github.com/Koodattu/hippos-analyst.git`, public, default `main`.
- Existing unstaged modifications: `.gitignore`, `README.md`; no staged changes.
- Existing untracked project work: `docs/`, `hippos_analyst/`, `scripts/`, `tests/`.
  This is the app built in the preceding turns, not an empty project. Preserve it.
- Source/document snapshot and SHA-256 manifest: ignored
  `data/product-improvement-baseline/`; no racing database copied.
- GitHub identity/repository access verified using escalated Git/gh after the
  sandbox lacked Credential Manager access. No credentials copied or changed.
- Remote main matches local HEAD, is unprotected. No GitHub Actions workflows or
  deployments were returned. Local tracked tree contains only README, licence,
  gitignore. No hosting/deployment configuration found. Remote deployment is a
  missing prerequisite; do not provision hosting or alter deployment policy.
- Established runtime is the private loopback Python server. Final release must
  include its required source, not depend on omitted untracked foundation files.
  Do not publish data/, screenshots of collected records, databases or diagnostics.

## Product brief and standard

Documented user: a Finnish horse racer and family; broader racing enthusiasts are
compatible secondary users. Principal jobs: find an upcoming meeting, compare its
runners, inspect results, revisit a horse's collected history. Frequent returning
use and phone use at a racecourse are assumptions, not interview evidence.

Promise: understandable racing evidence with few clicks, useful density and honest
coverage. Keep the Python/SQLite/vanilla ES-module stack, Finnish locale, local-only
access, provider field allowlists, rate limits and persistent stops. No wagering,
invented predictions, cloud accounts or licence claims.

Quality standard: selected race remains the focal evidence; core information is
readable at desktop and 320-pixel width; saved context survives return/reload;
unknown, future, scratch and result states stay distinct; recurring horse lookup
should not require repeated name entry; archive completeness/freshness must be
understandable without reading SQLite or operations docs. Preserve the useful
calendar/race split, inline history, native controls, green/neutral visual identity.

Primary visual discipline: Interface Design for this dense operational tool.
End-User UI/UX governs complete journeys and recovery. Impeccable Operate guidance
supports familiarity and self-critique, not a competing redesign. Explore domain:
race day, lähtö, lähtönumero, ravirata, ohjastaja, koelähtö, kilometri-aika.
Natural palette: dark rail green, pale paper, white race sheets, charcoal ink,
muted turf, restrained amber exceptions. Signature: numbered race navigation next
to a readable field and contextual horse form. Reject generic KPI dashboard,
betting coupon UI and decoration that consumes the evidence viewport.

## Skills applied so far

- End-User UI/UX SKILL: task success before novelty; functional/visual QA separate.
- Interface Design SKILL: operational density, coherent components and focal field.
- Impeccable SKILL, Operate and critique guidance: existing visual truth, restrained
  state vocabulary, sequential self-review per user's explicit single-agent rule.
  Context launcher ran once successfully against app.mjs; it did not recognize
  the existing .mjs visual implementation. Existing code/browser/docs are the
  authority. No simulated user approval, helper injection, skill/policy updates.
- Research SKILL: primary sources documented directly; delegation clause overridden
  by explicit user instruction to work alone.
- Data-visualization router and visualization-strategy-and-critique: choose tables
  for exact comparison, keep missingness/source context beside evidence.
- Software engineering/performance skills and prior verification remain available.

Before each implementation batch, load only the needed remaining specialists,
TDD/debug/architecture references and Impeccable craft floor. Run its detector once
on finished changed UI; no browser injection through read-only evaluation.

## Baseline and coverage

- Current app: http://127.0.0.1:8765 (server session 42568).
- Existing verified baseline: 44 Python + 13 JS tests; 1,000-meeting/100,000-horse
  benchmark in docs/archive-growth.md, calendar pages 30 meetings.
- Actual journey used this pass: calendar -> runner inline preview -> full horse
  profile. It keeps context and displays the collected source/time. No recurring
  horse shortcut or follow list exists. Form preview is merely the five newest
  stored entries, not a pre-race comparison across all runners.
- Local UI initially inspected at 958x898. Earlier desktop/mobile evidence is in
  docs; new changed journeys still require new verification.
- Coverage/freshness is currently scattered counts and a queue badge, with no
  explorable coverage/status view. New users cannot tell which dates are queued,
  collected empty, partially collected or stopped from one understandable place.
- Horse profile: collected-start table and three counters; future entries are not
  separated into an upcoming section. Inspect with synthetic mixed dates before
  deciding the exact presentation and statistics contract.
- Other areas (empty archive, recovery after collector failures, repeated saved
  use, richer runner comparison, final release) need current-pass evidence.

## Discovery pass 1 / candidate backlog

1. Trust and useful runner comparison: show pre-race recent collected form and
   relevant source fields without clicking every horse. Exclude future/current
   race from retrospective form. Distinguish trial/pony results and missingness.
   High potential value, moderate work; inspect actual available fields first.
2. Return to important horses: locally saved horses plus a complete list/upcoming
   starts journey. Strong observed missing action; value is still a user hypothesis.
   Prefer browser-local preferences to new accounts or write access to the archive.
3. Understand archive status: coherent coverage, partial/stale/error states and
   source times. High confidence given ongoing crawl and incomplete snapshots.
4. Calendar orientation/density and mobile evidence priority: inspect current
   populated layouts before choosing structural changes; preserve working controls.
5. Weather, odds and predictions remain outside the first wave: unverified external
   contracts/data coverage make them less valuable than trustworthy browsing.

Research in progress: ATG official help on compact/customizable fields and start
watching; Svensk Galopp official guide on calendar, horse shortcuts and watches;
Racing Post first-party guide on contextual runner form. Record sources and exact
adopted/rejected patterns in docs/product-research.md before implementation.

## Ongoing collection (separate from tests)

Worker session 66672: 64-request maximum, 30-second spacing, 200 daily ceiling.
Daily heartbeat grow-hippos-archive-slowly at 10:00 local; see docs/backfill.md.
Do not start a second worker, clear provider stops, change budgets or use real
records as test fixtures. Keep synthetic DBs separate and localhost-bound. The
live archive may be read for product inspection. Reconcile completion during this
goal and update the operational checkpoint. Any limit ends provider access.

## Next action

Finish focused research/skill reading, inspect mixed upcoming/history and status
journeys using synthetic fixtures, record the chosen first batch's criteria, then
implement/test it. Continue discovery after each verified batch. Final self-review,
normal commit/push and local smoke verification follow only after the stopping
assessment; report the absent hosted deployment workflow honestly.

## Batch 1 checkpoint

Implemented pre-race five-start comparison (strictly before selected date, only
visible membership), result-aware times, and upcoming/history separation. Red to
green: server form test; frontend date/result split test. 14 server tests and 14
JS tests passed. Synthetic desktop journey verified: inline preview -> full horse,
7 past records counted separately from 2 upcoming; zero times shown as missing.
Profile type labels and mobile review remain in this wave. Synthetic fixture
script now provides a reproducible, isolated mixed archive (24 horses, 9 meetings).

## Batch 2 decision / acceptance

Saved horses complete the recurring visit: save from profile, discover a dedicated
list from main navigation, see upcoming collected entries, open race/profile,
remove and reload. Store up to 100 string IDs only in this browser; do not write
SQLite or contact upstream. Use one bounded local read endpoint. Empty, missing
horse, storage unavailable/corrupt, cap, and API failure must be understandable.
Test persistence through a storage boundary double plus real browser reload.
This addresses the observed repeated-search gap and ATG's documented saved-horse
pattern; improved usefulness is a hypothesis pending the user's father trying it.

## Batches 2–3 and rediscovery checkpoint (21:53 Helsinki)

- Saved-horse endpoint + browser-local IDs implemented. Verified save, reload,
  upcoming entries, race click, return, remove and empty list in Chrome. Storage
  corruption, quota failure and 100-item cap are tested through the real module's
  storage boundary; browser settings were not modified to manufacture failure.
- Coverage read is paged at 30 dates. Tests distinguish pending, empty calendars,
  partial and complete fields; browser verified all four and date-to-calendar
  navigation. No claim of a continuously covered min/max date interval.
- Rediscovery found a real multi-line inline-link hit-target gap: clicking the
  apparent center focused the table instead of the race. Inline-block fixed it;
  mouse click and keyboard Enter now reach the race and return to saved horses.
- Four navigation destinations initially overflowed mobile. Two-column navigation
  now fits at 390 and 320px. Saved/profile documents have no horizontal overflow.
- Upcoming tables originally showed blank result columns and required mobile
  horizontal scrolling. They now show date plus race/driver context, including
  cancellations first; measured table/content both 271px at a 320px viewport.
  Past-result tables preserve all result fields and their independent scroll.
- Trial labels, full date titles/year when crossing years, and missing-result
  times prevent misleading comparisons. No scores/probabilities invented.
- Final combined unit milestone: 47 Python + 15 JS tests passed; ES-module syntax
  check passed. Remaining: final error/empty/live smoke, detector, source review,
  docs, release payload review, commit/push and local revision verification.
- Existing 100,000-horse/1,000-meeting fixture, three reads each including JSON:
  coverage first 3.36ms / last 1.90ms, race+form 0.34ms, saved100 3.41ms median.
  Most horses in that fixture have one start; mixed repeated history is separately
  tested in demo v3 and the server regression. These are local measurements.
- Live collector stopped at request193 on transient transport failure: 56 success
  responses in this batch, then status0. No retry this wake-up. Final 15 meetings,
  171 races, 1,722 entries, 1,502 horses, 191 snapshots, 25 pending. Integrity ok,
  zero FK violations; min spacing 30.00010s. Details in docs/backfill.md.

Review skill: code-review's standards/spec axes applied sequentially by the main
agent against starting SHA plus the saved baseline, not claimed independent.
User's explicit single-agent/decision delegation overrides its parallel-agent,
fixed-point question and issue-tracker setup prescriptions. Spec is the attached
brief plus established product/crawl requirements; no issue tracker is needed.
Impeccable critique likewise uses sequential self-review, with no fictitious
second opinion or user approval. Routine design questions delegated by the brief.

## Final discovery / release preparation

See docs/product-improvements-2026-10-22.md for the complete coverage matrix,
source rationale, standards/spec review and stopping assessment. Final source
checks at 21:56: 47 Python tests + 15 JS tests + module syntax all passed.
33 candidate text files scanned for credential signatures and invalid replacement
characters; no findings. This is a targeted scan, not a secret-audit guarantee.
Final real archive sort survived reload; 11 runners rendered; no application
console errors. Empty archive/server-loss/retry and scratch/cancellation cases
were exercised after the latest product wave. No further release-blocking product
failure was observed in these flows. Remaining limitations are explicit in docs.

Detector: one run, exit1 with two warnings for the same existing Inter stack.
Retained deliberately for continuity/readability; not reported as a clean pass.

Release prerequisites rechecked: remote main remains initial SHA, zero Actions
workflows and zero GitHub deployments. Hosted deployment remains unavailable.
Do not invent hosting. The source release includes the pre-existing untracked
application from the preceding turns because it is a necessary foundation for a
runnable revision; it is not represented as newly authored in this improvement
wave. No unrelated files, live/synthetic databases, screenshots or diagnostics
are included. The baseline copy remains ignored and intact.

Next: stage this complete application/doc/test payload, inspect staged paths and
whitespace, commit and normal-push main, verify remote SHA and local committed
runtime, then record exact release results. No more provider requests this turn.

## Source release and final local verification

Application commit 55854832cc9551256b798355bfc20cab9eb9cf35 was pushed normally to
origin/main. An isolated git-archive export passed 47 Python and 15 JS tests.
The post-push live view exposed one new semantic case: a collected empty race
list displayed the collected-field label with 0/0. Fixed in
**d0ac02c059da94c6dbe29a4bf79cc7c34148408d**, pushed normally to main, with a new
red/green coverage-state regression. Final JS count **16 passed**; Python source
unchanged since its 47-test pass. Syntax/whitespace checks passed.

Local runtime restarted from the clean source at http://127.0.0.1:8765 (session
56323). Served assets compared byte-for-byte with source; overview, coverage and
saved endpoints HTTP200. Chrome real-data reload verified 29 October's explicit
empty-race-list state. Live coverage screenshot data/product-live-coverage.jpg.
Test tabs closed and viewport reset; synthetic servers are shut down during
cleanup. The app's live tab is kept open. No collector is running; no retry after
request193's transient failure. All data and screenshots remain ignored.

Remote application SHA verified after push. GitHub: zero workflows, no CI runs,
zero deployments. No hosted deployment was attempted; no established workflow
or hosting target exists. This missing prerequisite prevents claiming the full
hosted-release outcome. No approval was denied and no credentials were changed.
First goal-turn blocking observation only; do not misuse the goal tool's blocked
status before its three-consecutive-turn rule. Independent authorized work is
complete. If resumed, inspect this record and current remote/state rather than
restarting research or generating unrelated improvements to fill time.

Final standards/spec and stopping assessment: docs/product-improvements-2026-10-22.md.
Further form fields need racer feedback; fresh-upcoming collection needs a budget
tradeoff; prediction/odds/weather need separate evidence/contracts. No unresolved
material product defect is known from tested journeys. Hosted release remains the
explicit unfulfilled prerequisite, not a successful deployment or a silent skip.


## Final scope confirmation — 22 October 2026

The user answered the release clarification: **Finish as a local-only project**.
This supersedes the earlier deployment-blocker notes. No hosting is required and
no hosting/infrastructure changes are authorized or needed for this completion.

Revalidated the clean source revision 74eff3d6488261f842358c8dc51a1b04baea0213
before this documentation-only update. The running localhost app's static assets
match source byte-for-byte. Overview returned HTTP 200: 15 meetings, 1,502 horses,
25 pending jobs. No provider requests or collector restart were made. Application
code is unchanged from the verified 47 Python / 16 JS test release, so a redundant
test run is unnecessary. The completed product/research, UI journeys, tests,
source release and stopping assessment remain in the product improvement record.

Commit and push this final scope documentation, verify the remote revision and
clean tree, then mark the goal complete. The daily bounded collection policy
remains separate ongoing operation; completing this improvement program does not
claim the entire provider archive has been crawled.
