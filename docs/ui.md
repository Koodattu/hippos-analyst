# Local UI

Run `python -m hippos_analyst serve` from the repository and open
[http://127.0.0.1:8765](http://127.0.0.1:8765). Stop the server with Ctrl+C.
Use `serve --port 8766` to change the port. No dependency install or build is needed.
The server is bound only to the local computer; there is no account system or
public hosting. Running the UI never starts the collector or calls Hippos.

## Implemented flows

- **Kilpailukalenteri** defaults to yesterday through six days ahead, using the
  current date in Helsinki. Filter dates and track, or select **Koko aineisto**.
  Calendar records are a sample, not proof of an empty nationwide racing day.
  Broad ranges show 30 meetings per page, with previous/next controls above the
  meeting list. The URL retains page, range and sort order. See the
  [growth verification](archive-growth.md) for the larger-archive measurements.
- The calendar opens a relevant racecard automatically. Meetings and their race
  numbers sit beside the racecard on desktop; clicking a number opens that race
  directly and preserves the date/track filters. Week arrows and **Viimeiset 7 päivää**
  provide quick date changes. Trial and pony races remain visible.
  Track changes apply immediately and retain keyboard focus in the track select;
  edited dates use **Näytä** or Enter. Week arrows remain available when a filtered
  range is empty or has never been collected.
- Racecards show participants, drivers/trainers, distances and available results.
  Sort by program number or placing. The selected race/order are preserved in the
  URL across local refresh, reload, and race links. Scratches are marked **Pois**. The external-view
  icon opens a standalone local race view; it does not contact Hippos.
- Clicking a horse name in a race expands up to five collected starts directly
  below that runner. Close it in place or open the full horse page. Modified clicks
  retain normal link behavior, including opening a horse in a new tab.
- Use **Hevoset** to search names. Search supports
  Finnish case folding and pagination. Horse IDs remain strings end to end.
  A profile's return link restores the originating query and page. Profiles opened
  from the calendar or a standalone race return to that view instead. Direct profile
  links fall back to horse browsing; external return destinations are not accepted.
- Horse history and summary counts describe only the collected sample. They are
  not career records, predictions or official statistics.
- Hash routes preserve filters/search and support browser back/forward. Finnish
  text is maintained in `hippos_analyst/web/locales/fi.mjs`.

The interface includes empty/loading/error states, keyboard focus, a skip link,
semantic tables, narrow-screen navigation and independently scrollable race tables.
The sidebar and oversized archive statistics were replaced by compact top navigation
and a small archive summary. On mobile the meeting list becomes a horizontal strip;
selecting a race brings the racecard into view. **Päivitä näkymä** reads current local
data without starting collection. Ordinary race changes preserve the meeting-list
scroll position and do not replace the whole page with a loading screen.
Source links open the Heppa home page; stable deep links are not yet verified.

## Result semantics

Observed upcoming entries have `placing="0"` and `price="0"`. Some historical
entries also have a zero placing. Until the source codebook is verified, the UI
shows zero placing as a dash and does not count it as an explicit result. It also
hides the prize for these entries. Source values remain unchanged in SQLite.
Other result codes are displayed as supplied; they are not translated into guessed
disqualification or finishing categories. Numeric result sorting is not a codebook.

Explicit first places (`1` and the equality suffix `1=`) count as **Ykkössijaa**,
excluding scratches. These counts include trial/pony races; they are not career
competition-win statistics. **Lähtömerkintää** includes upcoming fields and scratches.
**Tulosmerkintää** means an explicit nonzero placing/code, not all completed starts.
Absence of results is not inferred from the date. No odds or winnings predictions
are shown. Timestamps identify when each local snapshot was fetched, not live data.

## API and persistence

Read-only GET endpoints: `/api/overview`, `/api/calendar?from=…&to=…&track=…`,
`/api/meeting?date=…&track=…`, `/api/race?date=…&track=…&number=…`,
`/api/horses?q=…&offset=…`, and `/api/horse?id=…`.
Each response uses one consistent SQLite read transaction. Missing details return
404, invalid parameters 400 and database failures 503. Static assets are allowlisted.

The latest successful observations determine visible meeting/race membership.
A removed meeting or race disappears from current UI views without deleting the
research archive. A never-collected race field is distinct from a successfully
collected empty field. Existing snapshots remain visible during a queued refresh,
with their original observation timestamps.

## Verification

```powershell
python -m unittest discover -s tests -v
node --test tests/ui.test.mjs
```

36 Python tests and 9 JavaScript tests passed on 22 October 2026. Tests include
HTTP responses/static boundaries, Finnish search and pagination, string IDs,
list removals/restorations, incomplete fields, result zeros, ties, scratches,
Helsinki midnight/DST dates, HTML escaping and the existing collector safeguards.
Additional workspace tests cover automatic selection, direct race links preserving
filters, removed/empty race lists and calendar race metadata without runner payloads.
Python tests make local HTTP requests against a temporary synthetic database;
they never contact upstream services. Node is a test-only requirement.

Chrome checks passed against the real local archive on 22 October 2026:

- Calendar current/all-data views and track filter; selecting Lappeenranta left
  only that meeting visible.
- Upcoming racecard: nine runners in Lappeenranta race 1, no spurious zero results
  or prizes. Nordic Goldie's profile showed one entry and zero explicit results.
- Historical Vermo race 1: sorting by placing moved Scudetto (program 7, place 1)
  to the top. Scratch and missing-result states remained distinct.
- Case-insensitive horse-name search, no-match state, 30-item pagination and
  browser back restored the first page. A missing horse showed a recoverable error.
- Desktop and 390×844 viewport inspection. Mobile calendar and race detail had
  no document-level horizontal overflow; the race table retained its own scroll
  region. The temporary viewport override was reset after testing.
- Keyboard skip link focused the main content without corrupting the hash route.
- No application-origin console warnings/errors during normal flows. Chrome's
  unrelated wallet extension emitted warnings; the deliberate missing-record test
  returned the expected HTTP 404.

A desktop preview is saved locally at `data/ui-calendar.jpg` (ignored by Git).
The dataset contains 4 meetings, 47 races, 468 entries and 456 horses; see the
[bounded live-run record](collection.md#ui-sample-expansion--22-october-2026).
This is a small sample, not a completeness or prediction-quality claim.

### Workspace redesign verification — 22 October 2026

- At 1440×1000, the meeting list and full race table share the available width;
  archive statistics no longer occupy a separate large panel.
- Default selection opened today's Forssa race immediately. Selecting a Vermo race
  number changed the adjacent racecard in one click while preserving dates and
  the Helsinki track filter. Browser Back restored the prior selection.
- Incanto WF's history expanded and closed inside the field; closing returned
  focus to its name. On mobile, keyboard Enter opened/closed Pastori's history
  with the same behavior.
- At 390×844, document width stayed within the viewport. Meeting cards used their
  own horizontal strip. A race selection focused and scrolled directly to the
  selected racecard; result tables retained their own horizontal scroll.
- Turku on 29 October had a collected empty race list and showed the explicit
  not-yet-available state rather than an error or fabricated field.
- Changing the track dropdown applied the filter without an extra button click.
- No application-origin browser console errors or warnings in these flows.

Collection ran concurrently with UI checks. Archive counts and queued-job counts
are snapshots; use the refresh-view button to see subsequently collected records.
The revised desktop preview is saved at `data/ui-workspace.jpg` (ignored by Git).

### Audit correction verification — 22 October 2026

All eight audit findings are resolved. **43 Python tests and 12 JavaScript tests
pass**, together with the ES-module syntax check. Browser verification covered
consecutive keyboard track selection, empty-week navigation in both directions,
result sorting through refresh/reload, and paginated horse-search return after
reloading the profile. Calendar/race-origin profile return links were also checked.
At 390×844 and 320×700, tested views retained independent table scrolling and had
no document-level horizontal overflow. Mobile race selection still focuses and
scrolls to the racecard. The muted text token now measures 5.358:1 on the page
background, with sampled white/selected/footer surfaces above that ratio.

The [fix record](audit-fixes-2026-10-22.md) contains acceptance evidence and
performance measurements. Viewport overrides were reset after testing. These are
targeted Chrome and contrast checks, not a full accessibility certification.

### Product improvement wave — 22 October 2026

Current verification is **47 Python + 15 frontend tests** plus syntax and browser
checks. See [the product record](product-improvements-2026-10-22.md) for complete
journeys, responsive evidence, semantics, limitations and reproducible fixtures.
