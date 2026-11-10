# CatBoost win probabilities

Implemented and locally verified 10 November 2026. Experimental probabilities are
visible in the racecard's sortable **Voitto %** column beside the horse name.
Expand **Mallin tulokset** for evaluation and timing. Scratches have no probability.
Unsupported races, missing forecasts, changed fields and stale inputs are explicit.
Historical test predictions are labelled **Historiallinen testi**, never presented
as forecasts saved before the race. Neither training nor prediction contacts a provider.

## Current model: monté and sulky — 10 November 2026

Active artifact: `data/models/20261110T151025Z-c251a9a4`, feature version **3**.
The earlier checkpoints below remain historical. Warmblood/coldblood TOTO monté
and sulky races are now supported; pony, trial, unknown-discipline and ambiguous
result fields remain excluded. No collection endpoints or budgets changed.

One pooled CatBoost model uses discipline as a categorical feature, general horse
form plus discipline-specific horse form, rider/driver and trainer history.
Comparable times use only the same discipline, breed, start method and distance
band. All histories still exclude the target date and future dates. Scratches
receive no probability, and known disqualified starters remain non-winners.

| Block | Sulky races | Monté races |
| --- | ---: | ---: |
| Train, through 26 August | 990 | 47 |
| Tune, 27 August–23 September | 239 | 11 |
| Calibrate, 24 September–11 October | 162 | 6 |
| Test, 12 October–9 November | 232 | 7 |

Monté top picks won **3/7** tests (42.9%); log loss 2.2358 versus 2.3036 for recent
form and 1.8843 for final market odds. Seven races are insufficient for a reliable
accuracy estimate. The paired monté log-loss difference versus form has a 95%
meeting-bootstrap interval of approximately [-0.485, 0.414], crossing zero.
Sulky top picks won 58/232 (25.0%). Different archive cohorts and repeated model
development mean these are experimental retrospective results, not a fresh
independent validation or proof of improvement. Final odds are benchmarks only.

The report records counts and comparisons by discipline. The racecard now shows
only the sortable win probabilities; model explanations and evaluation details
are kept off the calendar. The **Ennusteet** page retains evaluation metrics.
Old prediction records remain immutable. Jokimaa 9 November race 1 has nine
non-scratched historical probabilities summing to one. Live HTTP checks also
verified upcoming monté forecasts for Vermo 11 November race 4 and Teivo
15 November race 3. The restarted watcher initially generated 62 eligible forecasts.

The collector remains running. Its new observations automatically update forecast
features through `predict --watch`; they do **not** retrain the fixed model.
To learn new weights, run `train` again, inspect the chronological and discipline
reports, then restart the watcher with the resulting artifact. More data may help,
but improvement is not guaranteed. No automatic retraining or startup service was
added. Current model path: `data/prediction-current-model.txt`.

Verification: **163 Python and 36 JavaScript tests passed**, plus JavaScript syntax
checking and live HTTP/browser checks of probabilities, scratches, monté-specific
evaluation and historical labels. The browser reported no console errors.
The local server runs on port 8766 (PID 49420); forecast launcher PID 31652.

```powershell
.\.venv\Scripts\python.exe -m hippos_analyst.predictions predict --model data/models/20261110T151025Z-c251a9a4 --watch
```

This watcher is already running; do not start a duplicate. Collector PID 56060
was left uninterrupted. The race-field parser repair continues separately.

## Model and first evaluation

Version: `20261110T140810Z-d011870b`, CatBoost 1.2.10, CPU QuerySoftMax grouped by
race. Four CPU threads, seed 42, depth four, learning rate 0.04, up to 400 trees;
early stopping on the tuning block retained 182 trees. A separate calibration
block selected temperature 0.8 from a fixed grid. Scores become within-field
softmax probabilities; calibration remains imperfect, especially in sparse bins.

| Block | Dates | Races | Runner rows |
| --- | --- | ---: | ---: |
| Training | 22 Oct 2025–27 Aug 2026 | 970 | 10,057 |
| Early stopping | 28 Aug–23 Sep 2026 | 231 | 2,464 |
| Calibration | 24 Sep–11 Oct 2026 | 155 | 1,715 |
| Untouched final test | 12 Oct–9 Nov 2026 | 208 | 2,190 |

