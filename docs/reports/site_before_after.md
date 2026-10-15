# Site before and after (Phase 5.1)

Measured with `scripts/site_shots.py` (Playwright driving the installed Chrome) at 1440 x 900 and 390 x 844. Before: `docs/reports/site_baseline/` (2026-10-14). After: `docs/reports/site_after/` (2026-10-15). All data is synthetic.

| Page | Height before (px) | Height after (px) | Print pages before | Print pages after | Sideways overflow before, 1440 px | after | before, 390 px | after |
|---|---|---|---|---|---|---|---|---|
| quality | 271,211 | 2,607 | 161 | 4 | 625 | 0 | 1555 | 0 |
| sure | 2,695 | 1,958 | 2 | 3 | 0 | 0 | 793 | 0 |
| markets | 3,342 | 2,741 | 3 | 4 | 2363 | 0 | 3293 | 0 |
| privacy | 4,126 | 3,237 | 3 | 4 | 0 | 0 | 0 | 0 |

The limit set by the handover is 12 print pages per page; every page is at 4 or fewer. The Pareto chart on the Data quality page, which was 268,183 px tall, is now a 250 px card thumbnail.

## What changed
- **Data quality (D1 to D8).** Q1 to Q5 are cards with a plain headline and a full-screen viewer (22 slides on the page). The dual-axis Pareto is horizontal bars per use; the heatmap is a grid with plain names and wrapped headers; the scatter is a stacked bar by league size and by how a league sends data (the scatter is kept for analysts); the fix list is a letter per league.
- **Club markets (M1 to M6).** The intro no longer ends mid-sentence (the literal `<k` was read as a tag). The tile map shows one use at a time with larger tiles; the growth charts wrap in a grid and use an index; the funnel shows what remains and splits each loss by cause; leagues are whole numbers; the privacy lens panel is back, beside the club panel, and a test fails if either goes missing.
- **How sure and Privacy by design** use the same cards. **Navigation** is four groups. **A glossary** and a **5-minute path button** on each page were added.

## Checks
`make site-check` (about 80 s, four pages) and `make site-check-ci` (about 50 s, two pages; part of `make all-phases`) cover layout, content and viewer. The full `make all-phases` after this work: dbt 450 passed (2 expected warnings), pytest 205 passed, site check OK.

Screenshots in `docs/reports/site_after/`: one per page and viewport, every card, and a selection of viewer slides.
