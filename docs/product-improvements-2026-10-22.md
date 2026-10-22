# Product improvements — 22 October 2026

Single-agent implementation and sequential self-review. No independent review,
user interview, accessibility certification or prediction-quality claim.

## What changed and why

The [primary-source research](product-research.md) favored runner context and
returning to familiar horses. The existing calendar/field workspace stays intact.

| Journey | Before | Verified outcome |
| --- | --- | --- |
| Compare a field | Open each horse to inspect history | Up to five earlier collected starts beside every runner; dates, source codes, scratches and trial types remain visible |
| Read horse form | Upcoming entries mixed into history and counts | Separate upcoming entries; only history contributes to summary counts; missing results show a dash |
| Return to a horse | Repeat name search | Save from profile, reopen Omat hevoset, see upcoming entries, open race/profile, remove; browser reload preserves IDs |
| Inspect an upcoming start on a phone | Blank result columns and horizontal scrolling | Date plus race/driver information; canceled/scratched status first; no table overflow at 320px |
| Understand collection | Aggregate count and queue badge | Aineiston kattavuus distinguishes not collected, collected empty, partial and collected fields; date links open the calendar |
| Continue after inspecting a race | Race tabs lost saved/profile origin | Return link survives race switches and result sort |

The form is an incomplete local sample, not a career record. It excludes the
selected date entirely; reliable cross-meeting time order is not established.
It is not an as-of backtest: historical corrections may have been fetched later.
First-place counts retain explicit ties and may include trials. No rankings or
probabilities were fabricated. Source codes remain verbatim.

Saved horses store only string IDs, up to 100, under `hippos.saved-horses.v1` in
localStorage. They belong to this browser and origin (host/port), not SQLite,
accounts or notifications. Storage failures do not pretend the change succeeded.
Corrupt stored data is preserved and reported rather than silently overwritten.
Missing archived horses remain removable. Refresh reads current local data only.

Coverage lists queued calendar dates, 30 per page, newest first. Missing dates
between the first and last snapshot are not inferred complete. Collected fields
need not contain final results or current information. A canceled meeting can
still have previously collected entries; cancellation stays visible.

## Verification and evidence

- `python -m unittest discover -s tests -v`: **47 passed**.
- `node --test tests/ui.test.mjs`: **16 passed**.
- `node --check hippos_analyst/web/app.mjs`: passed.
- New behavior followed red/green checks: five earlier visible starts, upcoming
  versus history, missing times, saved-ID persistence/failure/cap, bounded saved
  reads, coverage states and pagination. Existing assertions were retained.
  The unrelated-history fixture now uses different horses, because the same
  horse's earlier history is intentionally relevant to the new form response.
- Chrome desktop at 1440px: full mixed field, inline preview, profile, save,
  reload, saved list, race/return, result sort and removal. Synthetic fixture
  includes long Finnish names, ties, `hll`, scratches, trials and future zeros.
- Chrome 390px and 320px: navigation/profile/saved/coverage fit without document
  overflow. At 320px the compact upcoming table and its content both measure
  271px. Detailed historical/race tables keep independent horizontal scrolling.
- Canceled and scratched upcoming entries checked in the rendered interface.
  Mouse and keyboard race links work after fixing a multi-line inline hit area.
- Empty archive: calendar, coverage, saved list and horse search have useful empty
  states. Stopping a synthetic server exposed the error/retry UI; restarting and
  retrying restored the horse browser. Application-origin console errors were
  absent on successful synthetic flows. The deliberate offline request failed
  as expected; unrelated wallet-extension warnings are not application errors.
- Real archive integrity: `ok`, zero foreign-key violations after the collector
  stopped. Final counts and the transport failure are in [backfill](backfill.md).
- Storage corruption/quota/cap and missing-ID behavior are automated tests; a real
  browser storage quota failure was not manufactured. Safari, Firefox and a
  physical phone were not tested. No screen-reader certification is claimed.

Local ignored screenshots: `data/product-form-desktop.jpg`,
`data/product-profile-desktop.jpg`, `data/product-saved-mobile.jpg` and the final
live preview. They are not published as upstream-data screenshots in Git.

### Read performance

Existing isolated fixture: 1,000 meetings, 10,000 races and 100,000 horses/entries.
Three repetitions per read, complete JSON serialization, no HTTP/network latency:

| Read | Median | JSON bytes |
| --- | ---: | ---: |
| First coverage page (30 dates) | 3.36 ms | 4,011 |
| Last coverage page (10 dates) | 1.90 ms | 1,373 |
| Race plus prior form (10 runners) | 0.34 ms | 8,151 |
| 100 saved horses | 3.41 ms | 66,603 |

