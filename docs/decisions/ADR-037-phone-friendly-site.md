# ADR-037: The whole site works on a phone, and a check keeps it so

- **Status:** Accepted, 2026-10-27, at Anna's request ("make the whole website mobile friendly").

## What an audit at 390px found
- **No page scrolled sideways**, but:
  - many controls were 19–31px tall: the notice's Dismiss, the menu button, every "For analysts" and "The numbers behind this chart", the walkthrough and Expand buttons, the purpose buttons and the roadmap cards;
  - text on the market tiles, product tables, roadmap chips and summary tags was 10–11px.
- **Charts:**
  - legends laid out in a row ran off the right edge (Audience, Club markets, Privacy);
  - long category labels down the side squeezed the plot, and labels along the bottom ran into each other.

## Decisions
1. **Phone rules in one place:** a `max-width: 719px` block at the end of `site_src/styles/site.css`, with the same rules in `site_summary.CSS` for the one-page summary. Every control is at least 44px tall to tap (the notice button 40px), and reading text is at least 12px. Inline links inside sentences are exempt.
2. **Charts are re-laid out on a phone, never recomputed** (`phoneSpec` in `site_src/site.js`, used by the page charts and by `viewer.js`). Below 600px:
   - every legend stacks in one column under the chart, with labels that fit the screen;
   - long category labels down the side wrap onto up to three lines, and the chart gets taller rows to hold them;
   - category labels along the bottom wrap onto short lines.

   Only layout settings change (orient, columns, label limits, label line breaks, row height). No data, field or number is touched, so the no-computing-in-the-browser rule holds.
3. **Card thumbnails keep their fixed height and whole labels.** The existing check forbids a cut-off label in a thumbnail. A phone thumbnail whose long side labels leave no room for a legend drops the legend; Expand opens the full chart with it.
4. **`site_check` checks every page at phone width** (390x844, touch), in local and CI runs. It fails on:
   - sideways scroll;
   - a control under 40px tall;
   - reading text under 12px;
   - chart text off the screen.

## Consequences
- Desktop and tablet layouts are unchanged: every phone rule sits behind a width query, and the chart re-layout runs only below 600px.
- Found during the audit and left as it was: in the Club markets "Is growth real" thumbnail (M2), two small charts (Georgia market 2, California market 2) draw no line at any width. That is a chart bug, not a phone one, and needs its own fix.
