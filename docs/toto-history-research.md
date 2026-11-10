# Historical Toto odds investigation

Investigated 10 November 2026 before implementing predictions. This pass read
the live archive in a consistent read-only transaction, reviewed the existing
importer and checked Veikkaus's official documentation. No new provider data
requests or seeds were made: the continuous Hippos worker held the shared lock.
The existing historical API verification below happened on 25 October, not today.

## What is already available locally

Candidate completed races were selected by `races.data.startType == TOTO` and
exactly one non-absent runner with placing `1`. This is a screening query, not a
complete result-validity/source-membership audit. Positive odds were checked
with decimal parsing of `entries.data.winOdds`; scratches were excluded.

| Measure | Count |
| --- | ---: |
| Candidate completed TOTO races | 2,111 |
| Non-absent runner entries in those races | 22,091 |
| Entries with positive Hippos winOdds | 22,082 |
| Candidate races with positive odds for every non-absent runner | 2,110 |
| Missing-odds candidate races | 1 |

The missing field is 4 June 2026, TK, race 2: nine non-absent runners without
winOdds. Do not assume Veikkaus can fill it until a matched probe succeeds.
These are stored post-race quotes, not verified pre-race snapshots. Confirm
final status and timing before labelling each quote a final market price.

The saved direct Veikkaus observation for Vermo 22 October 2025 race 1 has eight
positive quotes and one scratched runner without a quote. All eight match the
Hippos odds exactly after dividing Veikkaus integers by 100 (e.g. 357 = 3.57).
The saved pool was FINAL according to the earlier investigation. This establishes
agreement for one race, not universal equivalence across dates or betting pools.

The earlier prediction assessment's reference to three direct Toto observations
understated available historical odds: most candidate completed fields already
have win odds through Hippos. Three observations still do not provide a useful
pre-race odds time series or training dataset at a fixed pre-start cutoff.

## Official endpoint evidence and remaining uncertainty

The [official documentation](https://github.com/veikkaus/sport-games-robot#toto-pelit)
lists discovery by date, today, future and active cards, followed by card races,
race runners/pools, and `/pool/{poolId}/odds`. It also lists card-wide pools.
Our existing importer supports the five date/race/runner/pool/odds families;
card-wide pools would require an explicit importer extension and validation.

The previous pilot successfully retrieved the October 2025 historical FINAL win
pool in October 2026, including losing runners' quotes. Historical final-odds
retrieval is therefore demonstrated, not restricted to upcoming races. There is
no verified date-retention guarantee or coverage result for every archived race.
Some Hippos qualification/teaching and other non-betting races have no matching
Toto win pool; absence is a legitimate outcome, not necessarily a crawler error.

No documented as-of timestamp/history endpoint for old win-odds movements was
found in the reviewed official material. A source `updated` timestamp describes
the returned quote; it does not retrieve its earlier values. The XML examples
describe T-game combinations, not a verified historical win-odds time series.
Treat historical pre-start movements as unavailable through the verified API
until a separate provider feed is established. This is not proof none exists.

The official automated-client header remains `X-ESA-API-Key: ROBOT`. No evidence
shows a personal key unlocks historical depth or a larger daily allowance.
Official guidance advises against polling odds more frequently than once per
minute and limits parallel processes to four; it does not publish a daily quota.
Our 40-Toto/day, 60-second spacing and shared-lock rules are project limits.
The Hippos worker's new 2,000 cap does not raise Toto's caps: `run-toto` still
requires a combined budget at most 200 and cannot run alongside that worker.

## Recommended historical strategy

1. Use locally stored Hippos odds for a retrospective market benchmark, with
   source/timing labels and complete-field checks. Normalize reciprocal decimal
   odds within each field for approximate market probabilities; this is not a
   verified fair-probability estimate or a pre-race executable price.
2. Validate additional date/track samples against direct Veikkaus, including
   the missing TK field, recent completed races and the oldest collected month.
   A small later probe must run through the shared ledger/lock and stop rules.
   Do not launch an independent research HTTP loop alongside collection.
3. Backfill missing or conflicting final quotes first. Store provider IDs,
   field mapping, pool status, source timestamp and retrieval time separately.
   Preserve original Hippos quotes and unresolved mismatches.
4. Expand to a complete direct-provider copy only if that distinct requirement
   justifies the calls. At this checkpoint there are 2,166 stored TOTO races on
   217 meetings and 177 dates strictly before 10 November. With shared discovery,
   the existing endpoint route costs roughly D + C + 3R = 6,892 requests before
   retries/mismatches (date, meeting races, runners, pools, odds). At 40 Toto
   attempts/day that is at least 173 eligible collection days. This is an estimate
   for a redesigned bulk scheduler, not something the three-race pilot implements.
   Card-wide pools may reduce cost but need separate validation.

## Upcoming and race-day observations

Use scheduled snapshots while the pool is open, for example near 60, 15 and five
minutes before scheduled start, followed by a final observation. These timings
are a proposal and may be missed under a tight budget; record actual times and
coverage. The current pilot allows only three samples, checks participants/pools
once, and does not guarantee a final observation, so it needs lifecycle changes.
Reconcile scratches and schedule changes; preserve field versions and avoid
post-start snapshots masquerading as pre-race information. Race-day updates do
not establish an in-running wagering feed: honor pool state and stop live polling
when betting closes, then retrieve settled data under a bounded policy.

Any future expansion should integrate Toto scheduling into the single worker,
reserve a bounded provider budget and protect time-sensitive snapshots from the
historical queue. Do not simply run the present Toto CLI in parallel, raise caps
implicitly, or reset the ledger. Provider objections/refusals/limits and schema
errors still stop collection. No collection policy or executable code changed
in this investigation.

References: [official API](https://github.com/veikkaus/sport-games-robot),
[existing pilot evidence](toto.md), [prediction proposal](prediction-plan.md).
