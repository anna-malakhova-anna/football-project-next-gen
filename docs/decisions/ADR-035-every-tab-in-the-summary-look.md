# ADR-035: Every tab takes the Data products summary's look

- **Status:** Accepted, 2026-10-27, at Anna's request ("apply the same style as in Data Products and Global outlook to the rest of the pages"). Anna chose the **look only**, with no new headline numbers or overviews, and asked for the Data products tab itself to be included. **The section-bar labels were approved as final by Anna the same day** (`page_sections` in `site_src/copy/charts.yml`).

## Decisions
1. **Every page gets the Global outlook's frame (ADR-033):** the dark banner, the sticky section bar and numbered sections with green-edged headings. This covers every tab, the appendix and the glossary. The one-page summary is unchanged.
   - **Banner:** the page's menu group as the eyebrow, or "Flag Football Project" when the group has the page's own name. Then the title, the synthetic-data badge and the page's existing one-sentence question. It has **no headline numbers**.
   - **Above the sections:** the intro paragraphs, the 5-minute path and the lens toggle stay as they were.
2. **Sections come from the content, not new text** (`sectionize` in `scripts/build_site.py`):
   - A card or chart before the first heading is a section of its own, titled by its question or chart title. That title stays in the page, visually hidden, as in ADR-033.
   - A heading starts a section that runs to the next heading, and keeps its anchor (`trust.html#documents` still works).
   - The only new copy is each section's short label in the bar. A section with no label stops the build.
3. **Only the frame of the summary stylesheet is used.** That is its colours, type, banner, bar and sections (`SUMMARY_FRAME_CSS`, the part of `site_summary.CSS` above its table rules). The summary's restyled tables, roadmap and persona cards stay on the summary page and the Global outlook, so the Data products cards render as before (the roadmap still fits 1440x900).
4. **Cards stack one per row inside their sections**, as on the Global outlook, instead of the two-column grid.
5. **Layout fixes the new frame needed:**
   - **Viewer slides:** they keep the site's own type (Barlow), so their tables still fit a phone. This also applies on the Global outlook.
   - **Wide tables:** a table with seven or more columns scrolls inside its section between 701px and 1100px. This fixes the Audience tab's household table, which was already 217px too wide at 768px.
   - **Print:** the section bar is hidden and sections may break across pages, so the Data products tab still prints on 12 pages or fewer.

## Consequences
- The page check passes on the 6 pages it covers (`site_check`, three widths and print). No page in the site is wider than the window at 1440, 1024, 768 or 390 px.
- A new card, chart or heading needs a label in `page_sections` before the build passes.
