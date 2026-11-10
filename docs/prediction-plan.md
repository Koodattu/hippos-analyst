# Win probability experiment

Proposed 10 November 2026. The [first implemented experiment and verification](predictions.md)
now records what shipped; this document retains the broader original design.

## Evidence and first scope

Read-only inspection found about 30,000 runner entries, 5,578 horse identities,
347 profiles and three Toto observations. A coarse query found 2,111 TOTO races
with exactly one non-absent runner recorded in first place. This is a candidate
count, not a validated training-set size: reconcile current source membership,
complete fields, result status and special codes before admitting races.
Stored entries span May–November 2026 plus an isolated October 2025 sample;
coverage and outcomes are incomplete. Profiles are much sparser than race data.
Across all race types, 4,944 of 28,420 non-absent entries had no earlier recorded
non-absent start; 15,836 had at least three. These are archive-history counts,
not proof of a horse's actual debut or complete career.

Follow-up [odds investigation](toto-history-research.md): 2,110 of these 2,111
candidate fields already contain positive Hippos win odds for every non-absent
runner. These support a retrospective market benchmark after validation; the
three direct Toto observations are not the extent of stored historical odds.
They still do not establish odds available at an earlier prediction cutoff.

Start with ordinary TOTO harness races, excluding qualification, teaching,
pony and monte races until separately validated. Include breed as a feature
and report performance separately by breed. Exclude cancelled, unresolved,
ambiguous and dead-heat races from the first experiment; report exclusion counts.
Unknown result codes must not silently become losses or numerical placings.

## Data and features

One row represents one runner in one race; race identity groups competing rows.
Target: winner=1, other confirmed starters=0. A horse ID is an identity key,
not a global class label. Generate field-relative features as well as absolute ones.

First features: strictly earlier 3/5-start form, comparable kilometre times,
time since last observed start, prior gallop frequency, distance, lane/handicap,
start method, field size, breed, track, and historical driver/trainer rates.
Shrink small-sample rates toward a training-only population prior and retain
history counts and missingness. Compare times within suitable breed, distance,
start-method and track contexts; do not equate raw times across race conditions.
Exclude the race being predicted from every aggregate. Use earlier dates only
until within-day event ordering and result availability are reliable.

Current-race placing, time, prize, gallop and final odds are targets or post-race
facts, never input features. Current lifetime totals, records, owners, trainer
assignments and equipment must not be assumed to describe historical knowledge.
Keep opaque source fields out until their meanings and availability are verified.
Defer owners, breeders, pedigree and weather until coverage and validation justify
them. Age/sex may be added where verified; missing profiles remain explicit.

Historical backfill supports a retrospective experiment using earlier-event
statistics, but cannot establish what was known before each historical race.
Label that experiment accordingly. A separate prospective evaluation must use
only successful observations available by the prediction cutoff, preserve input
snapshot/request IDs, and record predictions before the scheduled race start.
Reject stale, missing or post-start fields rather than inventing a pre-race forecast.

## Models and tools

Keep Python, SQLite and the existing web application. Proposed optional research
dependencies: pandas/NumPy for feature tables, scikit-learn for a regularized
linear baseline and evaluation, CatBoost for a nonlinear tabular challenger.
Use a separate environment and pinned versions; no packages installed by this plan.
CPU training is sufficient for an initial experiment of this size; no cloud or GPU
requirement. Training reads a consistent SQLite backup and writes versioned local
artifacts. Prediction work must not hold collector write transactions.

Compare uniform 1/N probabilities and a simple recent-form baseline first.
Convert a linear baseline's scores to within-race softmax probabilities.
For CatBoost, evaluate a race-grouped QuerySoftMax objective with winner labels.
Convert scores within each field and fit temperature scaling on a separate
chronological calibration window. Sum-to-one is necessary, but does not establish
calibration. Use numeric historical aggregates initially; raw horse/person IDs
are not needed as predictive features.

## Evaluation and operation

Split whole meetings chronologically: older months train, following block tunes
and calibrates, latest completed block is untouched final test. Use rolling
evaluation on earlier blocks; select actual boundaries after coverage checks.
Fit all preprocessing and hyperparameters without the test block. Repeated horses
across dates are expected; random runner splitting would leak race/time information.

Primary metrics: race-averaged winner log loss and multiclass Brier score.
Also report top-pick win rate, calibration, field-size/breed/history segments,
excluded races and uncertainty using meeting-level resampling. A model should
beat simple baselines out of time before replacing them. Final odds can be a
clearly labelled retrospective benchmark; only odds observed before the same
cutoff are a fair deployable comparator. Three direct Toto samples cannot support
a fixed-cutoff pre-race market model or claims of market advantage; the existing
Hippos quotes can support a separately labelled retrospective benchmark.

Freeze versioned model artifacts, training cutoff, feature schema, evaluation
report and calibration parameters. Save each prediction's full field, probabilities,
creation/cutoff times, model ID and input references immutably. Preserve earlier
forecasts after scratches; record a new field version and mark the prior forecast
as superseded. Evaluation needs an explicit scratched-field policy and counts.

First release: offline quality report, baselines and backtest. Second: CatBoost
comparison and prospective shadow predictions. Third: a compact Finnish racecard
probability column with timestamp, history coverage and optional contributing
features (associations, not causal explanations). Keep uncertainty/coverage separate
from estimated win probability. Recompute locally after relevant archive changes;
weekly retraining is a starting proposal, not training on every request. No extra
upstream polling, automatic betting or collector-policy changes are part of this plan.

## References

- [CatBoost grouped objectives, including QuerySoftMax](https://catboost.ai/docs/en/concepts/loss-functions-ranking)
- [scikit-learn probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [scikit-learn leakage and preprocessing guidance](https://scikit-learn.org/stable/common_pitfalls.html)
- [Existing roadmap](roadmap.md), [snapshot architecture](architecture.md), [Toto scope](toto.md)
