# Track profiles

Implemented 25 October 2026. Open **Raviradat** to browse the map and venue cards.
The heading sits inside the map; there is no directory search form or intro block.
A profile links to its website, map location, source
pages and paged upcoming/historical meetings. Race pages link back through
**Radan tiedot**. Period and page survive navigation through racecards.

The directory pairs a Finland outline with the track cards. Circles use the
stored coordinates, with city names centered just above their dots.
Both circle and label open the profile. Pagination
applies to both sides; the map shows only the current page. Old search URLs display
the full directory, so a hidden filter cannot omit venues. Missing or out-of-region
coordinates leave the card available without inventing a map position. The map
stays beside the cards on larger screens and stacks above them on phones.

The local outline is Finland from Natural Earth 1:110m Admin 0 v5.1.2, reduced to
five decimal places. It is a generalized geographic overview, not a navigation
map; small islands are omitted at this scale. Outline and markers use the same
equirectangular projection with longitude scaled at 65°N. No map tiles, external
runtime requests or additional libraries are used.

- [Original GeoJSON](https://github.com/nvkelso/natural-earth-vector/blob/v5.1.2/geojson/ne_110m_admin_0_countries.geojson)
- [Natural Earth public-domain terms](https://www.naturalearthdata.com/about/terms-of-use/)

`node --test tests/track-map.test.mjs` checks projection directions, missing
coordinates, marker positions and identities, and safe profile links.

## Data and collection

The additive `tracks` table stores an internal ID, unique Hippos code, minimized
venue observation and fetch time. Startup seeds 17 reviewed venues and backfills
existing meeting records once, offline. New calendar observations update tracks
in the same transaction as meetings. Unrecognized codes create separate profiles;
names are never used to merge venues. Existing racing records are unchanged.

IDs currently use `hippos-<exact code>`; they do not imply that another provider
uses the same identifier. Kuopio's observed Toto abbreviation `Ku` is retained
separately from Hippos `KU`. Other Toto mappings remain unverified in this catalog.
This feature does not change Toto matching or queue any external requests.

`hippos_analyst/track_catalog.json` holds curated names, addresses, official links,
source/check dates and licensed image metadata. Vermo's physical locality Espoo
is separate from Heppa's racing label Helsinki. Technical dimensions are currently
verified for Teivo only. Unknown dimensions and photos remain explicitly missing.
Coordinates come from Heppa and are checked for finite values and valid ranges.

Source observations retain only venue fields and their originating meeting date.
The most recently fetched observation wins (latest meeting date breaks ties).
It is not a reconstruction of historical venue changes. Track condition,
temperature, cancellation and event names remain on the meeting. Corrected
calendar membership removes obsolete meetings from profile history, but does not
delete the track itself. Today belongs to the upcoming date bucket; this does not
assert that today's races have not finished. Cancelled meetings remain labelled.

## API

- `GET /api/tracks?today=YYYY-MM-DD&q=...&offset=0`
- `GET /api/track?id=hippos-H&today=YYYY-MM-DD&period=history&offset=0`

Both endpoints read local data only. Search and period filtering precede paging;
pages contain at most 30 records. Only the selected meeting page expands race
lists. Missing venues return 404; invalid dates, periods and offsets return 400.
The browser supplies the Europe/Helsinki calendar date.

Restart the local server after updating Python sources; startup applies the
offline backfill. No dependency installation or network collection is needed.

## Images and sources

All seventeen track photos are bundled locally. Sixteen are from Commons, with
creator, year, original page, licence and resize/crop notice. Ylivieska uses the
photo published by Suomen Hippos, with publisher/source credit; no open licence
is asserted for that photo. All cards share equal row heights and a fixed-height
image area, including a same-size fallback for future tracks without photos. See
[image attribution](../hippos_analyst/web/images/README.md). External websites and
maps open only when clicked. Hippos directory photographs and logos were not copied.

- [Hippos track directory](https://www.hippos.fi/raviurheilu/raviurheilu-lajina/suomen-raviradat/)
- [Teivo technical facts](https://www.teivo.fi/radan-kayttajat/ohjeet-raviradan-kayttajalle/)

To enrich another venue, verify its exact code and source facts before editing the
catalog. Store image attribution and a reusable licence, bundle the file locally,
and add its exact asset path to the server allowlist. Do not infer licence rights
from an accessible image URL. The catalog is deliberately incomplete rather than
claiming coverage of every Finnish track.

## Verification

`tests/test_tracks.py` covers offline catalog availability, Finnish search,
identity separation, location differences, invalid coordinates, calendar
corrections, pagination, additive/idempotent backfill, freshness ordering,
validation, source credits and local HTTP/image delivery. The frontend regression
checks return context and view identity when switching tracks.

Initial verification on 25 October 2026: all 121 Python tests and 27 frontend logic tests
passed; JavaScript syntax and Git whitespace checks passed. Browser checks covered
directory search, Vermo/Teivo profiles, historical meetings, race navigation and
return links. At a 390-pixel viewport, body width remained 390 pixels and the
local photo loaded. The initial live archive exposed 17 profiles, 17 addresses, 17 valid
coordinate pairs and two photographs. No new Heppa/Toto requests were needed.

The map/photo layout revision passed 30 frontend tests and eight track tests,
including HTTP delivery of all 17 image assets. Browser checks at 1440px and
390px confirmed 17 photo cards with equal heights, one page heading inside the
map, no search input, and no horizontal body overflow. Old search URLs show all
17 tracks. Ylivieska's profile displays its local image with source credit.
