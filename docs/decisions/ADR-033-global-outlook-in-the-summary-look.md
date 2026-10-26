# ADR-033: The Global outlook tab takes the Data product summary's look

- **Status:** Accepted, 2026-10-26, at Anna's request ("the style similar to the Data product summary page"), applied to the tab itself rather than as a separate summary page (her choice). **The new banner text, headline-number labels and section labels were approved as final by Anna the same day** (`pages.global` in `site_src/copy/charts.yml`); the cards' text is unchanged.

## Decisions
1. **Same parts, same styles, no copy of the CSS.** The page reuses `site_summary.CSS`, the summary page's stylesheet, scoped to `body.summary`:
   - **Banner:** dark, with an eyebrow line, a large uppercase title, the synthetic-data badge, the intro as its line, and four headline numbers.
   - **Section bar:** sticky.
   - **Sections:** numbered, with green-edged headings.

   A short `GLOBAL_CSS_EXTRA` in `scripts/build_site.py` adds only what a card inside a section needs.
2. **The site template gains three optional inputs** (`site_src/templates/base.html`, `render_page`): a full-width banner shown in place of the plain title, a body class, and a style block. Every other page passes none of them and renders as before. The site's top menu, footer and full-screen viewer stay on the Global outlook page.
3. **One numbered section per card, in an order set by the copy:**

   | # | Section | Card |
   |---|---|---|
   | 1 | Map | G0 |
   | 2 | Markets | G1 |
   | 3 | Growth | G2 |
   | 4 | The guess | G3 |
   | 5 | Quality | G4 |
   | 6 | Next steps | G5 |

   The section title is the card's question, so the card's own question line is visually hidden (kept for screen readers and the page check). The card keeps its headline, chart, notes, analyst section and viewer slides.
4. **Every number in the banner is an insight value** (`{G0.n_markets}`, `{G1.n_readable}`, `{G2.mdc_pct}`, `{G5.n_now}`), filled by `site_cards.fill` like every headline, so nothing is typed into the page.

## Consequences
- The page check (`site_check`, three widths) passes. On a phone the banner's four numbers wrap to two rows, and the page does not scroll sideways.
- Charts below the first screen draw as they scroll into view (the viewer's existing behaviour), as on every other page.
