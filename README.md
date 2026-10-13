# Counting Flag Football

**[Results site](site/index.html)** (built by `make site`; CI publishes it to GitHub Pages) · [Participation memo](docs/methodology/counting-a-participant.md) · [Fan-acquisition memo](docs/methodology/flag-as-fan-acquisition.md) · [Decisions](docs/decisions/) · [Demo script](docs/demo_script.md) · [UI spec](ui-spec.md)

**How many fans does flag football create, how engaged and valuable are they, and how many can we contact?** This is a governed data platform for a **synthetic** global flag football
program that answers that question, and then shows how sure it is: the fans the programme added (an estimate with an interval, next to the naive count that is more than twice too big), what a fan
is worth, and how much of the engaged audience governance lets the organisation talk to. It started as "how many people play" and still answers that too. Five messy sources (a league CSV, a club API,
a federation workbook, school headcounts and a fan feed) go in; every claim is graded against an answer key the generator keeps. Python generates and loads; **SQL (dbt on DuckDB) is the showcase**.

**Status:** all 13 steps of the fan-acquisition rework are built; methodology **v2.0** (25 scorecard KPIs) is published for 2021 to 2025 and the restatement log is empty. The two methodology memos and the demo talking points are drafts for the owner to write, and the CI workflow has not yet run (no GitHub remote). The results site has six pages (overview, acquisition, value, audience, participation, trust) plus an appendix, a drive chart on the Acquisition page, and an original project mark; a build check refuses any image file, `<img>`, foreign inline SVG or foreign favicon, so no third-party logo can ship. [`fix-list.md`](fix-list.md) tracks what remains (the generator-side items are open).

> ## All data in this project is synthetic
> Every person, email and phone number is fake, generated from a fixed seed (42). The real equivalent is **minors' personal information**: children aged 5 to 17, their
> guardians' contact details, photo and marketing consent. That is why the project uses invented people: the modelling, privacy and governance patterns can be shown in public
> without exposing a real child. Every number below describes a generated population, not a real program.

## Architecture

```mermaid
flowchart LR
  S[Sources A to E<br/>CSV, JSON, XLSX, aggregates, fan accounts, events, consent] --> K[Contracts<br/>validated every build]
  K --> R[raw<br/>strings as-is]
  R --> ST[staging<br/>typed, flagged]
  ST --> I[identity<br/>blocking, Fellegi-Sunter,<br/>components]
  I --> F[facts<br/>counting rules C1 to C15]
  F --> M[marts<br/>KPIs, retention,<br/>bounds, fan status,<br/>funnel, acquisition,<br/>value, audience]
  M --> SH[shares<br/>by audience,<br/>small cells suppressed]
  SH --> W[results site]
  ST -.restricted.-> L[linkage schema<br/>households to fan accounts,<br/>guardians only]
  L -.aggregates only.-> SH
  G[(ground truth<br/>schema eval)] -.evaluation models only.-> M
```

## Results (synthetic data, 2021 to 2025; latest period shown)

| What | Result |
|---|---|
| **Fan accounts the programme added** (incremental, stacked market-launch comparison) | **1,264** (95% interval 897 to 1,630); truth 1,111. The naive count of net-new households is 939 linked (0.85x the truth) and 2,543 scaled by the link rate (**2.3x**) |
| **Addressable audience** (guardian opted in on at least one channel, December 2025) | **3,511 of 13,043** registered households (email 2,107, SMS 1,231, push 1,748; channels overlap) |
| **Consent gap** (active households with no opt-in at all) | **803 households, about 25% of the active**, worth about 96,360 in synthetic currency at the median monetized household's spend (an opportunity size, not revenue) |
| Fan lifetime value (36-month horizon, synthetic currency) | existing fans 387 (381 to 393), net-new 368 to 372 (352 to 386); 12-month survival 95% for existing fans, 89% for net-new |
| Value uplift after registering a child (existing fans) | +0.21 events per household-month (truth +0.18); net spend up about 1.1 per household-month (synthetic currency) |
| Fan engagement uplift after first registration (linked households) | naive +17.5% (0.99x the truth), matched difference-in-differences +22.6% (truth +20.5%) |
| Markets (46 synthetic) | 15 retention-and-engagement, 8 program-growth, 3 acquisition white space, 20 long-term build |
| Unique registered participants | 8,959 in 2025 (identity range 8,921 to 8,976, a 0.6% band) |
| Identity resolution, final matcher (`fs`, automatic merges) | precision 99.81%, recall 99.99%; **9 sibling/twin false merges (a finding, not yet fixed: ADR-008)**; 14,991 predicted vs 15,000 true people |
| Rules baseline vs probabilistic | rules recall 92.7% (16,044 predicted people, no sibling merges); literal Fellegi-Sunter `fs_naive` makes 213 sibling merges; the corrected `fs` makes 9 |
| One-year retention of entrants (Kaplan-Meier, censored) | 72.2%; counting age-outs as churn would report 37% for entrants aged 14 to 17 (truth 61%) |
| Household link rate (registration to fan account) | 36% overall; email links 99.98% precise, phone links 85.8% (UNLINKED means unknown: about 23% of unlinked households do have an account) |