The first block includes the isolated October 2025 sample; the intervening
uncollected dates are not treated as observed races. All blocks split on dates,
so runners and meetings cannot straddle a split. Earlier results within test dates
may supply history for later dates, as in sequential forecasting, without refitting.

| Predictor | Winner log loss (lower is better) | Race Brier score | Top-pick win rate |
| --- | ---: | ---: | ---: |
| CatBoost | 2.0186 | 0.8361 | 24.0% (50/208) |
| Last-five-start win-rate baseline | 2.2072 | 0.8727 | 21.3% |
| Equal chance per starter | 2.3350 | 0.9012 | 9.9% |
| Normalized reciprocal final odds | 1.6627 | 0.7284 | 43.3% (90/208) |

Tied top predictions receive fractional credit. All 208 test fields had complete
positive odds, so the market comparison uses the same cohort. Final odds are a
retrospective benchmark, not an available-at-cutoff model feature. CatBoost beats
the two simple baselines, but does not beat the market. The paired meeting-block
bootstrap interval (500 resamples, seed 42) for CatBoost minus form log loss is
[-0.276, -0.104]. It measures sampling variation, not missing-data or hindsight bias.
The artifact report also includes breed segments and probability calibration bins.

The full retained-field audit contained 1,564 eligible races, 1,264 unsupported
types, 205 fields with unknown placing codes, five without a unique winner, and
70 unsettled fields. These counts are from the frozen training backup, not live
coverage. Exclusion of ambiguous results can bias this sample; predictions must
also be assessed prospectively before claiming dependable performance.

## Features and boundaries

- 22 inputs: track, breed, start method, distance, lane, distance handicap, field
  size; observed prior start counts, last-five form, days since last start,
  smoothed career/recent win rates, relative finishing position and gallop rate;
  recent comparable kilometre time and its sample count; driver/trainer recent
  smoothed rates and counts; form and time relative to this field.
- Track/breed/start method are categorical. Horse and person IDs only join history;
  no raw identity is a predictor. Rates use fixed weak priors (1/10 for horses,
  2/20 for people); people rates use at most 100 earlier eligible starts.
- Features are computed before incorporating any result on the same date.
  Current-race results, prize, gallop, odds, lifetime totals, equipment and profile
  attributes never enter the feature vector. Odds appear only in evaluation.
- Only ordinary warmblood/coldblood TOTO races, no monte, and known group/handicap
  start modes. Training requires status `2`, one winner, at least two starters,
  unique horse IDs and placings in 0..field size. No 100-series code interpretation.
- Times accept the verified `1.17.8` form (77.8 seconds/km). Comparable history
  uses the same breed/start method within 200 metres, among the last ten eligible
  starts. This is a coarse adjustment, not a complete track-condition speed figure.
- Read latest successful calendar/race/field snapshots, excluding removed/cancelled
  meetings. Missing history is explicit; archive history is not a complete career.
- Historical evaluation uses backfilled, latest observed facts. It is event-time
  reconstruction, not proof of the exact information available on the original day.
  No linear baseline or full rolling-origin model comparison was added in v1;
  those and more sophisticated speed adjustments remain possible later experiments.

## Reproduce and operate

