# API research

Investigated 22 October 2026. Distinguish successful HTTP access from a documented
reuse licence or a guarantee that an endpoint will remain available.

## Hippos / Heppa

- [Legacy Heppa](https://heppa.hippos.fi/heppa/app) serves Apache Tapestry assets
  and jQuery 1.6.1. The displayed application version was 3.1.6, built 15 October
  2026. Tapestry indicates a Java application; the deployment and database were
  not established. Horse search submits a Tapestry form rather than a JSON query.
- [Mobiiliheppa](https://heppa.hippos.fi/mobiili/) uses React 16.14.0 and Webpack.
  Network inspection and its published JavaScript established the JSON base URL:
  `https://heppa.hippos.fi/heppa2_backend`.
- Search and calendar requests also succeeded without browser cookies or login.
- [robots.txt](https://heppa.hippos.fi/robots.txt) returned a general
  `User-agent: *` / `Disallow: /` rule. We have not obtained Hippos permission or
  found an open-data licence. The project owner explicitly chose to proceed with
  bounded private collection, stopping on objections, access denials or limits.
  This records that decision; it does not represent provider approval. An approved
  API arrangement or bulk export remains preferable for a broad historical copy.
- `isFreeToPublish` and `publishFree` are API data flags, not evidence of a blanket
  licence to archive or republish the database.

### Observed endpoints

All paths below are relative to the base URL. Calendars, race lists, fields and
horse profiles are implemented. Other paths were observed in browser traffic.

| GET path | Response / purpose |
| --- | --- |
| `/race/search/{from}/{to}/` | Array of `{raceDate, events: [...]}` calendars |
| `/race/{date}/{track}/races` | Array of wrappers containing a `race` object |
| `/race/{date}/{track}/start/{number}` | Complete participant/result array for one race |
| `/race/{date}/{track}` | Meeting details |
| `/search/all?term=Viesker&limit=5` | Object with `horses`, `persons`, `tracks` |
| `/horse/{id}` | Horse profile |
| `/horse/{id}/stats` | Totals, annual statistics and monte statistics |
| `/horse/{id}/starts?pageNumber=1&pageSize=10&onlyResults=false` | Paginated history array |
| `/advanceCompetition/horse/{id}/competitions/future` | Upcoming advance-payment competitions |

The mobile bundle additionally contains pedigree and offspring endpoint strings;
those were not validated as live calls and are not implemented. The current
[pedigree feature](horse-relationships.md) instead follows verified sire/dam IDs
from `/horse/{id}`, within a two-generation collection bound. Owner/breeder names
come from this profile; no party IDs were present in the checked responses.

### Historical schema probe

For 2025-10-22, the calendar returned Helsinki/Vermo, track code `H`. Its race list
contained 11 races. Start 1 returned nine participants. These observations ground
the importer; they do not establish completeness for all years.

- Calendar events include `date`, `trackCode`, `finnishTrack`, `startTime`,
  `trackCity`, `canceled`, and sometimes `trackCondition` and `temperature`.
- Race list items wrap fields in `race`, including string `startNumber`,
  `baseDistance`, `startForm`, `eventType`, `plannedTime` and `status`.
- Participants include `programNumber`, string `horseId`, `horseName`, driver and
  trainer identifiers, equipment, `placing`, `kilometerTime`, `price`, and `absent`.
- A kilometre time can be `1.17.8`, with a display variant such as `17,8`. Preserve
  source strings until units and exceptional result codes have a tested parser.
- Identifiers can exceed JavaScript's safe integer range. Store and expose them
  as strings. Placings are not universally integers; ties and disqualifications
  need explicit modelling.
- Current lifetime totals and comments retrieved after a race are not evidence
  of what was known before that race.

## Veikkaus Toto: supplementary source

A bounded importer is now implemented; see [Toto operations and verification](toto.md).
The assessment below records the evidence before implementation.

[Official API documentation](https://github.com/veikkaus/sport-games-robot)
describes read-only paths under `https://www.veikkaus.fi/api/toto-info/v1`:

| Path | Purpose |
| --- | --- |
| `/cards/today`, `/cards/future`, `/cards/active` | Meeting discovery |
| `/cards/date/{YYYY-MM-DD}` | Historical date |
| `/card/{cardId}/races` | Races |
| `/race/{raceId}/runners` | Participants and form |
| `/race/{raceId}/pools`, `/card/{cardId}/pools` | Pools |
| `/pool/{poolId}/odds` | Odds (documented, not live-verified in this investigation) |

The documentation specifies `X-ESA-API-Key: ROBOT` for automated clients. A
current Finnish meeting (Forssa, 2026-10-22), its races and runners were verified
without account credentials. The 2025-10-22 calendar also returned a Finnish
meeting; historical races/runners and archive depth remain unverified.

Runner fields include previous starts, driver statistics and equipment, but also
irrelevant information such as owner hometown and vaccination data. A future
importer must use an explicit field allowlist. Check money units independently:
Veikkaus and Hippos should not be assumed to encode prizes identically.

The [reference-software licence](https://github.com/veikkaus/sport-games-robot/blob/main/Lisenssisopimus.md)
is restrictive and concerns the provided code, not a general open-data licence.
Do not copy that implementation into this project. Long-term storage/reuse terms
and provider identity mappings need further investigation before integration.
The separate [developer portal](https://dev.developer.api.veikkaus.fi/get-started)
describes approved accounts/API keys; do not assume that is the same access model
as these older documented public Toto endpoints.

### Integration value assessment — 25 October 2026

Rechecked the official Toto documentation and the current Hippos field allowlists
and SQLite records. No Veikkaus collection was started during this assessment.

- **Highest distinct value: timestamped market observations.** The documented
  pool and odds endpoints could support pre-race odds snapshots and a market
  baseline for prediction experiments. Odds response shape, availability after
  closure and historical depth still need live validation. Do not assume a
  historical date endpoint supplies historical odds movements.
- **Useful secondary value: runner form and race-day reconciliation.** The earlier
  runner probe found previous starts, driver statistics and equipment. These may
  fill gaps in our small archive, but their coverage, timestamps and overlap need
  comparison before import. Faster or more complete updates are not established.
- **Lower priority: betting-product context.** Documented meeting/pool data covers
  products and bonus/jackpot information. This is optional race context, with less
  value for the current calendar/profile experience than richer racing records.
- **Existing Hippos data should be surfaced first.** Of 3,799 stored entries,
  2,398 have a non-null `winOdds` value; the other 1,401 have `winOddsStr="-"`.
  Shoeing and sulky codes are also already stored. Their source-code meanings and
  odds observation timing need verification before labels or model features are
  assigned. Stored odds are not a time series or proof of a pre-race observation.

Recommended scope is a small optional enrichment importer for matched Finnish
meetings, preserving Hippos as the primary archive. Keep provider IDs and
observation times separate. Match date, mapped track and race number, then verify
runner identity; never merge horses by name alone. Retain disagreements with
provenance instead of silently replacing Hippos values. Validate units and an
explicit field allowlist before storage. Preserve existing stop/budget policies.

For prediction work, collect observations prospectively and enforce a pre-race
cutoff: later results, final odds and subsequently updated form must not enter an
earlier prediction's features. Start with a few scheduled observations for selected
races, rather than continuous broad polling. The official documentation advises
against odds polling more often than once a minute; that is not a reason to
increase our existing conservative request budget. Storage/reuse terms remain an
open integration question. This is a recommendation, not an implemented feature.

## Other providers

- [ATG official partner feeds](https://www.swedishhorseracing.com/for-partners/offer-and-solution/):
  AIS, XML and historical race-field exports, offered to partners. Relevant to
  Swedish trotting; Finnish coverage and private access terms are not established.
- [PGI harness coverage](https://www.pginternational.co.uk/markets/harness):
  advertises Finland among covered markets, including 19 tracks. Partnership
  offering, not an established free open API for this project.
- [The Racing API](https://www.theracingapi.com/data-coverage): published coverage
  concentrates on thoroughbred racing; not an established Finnish trotting source.
- [FMI open data](https://www.ilmatieteenlaitos.fi/kysymyksia-avoimesta-datasta):
  observations and forecasts. [CC BY 4.0 and service limits](https://www.ilmatieteenlaitos.fi/avoin-data-lisenssi)
  make this a good future weather source. Attribute the source, cache weather by
  track/time, retain forecast issue time and distinguish forecasts from observations.

No comprehensive, clearly open-licensed replacement for Finnish trotting records
was established. Do not interpret third-party API wrappers as provider permission.