Counts are **registered participants in onboarded sources**, not total participation; fan results describe **households linked to a fan account**. Details and caveats: the
[participation memo](docs/methodology/counting-a-participant.md) and the [fan-acquisition memo](docs/methodology/flag-as-fan-acquisition.md) (both prose still being written), and the [results site](site/index.html).
Governance sets the size of the marketable audience: nothing linked reaches marketing or media, so the audience is published as counts only (ADR-009).

## Design decisions

| ADR | One line |
|---|---|
| [001 Stack](docs/decisions/ADR-001-stack.md) | dbt-duckdb, with every DuckDB-specific function logged so a Snowflake port is a list, not a hunt |
| [002 Age cutoff](docs/decisions/ADR-002-age-cutoff-convention.md) | Age is age on December 31 of the season year |
| [003 Identity resolution](docs/decisions/ADR-003-identity-resolution.md) | Blocking plus Fellegi-Sunter in SQL; precision first, because a sibling merge is a privacy incident |
| [004 Participant ID stability](docs/decisions/ADR-004-participant-id-stability.md) | IDs are derived and stable across rebuilds; a persisted registry is the production step |
| [005 Counting rules](docs/decisions/ADR-005-counting-rules.md) | Rules C1 to C15 define who counts, once, in which country, at what age |
| [006 Privacy controls](docs/decisions/ADR-006-privacy-controls.md) | Audience column policy, small-cell suppression, pseudonymization; pseudonymous is not anonymous |
| [007 Publish and restatement](docs/decisions/ADR-007-publish-and-restatement.md) | Immutable snapshots; a changed published number needs a cause, a threshold and an owner |
| [008 Phase 4 scope and findings](docs/decisions/ADR-008-phase-4-scope-and-findings.md) | Config-driven window, contracts and a playbook, aggregate-only sources, and what Phase 4 found |
| [009 Household linkage governance](docs/decisions/ADR-009-household-linkage-governance.md) | Linking registrations to fan accounts is a governance decision; restricted zone, aggregates out. Decided by Anna (2026-10-02) |
| [010 Fandom outcomes](docs/decisions/ADR-010-fandom-outcomes-design.md) | Matched difference-in-differences, designed before the truth was read and never tuned to it |
| [011 Acquisition measurement](docs/decisions/ADR-011-acquisition-measurement-design.md) | Fan acquisition is measured at market level from staggered launches: stacked cohort comparison against not-yet-treated markets, not a pooled two-way regression |

## Phase 5: data quality under privacy constraints (in progress)

Participation data is thin and messy, and the obvious fixes (collect more, buy enrichment, share more) are the ones privacy rules block. Phase 5 asks how to fix it anyway,
for two audiences: a privacy lead (minimization, purpose limitation, retention) and a club analytics lead (what can I trust in my territory). Status: **step 1 of 7, the source feeds.**
Phase 5 is an isolated scope: its feeds are derived from the existing true US youth registry with their own random stream (`phase5.seed_offset`), so no Phase 1 to 4 file or published number changes.
The feed names, shapes and consent wordings are **assumptions** made for the demonstration; none describes a real NFL, RCX, vendor or club system.

`make p5-feeds` writes `data/raw/p5/<feed>/` and lands the files in `raw.p5_<feed>` as strings; ground truth goes to `eval` only. Every rate is in `config/generation.yaml` under `phase5`.

| Feed | Shape (assumed) | Defects injected on purpose |
|---|---|---|
| `matrix_export` | cleanest: league id, DOB, parent email, ZIP, consent version and timestamp | missing ZIP, ZIP+4, consent timestamp or version missing, no consent record, stale leagues (no latest season) |
| `vendor_reg_a` | a third-party platform: different names, free-text league name, DOB as text | league name variants (only 85% in the alias map), four DOB text formats, impossible DOB, invalid or missing ZIP, no consent timestamp |
| `vendor_reg_b` | age group only (`U10`), no DOB, combined parent name | missing age group, invalid or missing ZIP, no consent record |
| `pop_warner_feed` | association-centric, tackle and flag mixed | tackle rows to filter out; an association is not a league (a quarter run two flag leagues, and the code that tells them apart is often blank); no consent field beyond a waiver |
| `pal_chapter_csv` | manual spreadsheet uploads | blank columns, typos in names and emails, duplicated rows, two-digit-year DOBs, consent in five wordings or none |
| `school_program` | roster only: school, grade, name | no parent contact, no ZIP, no DOB (grade only), missing grade |

Across feeds: the same child in two feeds with name variants, one parent email shared by siblings, some households using two parent emails, case and whitespace noise on emails, late submissions,
and leagues that never sent their latest season. Seasons are 2024 and 2025; the Phase 1 to 4 window is not extended.

## If this were real

