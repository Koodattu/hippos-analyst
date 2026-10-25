# Trainers, drivers and relationships

Implemented 22 October 2026. Local-only; no new upstream requests or collector
changes were needed. The current 1,722 entries contain 411 distinct driver IDs
and 845 distinct trainer IDs. These are role-specific counts, not a combined
count of unique people or the complete Hippos register.

## User journeys

- **Ihmiset → Ohjastajat / Valmentajat**: Finnish case-insensitive literal name
  search, 30 people per page, distinct horses and entry counts.
- Open a person to see upcoming entries, paginated history, linked horses,
  the other role recorded on each entry, and direct race links.
- Driver/trainer names on racecards and horse histories open these profiles.
  Return links preserve search, role, history/upcoming selection and page.
- Names without an ID remain text. Empty results explain the archive boundary;
  unknown or removed people use the existing not-found screen.

Profiles show entry counts, result-bearing entries and first places in this
archive, not career statistics. Tied first places count; scratches do not count
as results. Trial starts are included and labelled in the rows. Upcoming means
today or later without a result, using the same Helsinki-date convention as
horse profiles. Canceled meetings and scratches remain visible with labels.

A trainer is an assignment on a particular archived race entry. It does not
establish the horse's current trainer, stable or ownership. Names may be
abbreviated. The latest observed name for each role is expanded only when the
same exact Hippos person ID has one unambiguous compatible full name in visible
entries. Role profiles and statistics remain keyed by `(role, exact string ID)`;
name similarity alone never establishes identity. See the verification below.

## Read API and storage

- `/api/people?role=driver&q=...&offset=0` (or `role=trainer`): people, total,
  offset and limit (30). Search is literal, including `%` and `_`.
- `/api/person?role=trainer&id=...&from=YYYY-MM-DD&period=history&offset=0`:
  person, whole-archive summary and at most 30 entries. `period` is `upcoming`
  or `history`; omitted selects upcoming when available, otherwise history.
  `from` is the caller's Helsinki calendar date, not a source-fetch instruction.

Both queries reconcile latest successful calendar and race-list membership before
counting or paging. Removed races do not consume page slots; refreshed fields
replace old relationships. Invalid roles, periods and offsets are rejected.
Stale valid offsets clamp to the last available page.

IDs and competition names were already collected in allowlisted entry JSON.
There is no migration, new dependency or separate identity registry. Queries
join visible race keys against the existing entry primary key. The HTTP server
continues to use read-only transactions and loopback binding.

## Verification

51 Python tests and 18 JavaScript tests pass; ES-module syntax checks pass.
New cases cover same-name/different-ID people, role separation, updated names,
missing IDs, Finnish literal searches, removal/correction, page boundaries,
results, ties, scratches, upcoming/history separation and internal return routes.

Chrome checks used synthetic and real archives: keyboard search, empty-search
recovery, role switching, profile history page two and reload, horse/race return
links, race-to-trainer navigation, and real directory page two (31–60 / 411).
Desktop and 320px layouts were inspected. Mobile directory fits the page;
wide race-history tables scroll within their focusable region. No console errors
were observed. The four profile totals use two columns on small screens.
Local screenshots: `data/people-profile-mobile.jpg`, `data/people-profile-live.jpg`.

Repeatable synthetic checks (choose fresh filenames):

```powershell
python scripts/seed_demo.py --db data/people-demo-new.sqlite3 --today 2026-10-22
python -m hippos_analyst --db data/people-demo-new.sqlite3 serve --port 8767
python scripts/benchmark_archive.py --db data/people-growth-new.sqlite3
```

The growth fixture has 100,000 entries, 500 drivers and 2,000 trainers. Three
measurements include read-model construction and JSON serialization, excluding
HTTP/browser overhead. Correct counts, identities and page sizes are asserted;
SQLite integrity and foreign keys pass. Median times on this machine:

| Read | Median | Response size |
| --- | ---: | ---: |
| Driver directory | 1.080 s | 3,961 bytes |
| Trainer directory | 1.083 s | 3,963 bytes |
| Driver history page two | 0.381 s | 22,610 bytes |
| Trainer history page two | 0.424 s | 15,148 bytes |

Results are in ignored `data/people-growth-results.json`. On the current real
archive, single directory reads measured 25–26 ms. Responses and rendered rows
are bounded, but aggregation still scans visible entries. These measurements do
not establish unlimited capacity; consider indexed relationship projections if
larger archives make directory searches slow.

## Next data areas

Update: owner/breeder source-name groups and bounded pedigrees are now implemented
and verified in [horse relationships](horse-relationships.md). The table below
records the earlier planning questions; stable person IDs and ownership history
remain unverified.

