# Collection expansion — 10 November 2026

The owner approved faster growth, endpoint auditing and horse photos, while
declining recurring checks of old races and completed profiles.

## Active policy

- **10-second minimum spacing, 5,000 combined attempts per UTC day**, one shared
  lock and persistent ledger. Existing attempts count. This local cap is not a
  provider-granted allowance; refusals, rate limits, redirects, schema errors and
  failed jobs still stop collection.
- **100 new participant profile roots per Helsinki day**, ten at a time after
  pending profiles/photos finish. The count survives restarts; a legacy same-day
  five-root marker is charged as five. Ancestors stay bounded to two generations
  and never become automatic roots.
- Recent calendar/list/field checks: today/tomorrow after one hour, previous three
  days after six hours, days +2 through +7 after 24 hours. Per-pass allowances remain
  20 recent, ten profile/photo and ten history requests. Queues and budgets can
  delay observations; these intervals are eligibility ages, not a live-feed SLA.
- No recurring older-race corrections or completed-profile refreshes. No extra
  Toto polling, Windows service, sign-in hook or Codex automation.

Successful fields replace the entire current entrant list atomically. Scratches
remain marked absent; removed entrants disappear from the current field. Old
snapshots remain. Existing forecast signatures invalidate changed fields and
the local forecast watcher recalculates eligible upcoming predictions.

## Endpoint inventory and retained data

`python -m hippos_analyst audit-fields` lists observed names, retention decisions
and first/last observations across calendar, race-list, runner and profile JSON,
including nested keys. It stores no excluded values and is not an assertion that
every possible upstream field has already been observed.

Newly retained: meeting classifications/special-event names; race names, levelling
headers, game-type lists, TV links and intermediate times; horse age, records,
birth country, colour, home track, registration IDs/status, trainer ID/name,
qualification points and reviewed breeding-index fields; horse photo metadata.
Current profile/career values do not enter historical prediction features.

Explicit exclusions remain comments/comment timestamps/owner city, medical and
chip/laboratory identifiers, DNA/vaccination details, profile free text, birth
place, extra renter/groom roles, breeding union, victory song, redundant formatted
birth date and parent registration numbers. Race-level photos and the unverified
`totoResults` wrapper remain inventoried but unimported; the tested wrapper was
empty. Horse photos are implemented; finish-line photos are not. These boundaries
are explicit rather than a claim to retain everything.

Parser versions: calendar 2, races 2, runners 4, profiles 3. **820 old calendar,
race-list and profile jobs were queued once** to recover new metadata/photos,
using successful observations with older parser versions. Existing failed jobs
were not included. This bounded upgrade does not introduce periodic refreshing.
The earlier runner repair continues; old snapshots are never relabelled.

## Cached horse photos

A live profile advertised the verified path
`https://heppa.hippos.fi:443/heppa2_backend/images/horse/photo/{id}`. Only HTTPS on
that host/port with the exact profile horse ID is accepted; query strings,
credentials, redirects and unrelated URLs are rejected. `horse_photo` jobs share
profile allowance, worker lock, ledger, spacing and cap. Completed photos are not
repeatedly fetched; existing curated photo assignments are preserved.

Responses must be bounded JPEGs (8 MiB, validated dimensions). Bytes enter the
existing local store and are served at `/media/{hash}.jpg`; browsing never fetches
Hippos media. The UI identifies Hippos as the source without inventing a
photographer or CC licence. This remains a private local project; a source URL
does not establish public redistribution rights.

First live photo: **Igor Du Bas Bosq**, ID `102070772246207535`. Its ordinary horse
page displays the cached image, source label and linked racing/relationship data.

## Verification

**173 Python and 37 JavaScript tests passed**, including 5,000-attempt accounting
across restarts, ten-second spacing, bounded profile batching/day counts, recent
refresh ages, scratches/removals, field auditing, photo identity/URL checks,
metered caching, no repeated photo fetch and malformed-image stops. Existing
refusal/cooldown/lock and prediction tests pass. Browser verification showed the
real cached photo and no console errors.

Live verification caught a list-valued `totoTypes` that the first new parser
expected to be scalar. Collection stopped without storing it. The parser was
corrected to validate string lists and regression-tested. Only the diagnosed
`/race/2026-11-09/L/races` job was explicitly retried after inspection; it succeeded.
The failed request and attempts remain in the ledger. No provider stop was cleared.

Upgraded collector PID 43248; local server PID 45996 on port 8766. The forecast
watcher is unchanged. See [backfill checkpoints](backfill.md) and the worker log.
