# Runner-distance and race-type audit — 10 November 2026

Read-only audit of `data/hippos.sqlite3`; no collection, parsing or UI changes.
Each query ran in a SQLite read transaction. The audit used `browse.visible(Archive)`
to restrict entries to the latest successfully observed calendar/race-list membership,
then grouped by date, track and race number. Scratched entries remain included because
the racecard displays them. Distances are the runner's `data.distance`, compared with
the race's `distance` / source `baseDistance`; positive numeric values were required.

## Observed archive

3,212 populated race cards and 31,543 entries, with represented race dates spanning
2025-10-22 through 2026-11-16. This span does not imply complete historical coverage.
The running collector can change these counts after the audit snapshot.

| Source start form | Populated cards | One runner distance | Multiple runner distances |
| --- | ---: | ---: | ---: |
| TASOITUSAJO | 1,817 | 96 | 1,721 |
| RYHMALAHTO | 1,395 | 1,394 | 1 |
| Total | 3,212 | 1,490 | 1,722 |

No missing/nonpositive/noninteger runner distances were found in these entries.
Seven single-distance cards have a runner distance different from the race header's
base distance. Therefore only 1,483 cards meet the strict hide-column condition:
every listed runner has a known distance equal to the header distance.

Examples:

- Lahti/Jokimaa, 2026-11-09 race 1: all ten listed horses have 2140m, including
  the scratched horse. The header also says 2140m.
- Pori, 2026-11-10 race 1: five entries have 2100m and seven have 2120m,
  including one scratched entry in the latter group. Header distance: 2100m.
- Jyväskylä, 2026-09-17 race 21: source form RYHMALAHTO, type KOE,
  eventType YHDISTETTY. Four entries have 2140m and three have 2180m.
  This combined qualification field is an exception to a start-form-only UI rule;
  its exact starting arrangement was not independently established.
- Across 155 handicap cards, 513 entries are 20m below the header's base distance.
  Do not assume baseDistance always equals the smallest runner distance or silently
  replace runner distances with it. The audit did not establish each race's allowance.
- Seven uniform fields differ from baseDistance: track code PO on June 17
  races 8/11 and September 13 race 4; Vieremä July 3 race 6, July 24 race 8,
  August 14 race 6; Kouvola August 22 race 4. Preserve their runner values.

## Meaning and implemented UI behavior

Hippos's [rules effective 1 July 2026](https://www.hippos.fi/tiedostot/ravikilpailusaannot/),
sections 24.1–24.2, distinguish handicap distances in 20m steps from equal-distance
group races. Handicap criteria and allowances are defined in the race conditions.

Distance remains in the underlying records and model. Following the audit, the UI
now always keeps the column for TASOITUSAJO. For other start forms it omits the
column only when every displayed distance is known and equals the header; differing,
missing or inconsistent values keep the column. Scratched entries are included in
this decision. The uniform group-race distance stays in the race header.

`PAIKALLIS` comes from the runner's `startType`; it means **Paikallisravit**.
Section 23.3 of the same rules describes this official race category separately
from practice races (23.4) and qualification races (23.5).
The audit found 1,713 entries with that source type. Que Tal's May 23 and June 5/6
starts, and Global Bam Bautin's August 7/September 5 starts, provide examples from
the pictured recent-form strips.

`recentForm()` falls back to the raw source code when the Finnish `types` map has
no entry. PAIKALLIS lacked a mapping at audit time. It is now translated as
**Paikallisravit** in expanded history and other detailed views, and suppressed
in the quick-form strip. Qualification and other non-Toto labels remain in that
strip; they distinguish materially different kinds of starts. No source records,
form results or prediction features were changed.

This audit also observed 25 OPETUS entries; that code still lacks a direct mapping,
despite the existing OPETUSLAHTO label.

Verification: 38 frontend tests passed, including uniform/group/handicap fields,
mixed and scratched-runner distances, header disagreement and missing values.
Browser checks covered Pori's handicap field, Jokimaa's uniform field and the
Jyväskylä combined qualifier exception. Expanded Que Tal history shows
Paikallisravit while the quick strip does not; sorting preserves the expansion
and the correct dynamic column span. Mobile expansion fits without document
horizontal overflow.
