# ADR-020: Site viewer, plain-language copy and chart fixes (Phase 5.1)

- **Status:** accepted for the build (2026-10-15). Two points are Anna's to decide and are marked OPEN: the control-limit method and the club market names. The copy in `site_src/copy/charts.yml` is a draft awaiting her review.
- **Numbering (a deviation from the handover).** The handover calls this ADR-017; ADR-017 is "Retention versus deletion", so this is **ADR-020**.
- **Synthetic data.** Every number on the site describes a generated population.

## Context
Anna reviewed the built Data quality and Club markets pages (printed to PDF, 2026-10-14). Several charts were broken, the pages were dense, and the captions were written for analysts. The next audience is a privacy/compliance lead and a domestic clubs / marketing / analytics lead.

## Pre-flight findings (2026-10-14)
- **Library and pipeline.** Charts are Vega-Lite 5 specs (via vega-embed, from the jsdelivr CDN) that `scripts/build_site.py` and `scripts/site_phase5.py` write into the page as JSON; `site_src/site.js` embeds them. Captions are built in `chart_block()` from `shows` / `doesnt` / `question` / `lens` strings in the Python chart definitions. Datasets are SQL exported to `site/data/*.json`; a spec may only map fields to marks.
- **Baseline (before).** Measured with Playwright driving the installed Chrome (`scripts/site_shots.py`; screenshots and `pages.csv` in `docs/reports/site_baseline/`): the Data quality page is 271,211 px tall because the Pareto chart is 268,183 px tall, and prints to **161 A4 pages** (Anna's PDF counted 198 on her paper size). The Club markets page overflows horizontally by 2,363 px at 1440 px. Every other page prints in 1 to 4 pages.
- **Playwright.** The handover assumes a pre-installed Chromium. This machine has none, so Playwright is added as a dev dependency and drives the installed Google Chrome (`channel="chrome"`); nothing is downloaded. GitHub's ubuntu runners ship Chrome, so the same call works in CI.
- **Duplicated sources? No gap; labelling only.** The heatmap lists 11 sources: the five original (`US_LEAGUE`, `CA_CLUB`, `INTL_FED`, `SCHOOL_AGGREGATES`, `FAN_ENGAGEMENT`) and the six channel feeds. The feeds are separate source systems (own raw table, own contract), not sub-channels of the US league, and `school_program` (a roster export, one row per student) is not `SCHOOL_AGGREGATES` (program headcounts, no people). ADR-013 decided this on purpose: the feeds are scored but **not counted** because they describe the same children as `US_LEAGUE`. So there is no reconciliation gap and no model change; the site only needs to label and group them (original sources / new intake channels) so the relationship is visible. `FAN_ENGAGEMENT` is not a registration source and is grouped apart.

## Decision

### 1. Cards and a full-screen viewer
- Each chart is a **card**: a plain-language headline with a real number, the question, a fixed-height thumbnail (250 px; a check fails above 320 px), *What this means*, *What to do* (both in a Club and a Privacy version), *Be careful*, and a collapsed *For analysts*.
- A card's slides open in one **`<dialog>` viewer** that holds every slide on the page, in page order (`scroll-snap`, arrow keys, PageUp/PageDown, Home/End, a rail of slide titles, Esc, focus returned to the Expand button). `quality.html#view=Q3-2` opens a slide directly. Slides render lazily when within one slide of the viewport; the chart is re-rendered from its own full-size spec, never scaled up from the thumbnail. A chart always sits in a box of fixed size (`autosize: fit`, `width` and `height` `container`), so it can never grow the page (the root cause of the 268,183 px Pareto).
- Slide kinds: a Vega-Lite spec, an HTML panel (tile map, fix letters, lens pairs), or a grid of small Vega charts (the grid wraps: 3 columns, 1 on a phone). The component (`site_src/assets/viewer.js`, `viewer.css`) contains no data logic.
- Pages shrank: Data quality 271,211 px to 2,638 px and 161 print pages to 3; Club markets no longer overflows sideways (details in `docs/reports/site_before_after.md`).

### 2. Copy rules
- Copy lives in `site_src/copy/charts.yml` (not `site/copy/`: the build recreates `site/`), one entry per card with `status: draft` until Anna approves it; the build warns while any entry is draft. Placeholders (`{field}`, or `{Q1.field}` on a page intro) are filled **by string substitution only** from SQL insight exports (`share_club__chart_insights`, `share_privacy__chart_insights`, and `eval_chart_insights` for the cards graded against the answer key, which therefore lives in `evaluation`). A missing value fails the build unless the entry declares a fallback headline with no numbers. People and families are whole numbers; estimates are rounded in SQL to the nearest 10 and prefixed "about"; a count under the small-cell limit reads "fewer than 10".
- Every card is checked for: a non-empty slot each, a headline of at most 15 words, sentences of at most 25 words, Flesch-Kincaid grade at most 9, none of the banned words or codes outside `<details>`, no long decimals, no unfilled placeholder, and every number in a headline present in an insight export (`scripts/site_check.py`).
- Plain labels come from seeds (rule label and action, purposes, dimensions, grades, sources, channels, club markets, funnel steps) with tests that every code has one. A glossary page lists every term with the analysts' name.

### 3. A league belongs to one market
Participants are allocated to club markets by ZIP3 weight (ADR-016), but a league cannot be split: it now belongs to the one market with the highest weight for its ZIP3 (ties: the lowest market id). League counts per market are whole numbers (the old chart showed 4.5 leagues). Participant allocation and the coverage estimate are unchanged. Only `orgs_known`, `orgs_reporting` and `orgs_dark` in `mart_market_coverage` changed.

### 4. Control-limit width (Q2): OPEN, Anna decides
Investigation in `docs/reports/site_after/control_chart_note.md`: the binomial P-chart flags 20% of source points (30% for the largest sources) because limits a few points wide ignore real year-to-year movement. Recommended: an individuals (XmR) chart on the score for sources, labelled "early read", and no limits for organizations. **Nothing was changed**: the chart uses the current limits, draws a band only from the fourth season, and says so in its analyst notes. The choice changes `dq_trend` and the Q2 headline numbers.

### 5. Other deviations from the handover
- The tile map groups tiles by state (west to east) instead of drawing a map: 72 px tiles with four lines of text do not fit a geographic grid in the viewer.
- The tile-map card defaults to Counting players, as specified; the Pareto card (Q3) defaults to Contacting families because the top Counting-players problem affects fewer than 10 players, so every bar would be hidden.
- Q4 cannot say "N times as likely": no league on the recommended software is graded C or D. The headline gives the shares.
- The "records deleted at age-out" line is not on the privacy panel: the count lives in a restricted store with no approved share. A `share_privacy` model for it would be the follow-up.
- `growth_from_new_reporting_share` (a growth headline) was not built; the growth card uses a neutral headline.
- The tour page (`tour.html`) was cut, as the handover allows: deep links and each page's "5-minute path" button cover it.
- Footer: "Scorecard methodology 2.0 · methodology memo 1.2". They are two different versions (the memo is 1.2, scorecard KPIs 2.0, per the CHANGELOG), now each read from its own source.

## Consequences
- The site-check suite (`make site-check`, `site-check-ci` in `all-phases`) runs in about 80 seconds for four pages and 50 seconds for two.
- The copy file is the one place Anna edits; everything numeric stays in SQL.
- Club market names remain "{State} market {n}". OPEN: approximate metro names if Anna prefers; never team names, logos or colours.
