# Project roadmap

## Intended outcome

A private educational tool that makes Finnish harness-racing information easier
to browse for a racer and their family, with transparent prediction experiments.
Grow toward all available public Finnish racing history in bounded monthly steps.
The earliest available date is not established, and other Heppa data families
still require research. See the [active backfill policy](backfill.md).
No automated betting is planned.

The highest priority is an easy-to-use view of the available information: few
clicks, useful defaults and efficient screen use. See [product direction](product-direction.md).

## 1. Collection foundation (implemented)

Bounded Hippos discovery, SQLite current records, minimized timestamped snapshots,
persistent queue/limits/stops and a local CLI. Validate a sample before expanding.
No broad unattended backfill is part of the initial verification.

## 2. Coverage and quality

Import one month, reconcile missing jobs and validate source counts. Measure size
and request cost before growing to 12 months, then 3–5 years. Add coverage reporting
by date, meeting and race so incomplete data is visible. The first UI already shows
collected-day and field coverage and reconciles omitted meetings/races. Add fuller
coverage reports and units/code parsers with domain tests.

A bounded Veikkaus pilot now matches complete fields and displays timestamped
win-odds observations. Two current and one historical observation are saved;
the historical scratched-runner omission is fixed. See [Toto integration](toto.md).
Historical depth and archival-use terms remain unestablished. Do not silently
mix conflicting results or identify horses by name alone.

## 3. Useful local web UI (first version implemented)

The first version uses a small Python read-only API and vanilla ES modules/CSS,
reading SQLite. This replaces the tentative React/TypeScript proposal and avoids
new dependencies for the local application. User-visible strings use a
Finnish locale structure. See [UI details](ui.md).

Implemented: date/track-filtered calendar, racecards/results, horse-name search,
paginated horses, collected horse history, missing-data states and observation times.
The calendar now includes an adjacent racecard, direct race-number links, compact
navigation and inline horse history, so the normal flow does not require a meeting
page followed by a race page.
Saved horses and their upcoming entries, five-start prior form and collection
coverage are also implemented. Searchable **ohjastajat** and **valmentajat** now
have profiles linked to horses and races, with paginated upcoming/history views.
See [people and relationships](people.md) for identity rules and verification.
Further work:

- Breed and race-type calendar filters.
- Recent-form and horse-history comparisons over a larger dataset.
- Track profiles and explicit stable identities after source contract research.
  Owner/breeder source-name groups and bounded pedigrees are now implemented;
  broader profile coverage continues within the daily request budget. See
  [horse relationships](horse-relationships.md). Historical ownership still needs
  a verified source; current profile labels do not establish it.
- Driver/trainer filters and comparisons by date, track and race type.
- Calendar export and deeper source links.
- Later: race eligibility and entry deadlines once the fields and rules are verified.

Success means a user can find a meeting, inspect a race and review a horse's form
without contacting upstream APIs from the browser. No authentication or deployment
changes are needed for the initial local version.

## 4. Weather context

FMI observations/forecasts, cached by track/time, with attribution and provenance.
Store observation time, forecast issue time and target time separately. Historical
observations are useful for analysis but cannot replace forecasts available at an
earlier prediction cutoff. Weather at a nearby station is not a verified measure
of the racecourse surface condition.

## 5. Prediction experiments

Start with a simple baseline, then compare a more flexible tabular model. Candidate
features: prior kilometre times, start method, distance, lane/handicap, layoff length,
gallop history and past driver/trainer performance. Account for breed and monte.

- Compute features only from events earlier than the prediction cutoff. Current
  career totals, future driver results and post-race equipment/comments can leak labels.
- Start preserving upcoming-field snapshots before building models. Backfilled
  historical responses do not reconstruct exact historical information availability.
- Split chronologically, keep entire races together and leave a final holdout.
- Record predictions before the race with model version, input cutoff and snapshot
  references. A subsequent re-run must not overwrite the original prediction.
- Evaluate calibrated win probabilities with race-level log loss/Brier score and
  calibration, alongside winner accuracy. Handle scratches, dead heats and invalid
  results explicitly; probabilities should refer to the actual prediction-time field.
- Compare against simple baselines and, if available, odds captured at the same
  prediction cutoff. Do not use final odds as if known earlier.

The goal is a measurable experiment. No profitability or predictive advantage is
assumed. Expand complexity only when it improves out-of-time evaluation.
