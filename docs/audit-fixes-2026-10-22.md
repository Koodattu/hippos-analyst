# Audit fixes and verification — 22 October 2026

All eight findings in the [original audit](audit-2026-10-22.md) are resolved.
The work was completed by one agent without delegation. No dependencies were
added and no collection run was started. The local UI was restarted to use the
corrected implementation.

## Resolution evidence

| Finding | Change | Verification |
| --- | --- | --- |
| A1: service cooldown | Persist transient backoff/Retry-After in the existing service control record and check before selecting/reserving any request | Two pending paths, seconds and HTTP-date headers, reopened SQLite, and a second run before expiry send no request; requests resume at expiry. Transport backoff, manual pause, 429, and the five-failure circuit also pass |
| A2: whole-archive reads | Filter meetings in SQL; index successful request lookups; count overview membership without runner fields; remove the unused whole-archive property | Scoped-read query work stays bounded with unrelated history; existing v1 archives receive the index; membership removal/restoration tests pass; comparable benchmark below returns identical data |
| A3: scalar schema drift | Require boolean scratch flags, validate supplied behavioral booleans, reject boolean/fractional/empty participant identities | Malformed refresh pauses without changing the prior field or adding a successful snapshot; valid ties and codes remain intact; all 135 existing snapshots normalize unchanged |
| A4: lost track focus | Restore focus to the track select when it still owns focus as the replacement view arrives | Chrome ArrowDown changes All → H → M without refocusing the control; SELECT remains focused even when the filtered range is empty |
| A5: empty-week dead end | Render calendar navigation independently of whether meetings exist | Filtered empty ranges retain both arrows; at 320 pixels, 4–11 November → 11–18 November → 4–11 November works without overflow; track preservation checked |
| A6: text contrast | Darken the shared muted token to `#59695f` | Computed contrast: 5.358:1 on page background, 5.515:1 on selected meeting surface, 5.816:1 on white, 5.596:1 on footer surface |
| A7: lost sort order | Store selected race/order in the URL, restore it when rendering, and carry order through race navigation | Forssa race 1 stays sorted by placing after local refresh and hard reload; program 6 stays first. Standalone and mobile race links retain result order |
| A8: lost horse-search context | Carry a validated internal return route in profile links | Search `an`, page 2: opening Coruscate Comanche, reloading its profile, and using the visible return link restores `q=an&offset=30`, the same first horse, and rows 31–60/193. Calendar/race return links and direct-link fallback are covered |

Behavioral booleans are `absent`, `canceled`, `hasPublishedResults`, `monte`,
`finnishTrack`, `totoResultsReady`, `publishFree`, `isFreeToPublish`, and `gallop`.
`absent` is mandatory for runners. Other flags may be omitted; supplied null,
string, or numeric values are incompatible and trigger the existing schema stop.
Equipment and result-code strings are not coerced into booleans.

Result order is view state, not a new user preference database. Sorting replaces
the current URL state without creating a history entry for every dropdown change.
Expanded previews still close when their table is refreshed or reordered.
Return destinations are restricted to internal horse-search, calendar, and race
routes; missing or incompatible destinations fall back to horse browsing.

## Automated verification

```powershell
python -m unittest discover -s tests -v
node --test tests/ui.test.mjs
node --check hippos_analyst/web/app.mjs
```

- **43 Python tests passed** on Python 3.11.9.
- **12 JavaScript tests passed** on Node v24.4.1.
- ES-module syntax check passed.
- New backend regression cases reproduced failures before the fixes and pass
  afterward. Existing assertions were preserved; the removal-visibility check now
  uses the calendar API instead of the removed internal whole-archive property.
- Frontend model tests cover order/URL round trips, Finnish query/page return,
  internal calendar/race origins, and rejection of external return destinations.
  Actual DOM focus, empty-state controls, and rendering were verified in Chrome.
- SQLite integrity and foreign-key checks pass. All 135 existing minimized
  snapshots pass the stricter validator unchanged. The upstream request ledger
  remains at 135; data is still 11 meetings, 120 races, 1,195 entries, 1,126 horses,
  and 19 queued jobs. Only the additive lookup index was applied to the live DB.

## Performance verification

Compared the saved pre-fix implementation with the corrected implementation on
identical disposable data: 1,000 meetings, 10,000 races, 100,000 entries, and
12,003 observations. The fixture includes repeated calendar observation,
removal, and restoration. The original database has its original indexes; the
corrected database includes the new successful-path index.

Each operation creates a fresh Archive and completes its entire read-model result.
Three measurements per implementation alternate execution order. SQL tracing is
disabled during timing and used separately to count statements. Result structures
are equal for every before/after pair; only the overview's generated `now` clock
is excluded from equality. No live racing database or external requests are used.

| Read | Queries before → after | Median seconds before → after | Before range | After range |
| --- | ---: | ---: | ---: | ---: |
| One-day calendar | 13,002 → 15 | 2.222431 → 0.001525 | 2.216000–2.269947 | 0.000891–0.002521 |
| One race | 13,002 → 15 | 2.237514 → 0.000338 | 2.160210–2.245775 | 0.000218–0.000469 |
| Overview | 13,007 → 2,007 | 2.297195 → 0.033129 | 2.240865–2.336885 | 0.031907–0.037988 |

These are local read-model timings, excluding HTTP serialization and browser
rendering. They establish the scoped-read improvement on this workload, not a
general capacity or end-to-end latency guarantee. Overview still examines meeting
and race-list membership; explicitly requesting the full archive still expands
the requested range. Horse-name search and all-archive rendering are separate
future scaling considerations.

The local reproducible harness is `data/verify_read_performance.py`; results are
in `data/audit-fix-performance.json`. Its baseline code is preserved in ignored
`data/audit-fix-baseline/`. These local diagnostic artifacts are not application
dependencies or downloaded datasets.

## Browser scope and remaining limits

Checks used the real local archive in Chrome at desktop 1440×1000 and phone
390×844/320×700 sizes. The phone racecard retains its horizontal table scroller;
race selection focuses the detail and scrolls it to roughly 16 pixels below the
viewport top. Browser overrides are temporary and reset at completion.

With 200 ms of simulated network latency, refresh exposes the busy state and
temporarily disables the old sort control; completion restores the selected
order and enables the replacement control. Blocking local API requests produces
the error view, and retry after clearing the block restores the sorted race.
Both network overrides were cleared. The final desktop capture is saved locally
as `data/ui-audit-fixed.jpg`.

The fixes do not decode unknown result codes, establish nationwide completeness,
add collection scheduling, or implement Veikkaus/weather/prediction features.
No screen-reader certification, cross-browser matrix, or physical-device test is
claimed. The original audit's domain and data-coverage limitations still apply.