These are local observations, not service-level promises. The large fixture has
mostly one start per horse; repeated history is covered by the dedicated server
regression and mixed product fixture. Existing archive-scale checks are described
in [archive growth](archive-growth.md).

## Final discovery and stopping assessment

After the substantial wave, the review revisited mobile saved/profile/race
journeys, cancellation/scratch semantics, empty startup, server-loss recovery,
coverage navigation and the actual growing archive. It found and fixed the
mobile navigation overflow, race-link hit target, blank upcoming columns and
lost origin across race tabs. The final affected flows meet the chosen standard.

Standards review: no unresolved hard violation found in the reviewed changes.
The shared starts-table/read helpers remove demonstrated duplication; SQL values
are parameterized, source text escaped, IDs remain strings, Finnish copy stays
in its locale, and archive access stays read-only. Collector/auth/deployment
behavior was not redesigned. Large template strings follow the existing stack;
a framework or broad architecture rewrite has no demonstrated benefit here.

Spec review: the product, data, verification and durable-documentation work is
implemented. A hosted release is unavailable because there is no established
hosting/deployment workflow; no new infrastructure has been provisioned.

The Impeccable detector ran once on the final UI and exited 1 with two warnings
for the same existing Inter font stack (HTML inference and CSS). This is an
adjudicated style warning, not a clean detector pass. The established readable
system-fallback stack is retained: introducing a new visual identity or font
asset would not improve these tasks. No finding was suppressed. The context
launcher did not recognize `.mjs`; browser evidence governed the review. Design
and code review were sequential self-review, per the user's single-agent rule.

Strongest remaining opportunities:

- **Upcoming-data refresh:** useful, but the active policy deliberately prioritizes
  historical backfill and shares a 200-attempt daily ceiling. A measured refresh
  cadence must trade off that budget and establish correction windows. The UI
  explicitly states snapshots may be stale; this pass does not silently expand
  network activity after the transport stop.
- **More runner detail/customization:** likely useful to an experienced racer,
  but which fields deserve permanent space needs the father's feedback. The
  current desktop field already shows eight useful columns and five prior starts.
  Adding speculative fields would make the mobile comparison harder.
- **Predictions/weather/odds:** potentially interesting, but the archive is small
  and incomplete; provider contracts and leak-free historical evaluation need
  separate work. These are not disguised as working features.
- **Hosted access:** blocked by missing deployment prerequisites and the explicit
  prohibition on provisioning hosting or changing deployment settings. The
  established local server remains the verified runtime.

No further observed feasible product defect warrants another change in this
wave. This is an evidence-based product checkpoint, not a claim that every
possible improvement or all historical collection is complete.

## Reproduce locally

```powershell
python -m hippos_analyst serve
# Open http://127.0.0.1:8765

# Optional isolated demo; choose a new filename (never overwrites an archive):
python scripts/seed_demo.py --db data/demo-new.sqlite3 --today 2026-10-22
python -m hippos_analyst --db data/demo-new.sqlite3 serve --port 8766
```

The demo makes no network calls. Changing the reference date keeps the fixture
useful for future manual checks. See the [work log](../work/goal-improvement/STATE.md)
for source baselines, decisions and release details.

## Release record

- Application commit: `55854832cc9551256b798355bfc20cab9eb9cf35`.
- Follow-up source correction: `d0ac02c059da94c6dbe29a4bf79cc7c34148408d`.
- Both pushed normally to `https://github.com/Koodattu/hippos-analyst.git`, `main`.
- The committed application was exported with `git archive` into an isolated
  folder; all 47 Python and then-15 JS tests passed there. It does not depend on
  omitted untracked files. The follow-up adds the 16th JS regression; all 16 pass.
- Post-push real-data inspection found that Turku's fetched empty race list had
  shown the complete-field label with 0/0 fields. The follow-up gives it its own
  explicit collected-empty-race-list state. Red/green regression and the live
  29 October row verified it. No provider requests were needed.
- Established local runtime restarted at `http://127.0.0.1:8765`. Every served
  static asset matched the clean committed files; overview, coverage and saved
  read endpoints returned HTTP 200. Final Chrome reload showed the corrected
  live coverage state. The local archive remains outside Git.
- GitHub reported zero workflows, no triggered CI runs and zero deployments.
  CI was **not run** and hosted deployment was **not performed**. There is no
  deployment URL or hosted revision to verify. No hosting configuration,
  credentials, account or infrastructure were added to force a release.

The product/source release is verified locally. The broader hosted-release step
is constrained by that missing prerequisite; this is not a claim of successful
hosted deployment. The final documentation checkpoint is a separate commit.