| Area | Next useful capability | Evidence still needed |
| --- | --- | --- |
| Tracks | Track pages, venue calendars and weather context | Stable venue identity, coordinates, source contract |
| Owners and breeders | Horse relationships with observation dates | Observed public fields/endpoints, stable IDs and archival scope |
| Stables | Horses and trainer relationships | Explicit stable identity; never infer a stable from a trainer name |
| Pedigrees | Sire, dam and offspring links | Verified horse-profile contract and bounded discovery rules |
| Race conditions | Eligibility, entry deadlines and equipment details | Field/code meanings, units and freshness requirements |
| People analysis | Date/track/breed filters and comparisons | Broader coverage and comparable race/result definitions |

Owners, breeders and pedigrees now have a bounded profile importer. Earlier race
snapshots cannot supply those fields; explicit stable details remain unimplemented.
Inspect observed public
requests before expanding allowlists; retain only relevant competition facts.
Any future importer must share existing request budgets, cooldowns and persistent
provider-limit stops. This feature did not restart the collector after its last
transport failure.

## Full person names — verified 25 October 2026

Hippos uses a shared person ID for drivers and trainers. The public
[Mobiiliheppa app](https://heppa.hippos.fi/mobiili/) routes both role tabs through
`/people/:id`; its `getPromise` passes that same ID to `/person/{id}`,
`/driver/{id}/stats` and `/trainer/{id}/stats`. This was checked in bundle
`7b2befc90a22ad05f3fa` and person chunk `23-bee4be53bfbf4c690bb1`.

Bounded live profile checks confirmed:

- `/person/2576121652984750609`: `firstname=Antti`, `lastname=Ala-Rantala`.
  That ID occurs locally as both driver `A Ala-Rantala` and trainer
  `Antti Ala-Rantala`.
- `/person/295190086041368698`: `firstname=Tommi`, `lastname=Kylliäinen`.
  The archive has driver `T Kylliäinen` without a trainer record for that ID.
  Full names are therefore available beyond local cross-role matches, although
  these samples do not establish complete coverage of every person.

The race response `/race/2026-10-28/H/start/9` also supplies `driverFirstName`
and `driverLastName` alongside the abbreviated `driverName`. For example,
`T Varis` has `Tuukka` / `Varis`, and `Vil Koivisto` has `Ville` / `Koivisto`.
Hippos's race-display module uses these same fields. Our allowlist now retains
both fields during normal collection and refresh. Previously minimized snapshots
cannot recover omitted fields without a new observation.

The read model uses these explicit driver fields and trainer names as full-name
candidates for the exact string person ID. It requires a unique candidate and a
matching complete surname plus a compatible given-name prefix (including dotted
initials and multi-letter abbreviations). Conflicting candidates, incompatible
names and missing IDs remain unchanged. Removed races/meetings supply no evidence.
The candidate cache is invalidated by successful collection observations.

Resolved names are used in directories, role profiles, racecards, histories,
previews and sorting before pagination. Directories search both the resolved
name and the latest source label. Responses retain `source_name` on role records
and `driverSourceName` / `trainerSourceName` on entries whose display name changed;
stored entry names and snapshots are untouched. Owner/breeder name groups and
role-specific counts are unchanged. On the checked archive this resolved 390
driver labels, including multi-letter abbreviations.

No person-profile importer or automatic upstream lookup was added. Unmatched
names can improve through ordinary race refreshes using the newly retained
fields. The four profile/race research requests used the existing collector lock,
30-second spacing, combined daily budget and persistent stop controls. Only
minimized identity/name research evidence was retained in ignored `data/` files;
unrelated person-profile values were not saved.

Regression coverage in `tests/test_person_names.py` checks exact string IDs,
conflicting candidates, prefix compatibility, source preservation, all display
paths, imported explicit names, search, ordering and cache invalidation after
corrections and membership removal.

### Hyphenated initials follow-up

Matching now compares each hyphen-separated given-name component: `A-S Hanttu`
resolves to `Anni-Sofia Hanttu` only for the same exact person ID, with the surname
and both initials matching. Different initials, missing components and different
IDs remain unresolved. This adds 15 safe driver expansions in the checked archive,
for 405 resolved driver labels in total. Six focused name-resolution tests cover
the matching and display paths.

The other eleven abbreviated labels in the follow-up screenshot have no full-name
candidate in the local archive. They require a new upstream observation, through
ordinary race refreshes or a future bounded person-name importer using the verified
`/person/{id}` endpoint. No profile-name backfill has been performed.