- **Snowflake and dbt Cloud.** The dbt is written to be portable (DuckDB-only functions are listed in ADR-001); real warehouse roles would replace the policy that a build check enforces.
- **Orchestration.** Scheduled loads, freshness checks and alerting; today everything runs from `make`.
- **Partner contracts as a governance process.** A contract here is a YAML file validated on every build; a real one is signed with the partner, owned by a named role and renegotiated when the data changes (see the [playbook](docs/playbook/onboard-a-source.md)).
- **A persisted participant-ID registry.** IDs here are derived; production needs a registry so that a merge or split is an event, not a rebuild (ADR-004).
- **Real access control.** Column policies per audience, with database roles, audit logging and an access review (ADR-006).
- **Real market launches are not random.** Markets here launch in an order unrelated to their fan potential, which is what makes the incrementality estimate credible; real launches target promising markets, so ADR-011's comparison would need pre-trends per market and a sensitivity analysis.
- **Attendance data.** A registration is not proof someone played. Counting attendance would change every definition here.
- **Real data would score lower.** The synthetic population has phone numbers that never change and one nickname list; identity resolution on real data is harder, and the truth column would not exist.

## Run it

Requires [`uv`](https://docs.astral.sh/uv/) and `make`. Python 3.12 is fetched automatically. pytest runs on four workers; the CI job allows 25 minutes.

```bash
make setup        # install dependencies, create dbt/profiles.yml from the example
make all-phases   # the supported full build, from an empty checkout: about 8 minutes, most of it the test suite
make site         # build the results site into site/
python3 -m http.server 8000 -d site   # then open http://localhost:8000
```

`make all-phases` generates the data, loads raw, ground truth and published snapshots, validates the contracts, runs every dbt model and test, runs pytest, and runs the build
checks: ground-truth isolation, aggregate lineage, share policy and participant-ID stability. Any failure stops it.

| Command | What it does |
|---|---|
| `make generate` / `make load` / `make load-eval` | write the synthetic files; land them in `raw`; load the quarantined ground truth into `eval` |
| `make contracts` | validate every source contract against the raw tables (an `ERROR` fails the build) |
| `make fan-status` / `make funnel` / `make acquisition` / `make fan-value` / `make audience` | run one fan analysis and print its comparison with the truth (also `make retention`, `make linkage`, `make fan`) |
| `make docs` | regenerate the data dictionary, metric catalog and access policy |
| `make publish YEAR=2025` | write an immutable snapshot of that year's scorecard under the current methodology version (refuses unless every test passes, about 5 minutes per year; never part of `all-phases`) |
| `make site` | build the results site from `scripts/build_site.py` and `site_src/` (templates, styles, JS); fails if a chart would compute a number in the browser, or if the site contains an image or an SVG that is not the project's own |

Explore `warehouse/flag.duckdb`:

```sql
select * from share_exec.share_exec__participation_bounds;       -- the headline with identity bounds
select * from quality.dq_summary;                                -- observed vs configured defect rates
select * from retention.mart_retention_survival;                 -- Kaplan-Meier with Greenwood intervals
select * from evaluation.eval_acquisition;                       -- incremental vs naive vs truth
select * from share_exec.share_exec__addressable_audience;       -- audience and consent gap (counts only)
```

## Principles

1. **SQL is the showcase.** Python generates and loads; cleaning, counting, matching and analysis are SQL.
2. **Raw is immutable.** Strings in, strings stored.
3. **Deterministic.** One seed; two clones produce byte-identical files.
4. **Messiness is specified.** Defects are injected at exact counts, so detection can be checked.
5. **Ground truth is quarantined.** It lives in schema `eval` and is read only by `models/evaluation/`; a build check enforces it.
6. **Never guess.** Ambiguity becomes NULL or `U` and is flagged. Consent not captured is NULL, never FALSE.
7. **Say how sure you are.** Identity bounds, censoring, confidence intervals, and a comparison with the naive answer next to every estimate.
8. **Never tune to the truth.** Estimator designs are fixed before the answer key is read; where an estimate misses, the result says so (ADR-010, ADR-011).
9. **Guardians only, and never to marketing.** Every fan account holder is an adult; household-linked data leaves the restricted zone only as suppressed aggregates, and nothing linked reaches marketing or media (ADR-009). Unlinked means unknown, not non-fan.

## Documents

[Participation memo](docs/methodology/counting-a-participant.md) · [Fan-acquisition memo](docs/methodology/flag-as-fan-acquisition.md) · [Changelog](docs/methodology/CHANGELOG.md) · [Metric catalog](docs/metrics.md) · [Access policy](docs/access_policy.md) ·
[Data dictionary](docs/data_dictionary.md) · [Source inventory](docs/source_inventory.md) · [Onboarding playbook](docs/playbook/onboard-a-source.md) ·
[Restatement examples](docs/reports/restatement_demo.md) · [Earlier build notes (phases 1 to 3)](docs/build_notes_phases_1_to_3.md)
