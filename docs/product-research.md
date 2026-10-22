# Product research — 22 October 2026

Primary-source research by one agent; no user interviews or competitor accounts.
These patterns inform decisions, not claims of proven demand for this project.

| Source | Relevant pattern | Decision for Hippos Analyst |
| --- | --- | --- |
| [ATG: start-list functions](https://atg-extern.kb.kundo.se/guide/ny-vy-pa-startlistan-faq) | Compact mobile fields, configurable information, contextual horse details | Keep field comparison central; show short prior-form context without opening every horse. Preserve readable mobile scrolling |
| [ATG: start watching](https://atg-extern.kb.kundo.se/guide/startbevakning-vad-ar-det?category=hast) | Saved horses are collected in one place with upcoming starts | Add local saved-horse shortcuts and upcoming entries. Do not introduce betting, accounts, email/SMS or claims of complete entry coverage |
| [Svensk Galopp: application guide](https://www.svenskgalopp.se/om-oss/om-webbplatsen/guide-till-galoppappen/) | Calendar-to-start-list/result flow, horse shortcuts and start watches | Preserve integrated calendar/field navigation and make returning to horses easy. Swedish archive depth does not establish Hippos depth |
| [Racing Post: free racecards](https://www.racingpost.com/racing-post-plus/everything-you-need-in-one-place-courtesy-of-our-free-racecards-aegm63U6deMV/) | Recent form stays close to each runner, with details on demand | Use compact collected-form entries and retain expanded details. Do not imitate proprietary ratings, odds or unverified performance claims |

The relevant standard is task continuity and useful comparison, not visual mimicry.
The retained green/neutral race-sheet design and Finnish terminology belong to
this project. Native controls, explicit missing values and visible source dates
take priority over decorative redesign. No competitor code or datasets were copied.

## First wave decisions

1. Earlier form belongs in the field. It means at most five visible collected starts
   **strictly before the selected meeting's date**, newest first. Exclude the whole
   selected day because reliable cross-meeting event order is not established.
   Do not call it a horse's complete career, a prediction, or an as-of backtest.
   Revised historical source snapshots may have been collected later.
2. Saved horses belong to the local browser, keeping the archive read-only and
   avoiding accounts. A complete saved list must support removal, empty state,
   persistence failures, reload, and upcoming-start discovery.
3. Coverage should answer what is present, pending, incomplete or stopped.
   A count of entries or calendar dates is insufficient evidence of completeness.

Alternatives considered: an analytics dashboard would emphasize uncertain sample
aggregates; a separate form-analysis page would fragment the main race journey;
a wholesale visual replacement would discard a working contextual layout. Select
incremental, connected improvements to the operational workspace instead.
