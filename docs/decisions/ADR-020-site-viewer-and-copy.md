# ADR-020: Site viewer, plain-language copy and chart fixes (Phase 5.1)

- **Status:** in progress (written during the build; finalized at the last step).
- **Numbering (a deviation from the handover).** The handover calls this ADR-017; ADR-017 is "Retention versus deletion", so this is **ADR-020**.
- **Synthetic data.** Every number on the site describes a generated population.

## Context
Anna reviewed the built Data quality and Club markets pages (printed to PDF, 2026-10-14). Several charts were broken, the pages were dense, and the captions were written for analysts. The next audience is a privacy/compliance lead and a domestic clubs / marketing / analytics lead.

## Pre-flight findings (2026-10-14)
- **Library and pipeline.** Charts are Vega-Lite 5 specs (via vega-embed, from the jsdelivr CDN) that `scripts/build_site.py` and `scripts/site_phase5.py` write into the page as JSON; `site_src/site.js` embeds them. Captions are built in `chart_block()` from `shows` / `doesnt` / `question` / `lens` strings in the Python chart definitions. Datasets are SQL exported to `site/data/*.json`; a spec may only map fields to marks.
- **Baseline (before).** Measured with Playwright driving the installed Chrome (`scripts/site_shots.py`; screenshots and `pages.csv` in `docs/reports/site_baseline/`): the Data quality page is 271,211 px tall because the Pareto chart is 268,183 px tall, and prints to **161 A4 pages** (Anna's PDF counted 198 on her paper size). The Club markets page overflows horizontally by 2,363 px at 1440 px. Every other page prints in 1 to 4 pages.
- **Playwright.** The handover assumes a pre-installed Chromium. This machine has none, so Playwright is added as a dev dependency and drives the installed Google Chrome (`channel="chrome"`); nothing is downloaded. GitHub's ubuntu runners ship Chrome, so the same call works in CI.
- **Duplicated sources? No gap; labelling only.** The heatmap lists 11 sources: the five original (`US_LEAGUE`, `CA_CLUB`, `INTL_FED`, `SCHOOL_AGGREGATES`, `FAN_ENGAGEMENT`) and the six channel feeds. The feeds are separate source systems (own raw table, own contract), not sub-channels of the US league, and `school_program` (a roster export, one row per student) is not `SCHOOL_AGGREGATES` (program headcounts, no people). ADR-013 decided this on purpose: the feeds are scored but **not counted** because they describe the same children as `US_LEAGUE`. So there is no reconciliation gap and no model change; the site only needs to label and group them (original sources / new intake channels) so the relationship is visible. `FAN_ENGAGEMENT` is not a registration source and is grouped apart.