The web server and collector still require only standard-library Python. Optional
training dependencies live in `.venv`; see `requirements-ml.txt` (CatBoost pinned)
and `requirements-ml-lock.txt` (the verified environment's transitive versions).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ml-lock.txt
.\.venv\Scripts\python.exe -m hippos_analyst.predictions train
.\.venv\Scripts\python.exe -m hippos_analyst.predictions predict --model data/models/20261110T140810Z-d011870b
.\.venv\Scripts\python.exe -m hippos_analyst.predictions predict --model data/models/20261110T140810Z-d011870b --watch
```

`train` creates a new immutable model directory, a consistent SQLite backup,
native `model.cbm`, and `report.json`. It saves predictions only for the held-out
test block and eligible upcoming races. It does not publish in-sample training
predictions. Keep the full directory to reproduce the experiment. Later training
runs must not be used to repeatedly optimize against this same final test block.

The separate `data/hippos.predictions.sqlite3` holds model reports and append-only
prediction versions. Records include model ID, source request watermark, field
request ID, input field signature, creation time, scheduled start and per-runner
probability/history count. Repeating the same model/field/source version is a
no-op. A later backtest cannot replace an existing prospective forecast in the UI.
The API reads this database without importing CatBoost and hides a prediction when
the field signature differs (including scratches, identities, drivers or schedule).

`predict --watch` checks the local request watermark once per minute and recalculates
on changes. It does not retrain the model, poll upstream or install a scheduler.
It was started windowless as PID 45696; launcher PID is in `data/predictions.pid`.
Logs: `data/predictions.stdout.log` and `data/predictions.stderr.log`. Verify process
identity before stopping it; this process is separate from the Hippos collector.
After reboot/sign-out it requires a manual restart, like the other local processes.
Use the desired new artifact path when deliberately switching to a newly trained model.

Prospective forecasts require an unsettled supported field observed within 24 hours,
no results, a date later than model calibration, and at least five minutes before
the scheduled start. The cutoff is rechecked after inference. No actual-off feed
is available. Existing pre-race forecasts remain viewable after the race; changed
fields hide old versions. The results page scores that accumulating cohort against
completed results when opened. It does not reconcile actual off times.

## Completed-race results

Open **Ennusteet** (`#/predictions`). The date-filtered, paginated page shows each
race's top pick, win probability, implied decimal odds (`1 / probability`), actual
winner, the winner's predicted rank, and hit/miss. Race and horse links retain the
results filters and page. Summary metrics cover the entire selected range, not
just the visible 30 rows. Historical reconstruction and forecasts saved before
the race are separate modes; the API never mixes them.

The latest model's saved versions are scored through
`GET /api/predictions/results?from=YYYY-MM-DD&to=YYYY-MM-DD&mode=backtest&offset=0`.
The latest version per race counts once. Changed field signatures, mismatched
identities, invalid probabilities, incomplete/unsupported results and absent
predictions are counted as exclusions. Forecast scoring also verifies creation
before the five-minute scheduled-start cutoff and observation before creation.
All three learned stages (training, tuning, calibration) must end **before** the
target date. Same-day and later outcomes never supply target features.

To calculate additional completed fields with the frozen model, without retraining:

```powershell
.\.venv\Scripts\python.exe -m hippos_analyst.predictions backtest --model data/models/20261110T140810Z-d011870b --from 2026-10-12 --to 2026-11-09
```

The command rejects any range starting on/before the latest fitting cutoff before
reading the archive or loading the model. It scores supported, completed races
whose scheduled start has passed, saves immutable backtest versions and prints
baseline metrics. It makes no network requests. Backtests are explicit runs;
the forecast watcher does not recompute historical backtests. The original frozen
training report is preserved, so its 208-race benchmark differs from a growing
archive evaluation. Reading the results page does not train or infer a model.

Verified 10 November against the enlarged archive with the unchanged model:

| Range | Evaluated races | Model top-pick wins | Final-odds favourite wins |
| --- | ---: | ---: | ---: |
| 12 Oct–9 Nov 2026 | 219 | 53 / 219 (24.2%) | 93 / 219 (42.5%) |
| 3–9 Nov 2026 | 40 | 11 / 40 (27.5%) | 15 / 40 (37.5%) |

For all 219 fields, CatBoost log loss was 2.0171 and race Brier score 0.8354;
final-odds log loss was 1.6639. All had complete odds, so both comparisons use
identical fields. The broader range also excluded 91 unsupported fields, 30
unknown placing-code fields and 26 unsettled fields. The model still trails the
market. These historical predictions use backfilled facts and are not evidence
of forecasts made before those races. Implied model odds are not offered payouts.

Results-page verification: 153 Python tests and 32 JavaScript tests passed.
Added checks cover all fitting cutoffs, removal of target/future outcomes,
probabilities/odds/ranks, fractional tie credit, invalid fields, forecast timing,
one version per race, aggregation before pagination, mode/date separation, invalid
API filters, and return navigation. Desktop and 390x844 browser checks verified
filters, pagination, race drill-down/back, prospective empty state and natural
vertical scrolling. Fixed multi-line race link hit areas during that verification.
The live results read model took about 0.35 seconds on the checked archive.

## Verification

### Result-code and monté investigation — 10 November 2026

**Follow-up:** the [result-parser repair](result-parsing.md) is now implemented,
with live confirmation of `hlo`/`106` and `hpl`/zero in Jokimaa race 2. The original
investigation below is a historical checkpoint. The current feature-version-2
artifact is `data/models/20261110T145450Z-d6e5c544`; its restarted watcher produced
60 eligible forecasts at verification. Known disqualified starters remain in
the field as non-winners; unknown codes still block scoring. The full legacy-field
refetch remains in progress. Monté eligibility is unchanged. See the repair
document for current evaluation counts, provenance and verification.

Lahti/Jokimaa 9 November, race 2 is a completed ordinary TOTO race. Gold Star
Mint has placing `1`; Blackriver Get On has placing `106`, gallop `true`, time
`1.23.5` and prize `0`. The current `result_reason` rejects the entire field as
`unknown_placing`. The importer does not retain `disqualifiedCode`, although the
official mobile frontend uses it alongside `placing`. Raw `106` in our UI and
the generic missing-prediction message are consequently misleading.

The previously downloaded official mobile bundle
`data/hippos-person-research-bundle.js` (SHA-256
`f0657991e8a6040c62697cd9d8cc3ded8698a557052ce2d6dc1ad6937406e260`)
contains `getPlacingValue(disqualifiedCode, placing, absent, simple)`. For `hlo`
it displays that prefix followed by `placing - 100`, so the pair `hlo` / `106`
renders `hlo6`. Other supplied disqualification codes are rendered as codes;
absence is separate. Therefore 106 alone is not a complete reason code and must
not be interpreted as an ordinary sixth place or automatically mapped to `hlo`.

[Hippos's official disqualification guide](https://www.hippos.fi/raviurheilu/ravikilpailusaannot/juoksun-hylkaamisen-syyt/)
defines `hlo` as galloping in the final 100 metres; when position was not improved,
the would-have-been placing and time are recorded. This supports an `hlo6`
interpretation, but the exact companion value for Blackriver Get On remains
unverified because the archive omitted it. No extra provider request was made
alongside the active collector; its shared lock was occupied and its stop state
was healthy. Do not claim a raw-response confirmation from this investigation.

Recommended correction (not implemented in this investigation): retain and
validate the companion result code, display disqualifications distinctly from
official finishing places, and model verified disqualified starters as non-winners
without discarding an otherwise valid single-winner field. Do not drop those
starters from the probability field or convert 106 to a normal sixth. Recover
missing codes through bounded refreshes with the shared ledger/lock. Rebuild
features and retrain a new version before claiming changed performance, since
historical result semantics and eligible cohorts will change. Unknown codes
should still fail closed. In the checked archive, 211 completed supported fields
were excluded for unknown placing codes, including 30 after the model cutoff.

Monté support is feasible but not validated by the current model. The archive
contained 77 completed warmblood/coldblood monté TOTO races (797 listed runner
rows), dated 14 May–9 November 2026: 70 warmblood and seven coldblood. Temporarily
evaluating only eligibility with the monté flag ignored yielded 71 otherwise
valid fields, including only seven after 11 October. No predictions or data were
changed by this count. A separate monté-only model would have little evaluation
evidence. Prefer testing a new pooled model with discipline as an explicit feature,
discipline-specific horse/rider form and comparable times, and separately reported
chronological monté metrics. Do not simply remove the existing monté guard: the
current model was fitted only on sulky races and cannot claim validated monté
probabilities. Continue collecting monté history before stronger conclusions.

146 Python tests passed in the ML environment, including real grouped CatBoost
training/save/load/prediction. 31 JavaScript tests passed. Tests exercise no current
outcome/odds leakage, same-day exclusion, chronological grouping, unsupported
results, probability arithmetic, missing history, pre-start/staleness rules,
immutable storage, changed-field invalidation, source membership and snapshot
isolation. A discovered SQLite backup-reader handle leak was fixed before passing.

Live HTTP checks verified forecast, historical-test and unsupported race responses;
all tested fields summed to one. The sidecar passed SQLite integrity_check and
contained no forecast created inside the five-minute cutoff. Browser checks at
desktop and 390x844 verified the column, probability sorting, scratches, historical
labels and natural page scrolling. The existing wide table scrolls horizontally.
The local UI remains at http://127.0.0.1:8766; no deployment or Toto polling changed.

See [original plan](prediction-plan.md) and [historical odds evidence](toto-history-research.md).
