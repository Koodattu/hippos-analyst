# Archive growth verification — 22 October 2026

Broad calendar ranges previously expanded every meeting and race into one JSON
response and DOM tree. Calendar responses now contain at most **30 meetings**.
The date/track filter and latest source membership are applied before paging;
only the selected page's race fields are expanded. Removed meetings consume no
page slots. Responses include `total`, `offset`, and `limit`; invalid offsets are
rejected and stale offsets after removal clamp to the last available page.

The Finnish UI shows previous/next meeting-page controls above the meeting list,
sticky within the desktop column. The controls preserve the date range and sort
order and clear the previous page's selected race. Dates are pinned when paging
so new collection outside the range cannot move the page. Changing filters resets
the page. Reload and horse-profile return links preserve the page in the URL.
Page changes reset the meeting column's scroll position; race changes within a
page retain it. Offsets are not immutable cursors: insertion/removal within the
selected range can still change page membership on refresh.

## Repeatable synthetic check

```powershell
python scripts/benchmark_archive.py --db data/growth-check.sqlite3
python -m hippos_analyst --db data/growth-check.sqlite3 serve --port 8766
```

The script refuses an existing destination and makes no external requests. Choose
a fresh path for a rerun. It builds 1,000 meetings, 10,000 races, 100,000 entries,
and 100,000 distinct horses. Synthetic names are visibly marked. This database is
separate from `data/hippos.sqlite3`; the test server is stopped after verification.

Three local measurements include complete read-model construction and JSON
serialization, excluding HTTP/browser overhead. Correct totals, page sizes,
boundary dates and runner identities are asserted outside timing. SQLite integrity
and foreign keys also pass. Measurements on this machine:

| Completed read | Median ms | Min–max ms | Response bytes |
| --- | ---: | ---: | ---: |
| Overview | 31.18 | 31.11–36.25 | 272 |
| Archive first page | 22.73 | 21.89–24.71 | 164,715 |
| Archive last page | 17.07 | 16.64–18.90 | 101,617 |
| One-day calendar | 0.99 | 0.87–2.03 | 3,287 |
| One race | 0.30 | 0.29–0.40 | 8,011 |
| Horse list, first page | 64.05 | 60.85–67.35 | 3,270 |
| Horse list, last page | 105.29 | 104.87–105.81 | 1,160 |
| Horse substring search | 73.16 | 72.98–75.51 | 3,366 |

Raw results: `data/growth-check-results.json`. Desktop proof:
`data/ui-growth-fixture.jpg` (synthetic fixture, not collected Hippos data).

## Regression and browser checks

- **44 Python tests pass**, including page boundaries, removed membership,
  stale/invalid offsets, bounded field expansion and all collector stop rules.
- **13 JavaScript tests pass**, including page/filter/sort URL round trips.
- ES-module syntax check passes.
- Chrome desktop 1440×1000: next page has 30 cards, 31–60/1,000, and column scroll
  resets. Result order and page survive a hard reload.
- Chrome phone 390×844: next/previous pages retain order; 320×700 settles without
  document overflow. Track changes return to page one.
- The real archive remains browsable while the single collector writes to SQLite;
  local refresh preserves selected race and result order.

The meeting summaries and coverage-day metadata still scale with the requested
date range; overview scans meeting membership and horse search scans names. Paging
bounds expanded fields and rendered cards, not every query or byte independent of
archive size. Re-measure as real coverage grows; these results do not certify
unlimited scale, every browser, or complete provider data.
