# Local UI

The current interface is documented in the [table workspace verification](#table-workspace--25-october-2026) below. Earlier verification entries describe their respective releases.

Owner/breeder name groups and linked pedigrees are implemented. The earlier
[relationship verification](horse-relationships.md) records 62 Python and 20
JavaScript tests, desktop/mobile journeys and the 10,001-profile growth fixture.

The **Ihmiset** section adds searchable drivers and trainers, linked profiles and
paged upcoming/history entries. See [people and relationships](people.md) for
the current 51 Python / 18 JavaScript test results, browser checks and growth
measurements. Older verification counts below describe their respective releases.

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
  Click a column header to cycle ascending, descending and default order. The
  selected race/order are preserved in the URL. Scratches are marked **Pois**.
  Race links open the calendar selection; old standalone race URLs redirect there.
- Clicking row space or its disclosure expands up to five earlier collected starts
  below that runner, with horse facts, equipment and driver/trainer previews.
  Horse and person names are normal profile links, including modified clicks.
  Sorting the race preserves expanded rows.
- Use the compact **Hevoset** and **Ihmiset** tables to search, filter and sort
  the whole matching dataset before pagination. All people roles share one table
  with a role filter. Search supports
  Finnish case folding and pagination. Horse IDs remain strings end to end.
  A profile's return link restores the originating query and page. Profiles opened
  from the calendar or a standalone race return to that view instead. Direct profile
  links fall back to horse browsing; external return destinations are not accepted.
- Horse history and summary counts describe only the collected sample. They are
  not career records, predictions or official statistics.
- Hash routes preserve filters/search and support browser back/forward. Finnish
  text is maintained in `hippos_analyst/web/locales/fi.mjs`.

The interface includes empty/loading/error states, keyboard focus, a skip link,
semantic tables, narrow-screen navigation and horizontally scrollable wide tables.
Compact top navigation leads directly to the data. On mobile the meeting list
becomes a horizontal strip. Selecting meetings and races preserves the viewport,
keyboard focus and horizontal list/tab scroll positions. Race panels show every
runner in normal page flow, including expanded horse details. The page owns
vertical scrolling; the meeting sidebar, race heading and field have no separate
vertical scrollbars. Panel height follows the content.
Old content remains visible during local reads instead of flashing a loading page.
Directory filters and pagination also preserve position; opening another profile
starts at its heading. There is no separate refresh-view button: navigation reads
the current local database, and browser reload refreshes the current view.
Repeated introductions and the local-data badge/footer have been removed. Context
about collection and result semantics is available under **Tietoja aineistosta**;
timestamps and missing-data states remain visible. Operational collection status
is shown under coverage, without a collection-stop badge above the calendar.
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

Collection ran concurrently with these historical UI checks. Archive counts and
queued-job counts are snapshots; navigation or browser reload reads newer records.
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

Current verification is **47 Python + 16 frontend tests** plus syntax and browser
checks. See [the product record](product-improvements-2026-10-22.md) for complete
journeys, responsive evidence, semantics, limitations and reproducible fixtures.

### Live relationship review — 25 October 2026

Reviewed the local app against 30 meetings, 359 races, 3,799 entries and 2,394
horse identities. The people directory contains 627 driver records and 1,224
trainer records, counted separately by role. Relationship enrichment currently
covers eight profiles, five owner-name groups, three breeder-name groups and
16 parent links; it does not cover the whole racing archive.

In-app browser journeys verified horse search → Corazon Combo → owner/breeder
group → horse; horse → P Korpi (driver) → Pekka Korpi (trainer); trainer history
page two → Gremlin Combo → return to the same history page; and trainer → race
→ inline horse history. Reload retained the trainer's history period and page.
Uncollected profiles displayed their explicit missing-data message.

Breeder search submitted with Enter, opened Ulla Gustavsson Konsult AB and then
Ullabella. Ullabella → Tekno Odin → Ullabella through the offspring list worked.
The populated three-level pedigree was inspected at the normal 1280px viewport
and at 390×844. Neither view had document-level horizontal overflow; the phone
layout stacked ancestry branches legibly. The temporary viewport was reset.

**Minor layout finding:** at the desktop width, the eight deepest pedigree
columns squeeze some names and the “Profiili keräämättä” label into awkward word
breaks. Links remain usable, but a wider minimum branch width or earlier stacked
layout would improve reading. This review did not change application code.

All 62 Python and 20 JavaScript tests passed. Database integrity was `ok`, with
zero foreign-key violations, zero race-entry links to missing horses and zero
identified parent links to missing horses. No browser console warnings or errors
were captured in these journeys. This is representative interaction verification,
not an exhaustive click-through of every person and horse. Browsing made no new
provider requests. Screenshot: `data/ui-relationships-2026-10-25.jpg` (local,
ignored by Git). The loopback server remains available on port 8765.


### Stable navigation and copy cleanup — 25 October 2026 (earlier iteration)

Removed forced mobile scrolling after meeting/race selection. The app retains
its header and current content while loading, restores focus without scrolling,
and preserves the viewport and nested meeting/tab/table scroll positions for
changes within a view. Pagination also retains keyboard focus on its next/previous
control when the destination URL changes. New entity pages still start at their
heading. A viewport-sized minimum prevents shorter pages from clamping scroll
position without retaining an entire previous directory's blank tail.

The initial implementation used a stable viewport-relative height and sticky table header
with scrolling rows. That containment was superseded by the natural page-flow
change below after user feedback; the navigation/focus fixes remain. Deep pedigree
branches stack earlier.

Removed the refresh-view control, local-data badge, repeated footer, generic page
introductions and opaque record-ID footers. Profile explanations are consolidated
in a single disclosure; collection/result explanations remain accessible without
repeating them above each section. Missing data, fetched timestamps, scratched
runners and collection-stop indicators remain explicit. No collector or backend
behavior changed.

Verification against the local archive:

- Before the fix, one race change at 816px moved scroll Y from 0 to 761.33px and
  increased document height by 191px. Afterward, direct race and meeting taps at
  that width preserved Y=0, document height=1650px and panel height=992px.
- At 390×844, direct taps from Pori race 2 (12 runners) to race 3 (10 runners),
  then Kuopio, retained Y=378.67px, document height=1451px and panel height=742.79px.
- At 1440×1000, populated and empty meeting panels both measured 852px; document
  height remained 1217px. The meeting sidebar retained its internal scroll.
- Standalone race selection with Enter retained Y=0, document height=985px and
  focus on the selected race. At 320×700 there was no document horizontal overflow.
- Horse directory paging retained Y=85.33px and focus on **Seuraava** across pages.
  Breeder directory → Ulla Gustavsson Konsult AB → Ullabella opened correctly.
  The desktop pedigree no longer compresses the deepest ancestors into eight
  narrow columns, resolving the preceding review's minor finding.
- All **62 Python tests and 21 JavaScript tests** pass, as do the module syntax
  check and `git diff --check`. The added routing test covers in-place selection,
  filtering, paging and entity boundaries. No browser warnings/errors were captured.

These are representative manual browser checks plus automated routing/data tests,
not an exhaustive traversal of every archived record. Browser automation can scroll
an offscreen control into view before clicking; direct visible taps were used for
the mobile no-jump measurements. The final preview is saved at
`data/ui-stability-2026-10-25.jpg` (ignored by Git). Viewport overrides were reset.


## Toto pilot — 25 October 2026

Racecards now show source-labelled win odds, Hippos equipment, and up to three
Toto observations inside the existing horse expansion. Source-update time,
collection time and relation to scheduled start remain distinct. A failed Toto
collection is shown explicitly, while the original Hippos records remain usable.
See [Toto integration](toto.md) for limits and the current historical parser stop.

Verified live current quotes and historical failure state in the browser. Desktop
race switching retained Y=78, document height=1217 and panel height=852; phone
switching retained Y=607.33 with a one-pixel document-height difference. The table
scrolls within the existing panel. Tests: 78 Python and 23 JavaScript passed;
module syntax and whitespace checks passed. These checks do not establish that
all historical Toto responses are supported: collection is paused on one such
response. The user-facing local server is running on port 8765.


## Natural page scrolling — 25 October 2026

Removed the race's fixed height and both nested vertical overflow containers.
All participants and expanded horse details now increase the document height.
Removed the desktop meeting sidebar's independent scrolling, mobile meeting-card
height constraints, clipped meeting headings and the oversized empty-race spacer.
Wide tables, race tabs and the mobile meeting strip retain horizontal scrolling.
Source explanations expand in normal flow instead of overlaying race content.
Existing focus and page-position restoration remain unchanged.

Browser verification against the saved archive:

- At 1440×1000, Kuopio race 1 displayed all ten rows in a 787px table viewport
  with matching 787px content height. Expanding Vonkaisu grew both to 1032px;
  no inner vertical scrollable element remained in the main content.
- Scrolling over the table moved the page by 400px and left its internal scroll
  position at zero. A direct switch to the 12-runner race 2 retained page Y=200;
  the table grew to 938px and showed the entire field.
- At 390×844, standalone Vermo race 1 showed all nine rows (712px table/content
  height), no nested vertical scrolling and no document horizontal overflow.
  Scrolling over the table moved the page by 422px. The source disclosure expanded
  the footer to 250px without clipping or an overlay.
- Mobile calendar selection from Kuopio race 1 to race 2 retained Y=506.67 and
  focus on the selected tab. Tab then Enter selected race 3 at the same Y position.
  The meeting strip had no internal vertical overflow.
- No browser warnings or errors were captured. Viewport overrides were reset.
- All 23 existing JavaScript tests, the module syntax check and whitespace check
  passed. No backend changes or provider requests were made for this UI pass.

Earlier fixed-height measurements above describe the superseded layout, not the
current acceptance criterion. Content height may change; selection must not force
an unrelated page jump. The screenshot is `data/ui-page-flow-2026-10-25.jpg`.


## Compact race workspace — 25 October 2026

Reduced space above the runners without reducing runner typography or row spacing.
The calendar heading remains available to assistive technology and document-title
logic, while the selected navigation item identifies the page visually. Filters
are grouped together instead of being pushed to opposite ends of the screen.
Removed reserved meeting-header height and tightened tab/filter spacing. Race
number/time, metadata, participant count, status and sorting now share the race
header on desktop; narrow screens wrap them into readable rows. Meeting cards
also use smaller padding. Every field still grows naturally with its content.

At 1914×958, the first runner moved from document Y=581.53 to Y=372.53: **209px
recovered** above the field. Seven full runner rows were visible after the change.
At 1024px the header had no horizontal overflow; at 390×844 the page had no
horizontal overflow or nested vertical scroll containers. Sorting worked, and a
direct mobile race change retained Y=422, the selected sort and keyboard focus.
All 23 JavaScript tests, module syntax and whitespace checks passed. The screenshot
is `data/ui-compact-calendar-2026-10-25.jpg`; viewport overrides were reset.


## Table workspace — 25 October 2026

The calendar is the canonical race view. Desktop date presets, custom dates and
track controls sit above the meeting list in a sticky sidebar header. On phones
the controls flow above the horizontal meeting strip. There is no duplicate race
page or sort dropdown. Headers are keyboard buttons with `aria-sort`; three clicks
cycle ascending, descending and source order. Numeric values sort numerically,
unknown values stay last, and equal values have deterministic ordering. Clicking
row space expands details; linked names navigate deliberately. Existing expansions
survive local race sorting. Collection messages no longer occupy the main header.

Horse and people directories use compact filter bars and 30-row semantic tables.
Horse filters include breed, gender, age range and upcoming entries. People share
one role selector; driver/trainer identities remain distinct `(role, id)` records,
and owner/breeder name groups retain their separate provenance. Name filtering is
literal and Finnish-aware. Debounced search cancels stale requests and restores
input focus/caret. Sorting and filters apply globally before paging.

Horse/person profiles put upcoming entries and history first, with compact sample
counts. Horse facts sit alongside activity on wide screens; pedigree and offspring
have a separate family tab. Person profiles also expose related horses. Upcoming
rows show entry status, rather than empty result columns. Relationship lists are
sortable tables. Return links preserve search, role, period, page and sort state.

### Read paths and limits

- `/api/directory/horses` and `/api/directory/people`: `today`, `q`, `offset`,
  `sort`, `dir` plus their UI filters; 30 rows per response.
- `/api/activity`: `today`, `role=horse|driver|trainer`, `id`,
  `period=upcoming|history|horses`, `track`, `q`, `offset`, `sort`, `dir`.
- `/api/preview`: `today`, `kind`, `id`, optional `before`; five rows at most.
  Race previews exclude starts on/after that race date.
- `/api/horse?section=activity` omits unbounded legacy history and pedigree;
  `section=family` loads relationships on demand. Legacy read routes still work.

All reads retain latest-successful-list membership and use a consistent read
transaction. Directory aggregates are cached per server, invalidated by the latest
successful observation and Helsinki day. The cache holds one record set per kind,
not one per query; memory still scales with archive identity count. Inline previews
have an 80-item, 30-second client cache. No production dependency, schema change,
upstream request or collector configuration change was needed.

### Verification

105 Python tests and 26 JavaScript tests passed with the concurrent name-resolution
changes included. Coverage includes whole-dataset sorting and paging, role/ID
separation, literal/Finnish search, missing numeric values, cache invalidation,
visible-list removals, bounded previews, relationships, three-state sorting,
canonical race links and origin/filter restoration. Module syntax checks passed.

Manual browser checks at 1440×1000 and 390×844 covered calendar selection, all three
sort states, preserved expansion, keyboard disclosure, inline person details,
debounced search, role filtering, profile back links and person history page two.
The old race URL opens the calendar selection. Tested mobile calendar and horse
views had no document horizontal overflow or nested vertical scroll containers;
wide tables retain horizontal scrolling and expanded details stay within the
visible width. These are representative checks, not exhaustive accessibility tests.

Reproduce the synthetic growth check without modifying its source database:

```powershell
python scripts/benchmark_browse.py --db data/people-growth-verified.sqlite3
```

100,000 entries / 100,000 horses / 2,500 role identities; three repetitions, name
descending sort, validated totals, ordering and 30-row responses. Median read-model
plus JSON times: horses 632.65 ms cold / 117.48 ms warm; people 1353.47 ms cold /
1.87 ms warm. Payloads were 6,640 and 6,321 bytes. Cold means empty application
cache, not cold OS/SQLite caches. HTTP and browser rendering are excluded. The
first people read includes the concurrent full-name resolution work. These are
local fixture measurements, not guarantees for arbitrary archive sizes.


### Compact inline details — 25 October 2026

Expandable rows now own their disclosure state and keyboard focus. Clicking row
space or pressing Enter/Space toggles the detail row; names retain normal links.
A decorative chevron sits in the last column, pinned to the visible right edge
on horizontally scrolling tables. Separate chevron and close buttons are removed.

The stronger green expansion uses a compact horse-facts line and adjacent horse,
driver and trainer sections. Driver/trainer summaries and up to three upcoming or
recent starts load automatically through the existing bounded preview endpoint;
there are no nested person disclosures. Odds observations sit with horse history,
without a separate full-width block below the tallest section. Unknown horse facts
are omitted rather than reserving a mostly empty background-information column.

Verification: 26 existing frontend tests, module syntax and whitespace checks
passed. Browser checks covered Enter/Space and pointer toggling, normal person
navigation, expansion retention while sorting, and matching header/body column
counts. At 1914×958, Vonkaisu's expansion was 254px tall with both person summaries
visible. At 390×844 the expansion fit a 315px content width, the chevron remained
at the visible right edge, and there was no document horizontal overflow or nested
vertical scroll container. No backend or collection changes were needed.
