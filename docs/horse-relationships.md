# Owners, breeders and pedigrees

Implemented and live-verified on 22 October 2026. The UI and collection remain
local-only. This extends the existing horse-profile endpoint; it does not use an
owner register, a guessed pedigree endpoint or unrestricted recursive crawling.

## Verified source contract

`GET https://heppa.hippos.fi/heppa2_backend/horse/{id}` returns one object. Two
exploratory responses and five normal collector responses returned HTTP 200.
The exploratory responses were held in memory, not archived or manually imported;
their two attempts remain in the shared request ledger with outcome `research`.

Retained fields are horse ID/name, birth date and its accuracy flag, breed code
and display name, gender, registration country, dead flag, owner/breeder display
names, and sire/dam IDs and names. The response also contains chips, laboratory
identifiers, vaccination details, other personal roles, photos and free text;
these are explicitly excluded. No raw response file is retained.

Observed owner/breeder values are **display strings without stable party IDs**.
They may describe a person, company, or co-owner group. The app does not split
strings, invent individual identities, link these names to driver IDs, or claim
to know historical ownership. Blank, dash and null values mean unavailable.

Sire/dam objects contain exact string horse IDs. Parents with a name but no ID
remain unlinked text. Invalid structures, mismatched profile IDs, invalid dates,
non-boolean supplied flags and self-parent references stop collection before
replacing data. Indirect cycles are bounded during discovery and display.

## Collection and storage

The normal collector now permits four endpoint families: daily calendars, race
lists, fields, and horse profiles. All share the same worker lock, ledger,
spacing, UTC daily budget, cooldowns and persistent stops. Browsing never queues
or fetches a profile.

```powershell
# Offline: five known race participants, up to two ancestor generations each.
python -m hippos_analyst seed-profiles --limit 5 --generations 2 --priority 90
# Offline: explicitly select a horse already in the archive.
python -m hippos_analyst seed-profiles --id 6016293616997709938 --generations 2
# Run only when the operating policy permits another batch.
python -u -m hippos_analyst run --max-requests 100 --delay 30 --daily-budget 200
```

Two ancestor generations require at most seven profile requests for a new root
before reuse. Grandparents' immediate parents can appear as identified stubs,
so the UI can display three ancestor levels without fetching a third generation.
Stubs do not automatically become new crawl roots. Batch seeds only select race
participants without an existing profile job; failed jobs are not retried.
Already fetched ancestors are reused. Explicitly selecting a previously collected
horse with a larger depth can queue its known parents without refetching it.
`--refresh` requires an explicit `--id`; routine scheduling does not refresh.

Additive version-1 tables are created idempotently by normal CLI startup:

- `horse_profiles`: latest minimized profile JSON and observation time.
- `horse_parties`: latest owner/breeder label per horse and role, with a SHA-256
  key of the trimmed, otherwise exact label. This is a grouping key, not a person ID.
- `horse_parents`: latest sire/dam links, indexed for reverse offspring lookup.

The existing `horses` table also stores identified ancestors so links work before
their profiles arrive. Consequently the horse count includes ancestors without
race starts. Refreshes replace current relationships atomically; previous minimized
snapshots remain for research. Removed labels disappear from current groups.

## UI and local read API

**Ihmiset → Omistajat / Kasvattajat** offers literal Finnish name search and
30-row pages. Each group opens its matching horses with observation times.
Horse pages show linked owner/breeder labels, birth information, a compact pedigree,
and a paginated reverse offspring list. Source-name grouping and incomplete
coverage are explained in Finnish beside the data.

- `/api/parties?role=owner&q=...&offset=0` (or `breeder`): name groups and counts.
- `/api/party?role=owner&id={group-key}&offset=0`: at most 30 matching horses.
- `/api/horse?id=...&offspring_offset=0`: existing horse/starts plus profile,
  collection status, party links, a three-level pedigree and at most 30 offspring.

Offspring means references found in collected profiles, not all progeny recorded
by Hippos. Pedigree data may combine observations from different dates. Unknown,
unqueued, pending and failed profiles have explicit UI states. Direct parents and
offspring link both ways; search and page state survive return navigation/reload.
Nested return context is capped at three levels to prevent repeated family
navigation from growing URLs indefinitely; browser Back retains full history.
Navigation context is not sent to the local read API.

## Verification

62 Python tests and 20 JavaScript tests pass, plus ES-module syntax and diff checks.
New coverage includes minimized fields, large string IDs, placeholders, identity
and type errors, atomic correction, old snapshot retention, additive initialization,
bounded/shared/cyclic ancestry, provider-stop and shared-budget behavior, grouping,
label removal, pagination and repeated family navigation.

Chrome checks on real and synthetic archives covered breeder → horse → parent →
offspring, owner search and detail, pending ancestor profiles, Finnish keyboard
search, empty-search recovery, 30-row group/horse/offspring pagination, return
navigation and reload. Desktop and 320px views were inspected without document
overflow. No console errors were observed. Local screenshots are
`data/relationships-live.jpg` and `data/relationships-mobile.jpg`.

```powershell
python -m unittest discover -s tests -v
node --test tests/ui.test.mjs
node --check hippos_analyst/web/app.mjs
python scripts/benchmark_relationships.py --db data/relationships-growth-new.sqlite3
```

The benchmark refuses existing paths, makes no network calls, and creates 10,001
synthetic profiles, 200 owner groups, 500 breeder groups and 10,000 offspring of
one parent. Correct counts/page sizes, SQLite integrity and foreign keys are
asserted. Three measurements include read construction and JSON serialization,
excluding HTTP/browser overhead. Median results on this machine:

| Read | Median | Response bytes |
| --- | ---: | ---: |
| Owner directory | 70.99 ms | 4,690 |
| Breeder directory page two | 64.29 ms | 4,543 |
| Owner's horses page two | 0.16 ms | 3,212 |
| 10,000-offspring parent, page two | 4.13 ms | 5,046 |

Results: ignored `data/relationships-growth-results.json`. Directory aggregates
still scale with collected profiles. Existing horse start history is not paginated;
these measurements do not establish unlimited capacity or complete source coverage.
See [backfill](backfill.md) for the final live counts and daily schedule.
