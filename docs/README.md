# Hippos Analyst documentation

This is a private educational project for browsing Finnish harness racing and,
later, testing predictions. Keep decisions, API evidence and operational changes
in this directory alongside implementation changes.

- [API research and sources](api-research.md): observed contracts, alternative feeds and uncertainties.
- [Horse and people photos](photos.md): reviewed Commons imports, local image storage, attribution and initial coverage.
- [Veikkaus Toto enrichment](toto.md): access, historical evidence, bounded observations and linked UI.
- [Track profiles](tracks.md): venue identities, curated facts, licensed images and linked meeting history.
- [Collection and operations](collection.md): commands, limits, pause behaviour and refreshes.
- [Active backfill policy and progress](backfill.md): slow scheduled continuation, coverage frontier and stop rules.
- [Archive growth verification](archive-growth.md): paged calendars and the 100,000-horse fixture.
- [Architecture and data](architecture.md): SQLite, snapshots, identifiers and data boundaries.
- [Project roadmap](roadmap.md): useful UI first, then honest prediction experiments.
- [Local UI and verification](ui.md): run commands, user flows, data semantics and checks.
- [Trainers, drivers and relationships](people.md): searchable people, linked profiles, verification and next data areas.
- [Owners, breeders and pedigrees](horse-relationships.md): verified profile contract, bounded discovery, linked UI and growth tests.
- [Product improvements and verification](product-improvements-2026-10-22.md): form, saved horses, coverage, final review and limitations.
- [Product research](product-research.md): first-party patterns and decisions.
- [Product direction](product-direction.md): fewer clicks, useful density and racing context.
- [End-to-end audit, 22 October 2026](audit-2026-10-22.md): verified findings, reproductions, checks, and final collection counts.
- [Audit fixes and verification](audit-fixes-2026-10-22.md): all eight findings resolved, regression coverage, and before/after performance.

The implementation includes a bounded Hippos collector, local command-line reader
and Finnish web UI, plus optional Veikkaus Toto enrichment. Weather and prediction models remain planned.
A bounded scheduled chat automation continues the backfill; see the operating policy above.
