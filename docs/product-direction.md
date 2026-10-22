# Product direction

The primary goal is to present the racing information clearly, with few clicks
and effective use of the screen. This takes priority over prediction features.
The intended user is a racer or racing enthusiast looking for a meeting, a field,
a result, or a horse's relevant history.

## Working principles

- Put the racing data before branding, navigation and archive statistics.
- Keep meeting, race and horse context together. Avoid a new page when an inline
  detail can answer the question without losing the current field.
- Make frequent actions visible: date/track selection, race changes, result order,
  horse history and returning to the previous view.
- Use desktop width for comparison. On narrow screens, keep controls reachable
  and scroll wide tables independently instead of shrinking their text.
- Show useful information with consistent labels and units. More information
  means relevant, understandable fields; it does not mean dumping raw API codes.
- State what has been collected and when. An incomplete field, a scratch, a missing
  result and a genuine zero are different states.
- Preserve filters and selected races in the URL. Browser back, refresh and links
  opened in a new tab should remain useful.
- Default to the most relevant available meeting. Do not make the user complete
  a selection wizard before seeing a racecard.

## Current interaction targets

| Task | Current behavior |
| --- | --- |
| See a race after opening the calendar | Automatically opens today's first available meeting, then the nearest upcoming meeting, or latest past meeting |
| Switch to any visible race | One click on its number in the meeting list |
| Inspect a horse's collected starts | One click on its name expands history inside the racecard |
| Return from horse preview | Close it in place, with keyboard focus returned to the horse |
| Change week | One click; preserves the track filter |
| Change track | Selecting a track applies the filter immediately |
| Browse from a phone | Meeting strip above the race; selecting a race moves to that racecard |
| See newly collected data | Refresh-view button reads SQLite only |

## Next decisions, driven by real use

After a larger historical sample is available, evaluate which additional columns
help a racer compare runners: recent form, verified equipment changes, records,
distance/lane and eligibility. Keep source provenance and code interpretation
explicit. Prioritize favourites, field comparison and calendar export according to
actual use. Odds, weather and predictions are complementary views after the core
race and horse browsing experience works well.

Verify changes with realistic long names, trial/pony races, upcoming fields,
results, missing data, keyboard use, desktop and mobile widths. Record actual
checks in [UI verification](ui.md), rather than claiming universal usability.
