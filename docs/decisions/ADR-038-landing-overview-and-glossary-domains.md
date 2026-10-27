# ADR-038: The landing page is an overview of the site; the glossary is grouped by domain

- **Status:** Accepted, 2026-10-27, at Anna's request. **The landing copy is `status: draft`** (`landing` in `site_src/copy/charts.yml`), and so are the new glossary terms (`site_src/copy/glossary.yml`).

## Decisions
1. **The landing page (`index.html`) gives a five-minute overview of the whole site.** It replaces the old headline table and link list.
   - **Banner:** four headline numbers: fans added, children who played, data products and readable program markets.
   - **A short intro.**
   - **One section per phase:**
     - Phases 1 to 4: high-level analysis;
     - Phase 6: data products;
     - Phase 7: global outlook;
     - trust and governance, marked in blue because it runs through every phase.

     Each section has a question, a one-line summary, five takeaways and pill links to its pages.
2. **Every number is filled from the build, never typed.**
   - `{name}` takes a value the results build already uses on its pages, formatted for reading.
   - `{X1.field}` takes an insight value, as in every card headline.

   The insight placeholder now accepts two-digit card codes (`D10`).
3. **The glossary is grouped into nine domains**, and a section bar lists them:
   - reading this site;
   - counting players;
   - fans and families;
   - matching and its errors;
   - data quality;
   - privacy and consent;
   - governance;
   - data products;
   - global outlook.

   It grows from 16 hand-written terms to 74, from a scan of every page's visible text for terms that had no entry. The uses, checks and grades from the seeds, and the collapsed list of every problem we check, sit under data quality.
4. **Terms are visually distinct from definitions.** Each term is a card:
   - **Term:** in the domain's colour, in the display type.
   - **Definition:** in body text.
   - **Analysts' name:** in a small grey code style under "Analysts call this".

   Dark mode lightens the domain colours so they keep their contrast.

## Consequences
- The phone check passes on both pages; terms stack in one column on a phone.
- A new term goes in the domain it belongs to, in `glossary.yml`.
