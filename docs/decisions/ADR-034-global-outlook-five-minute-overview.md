# ADR-034: The Global outlook's five-minute read is an overview, not a slide tour

- **Status:** Accepted, 2026-10-26, at Anna's request: she found the page itself better than the "5-minute path", and wanted the five-minute read to be an overview that synthesizes the tab rather than a more detailed walk. **The overview's text was approved as final by Anna the same day** (`pages.global` in `site_src/copy/charts.yml`).

## Context
On every card page, "Start the 5-minute path" opens the full-screen viewer and steps through every slide. On the Global outlook that meant 11 slides: four continent maps and two step-by-step walkthroughs among them. That is the detail, not a summary of it.

## Decisions
1. **On this tab the slide tour is replaced by an overview: "In five minutes: what the global outlook says".** It is placed straight under the banner, above the lens toggle (the overview does not change with the lens). It has five stat cards, one per question:

   | Card | Number | Sentence |
   |---|---|---|
   | Markets we can read | 7 of 22 | how many more only report club activity, and how many send nothing |
   | Change needed to tell | 51% | how many markets show growth we can tell from noise, and what would change that |
   | Guesses right in our test | 5 of 15 | why markets with no data get a plan, not a number |
   | Markets close to readable | 2 | which markets, and how many more club filings each needs |
   | Markets in the first lane | 4 | what to ask them for |

   Each card links down to its section, and "Overview" is the first link in the section bar. The cards use the Data product summary's own stat-card style (`ps-leader`).
2. **Every number is an insight value**, filled by `site_cards.fill` like every headline. The guess card says "in our test", because its numbers come from the synthetic answer key.
3. **The detail stays.** Each card's Expand button still opens its full slides in the viewer. `lens_scope` now leaves out the five-minute path when a page gives none; the other pages keep theirs unchanged.

## Consequences
- The page check passes at three widths. On a phone the five cards stack.
- If the five-minute path on the other tabs should also become an overview, that is a separate change, page by page.
