# Hippos Analyst

A private educational Finnish harness-racing project. The first implementation
collects public Hippos calendars, race lists and participants/results into local
SQLite, with a resumable queue and conservative request limits.

Requires Python 3.11+; no third-party dependencies. Includes a Finnish local web
UI for the calendar, racecards/results, horse search and collected horse history.
The calendar shows meetings beside the selected race, with direct race links and
horse history that expands in place. Prior form is visible beside runners; Omat
hevoset saves browser-local shortcuts and upcoming entries. Aineiston kattavuus
shows which dates and fields have been collected. See [product direction](docs/product-direction.md).

```powershell
python -m hippos_analyst serve
```

Open [the local UI](http://127.0.0.1:8765). Browsing never contacts Hippos; run the
collector separately to add or refresh data. Use `--port 8766` if needed, or
`python -m hippos_analyst --db data/another.sqlite3 serve` for another archive.
There is no frontend build or package-install step.

```powershell
python -m hippos_analyst seed --from 2025-10-22 --to 2025-10-22
python -m hippos_analyst run --max-requests 3
python -m hippos_analyst status
python -m hippos_analyst calendar --from 2025-10-22 --to 2025-10-22
python -m hippos_analyst race --date 2025-10-22 --track H --number 1
```

The sample imports one day, its meeting's race list and one race field. Remaining
fields stay queued. `seed` alone does not make network requests. Defaults: one
worker, 15 seconds between requests, 25 requests per run and 500 per UTC day.

Read [collection operations](docs/collection.md) before expanding collection,
including the recorded Hippos robots restriction and persistent stop behaviour.
The local database is ignored by Git. This workspace has a bounded scheduled chat
automation; see [the active policy and checkpoint](docs/backfill.md). Cloning the
repository does not install that automation.

[Documentation index](docs/README.md) · [API findings](docs/api-research.md) ·
[Architecture](docs/architecture.md) · [Roadmap](docs/roadmap.md)

```powershell
python -m unittest discover -s tests -v
node --test tests/ui.test.mjs
```

Node.js is only needed to run the frontend logic tests. See [UI and verification](docs/ui.md).
[Veikkaus Toto enrichment](docs/toto.md) is available for explicitly selected races.
Weather integration and prediction models remain planned.
The software licence does not grant rights to the upstream datasets.

[Latest product changes and verification](docs/product-improvements-2026-10-22.md)
