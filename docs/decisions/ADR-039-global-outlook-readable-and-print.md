# ADR-039: "Readable" means Measured everywhere on the Global outlook; the guess chart says what it measures; the page prints whole

- **Status:** Accepted, 2026-10-27, from a review of `global.html` (Anna's handover). No status, direction, scenario or lane rule changed (ADR-025, ADR-029).
- **Synthetic data.**

## What the review found
1. **"Readable" meant two things.**
   - The hero, the G1 card, the overview and the landing page counted Measured + Partial ("7 of 22").
   - The "close to readable" card asked how many more clubs Japan and the UK (Partial, grade D) need to reach the Measured bar.

   One word, two sets.
2. **The guess chart's two numbers measure different things.**
   - "Right in 5 of 15" means the true value fell inside the guessed range.
   - "Direction wrong in 15 of 15" is not a sign error. The scenario's direction comes from its comparables, and none shows a change beyond the noise floor (±51%), so it is FLAT for all 15.
   - The answer key calls a market flat only within ±3% (`phase7.truth.flat_band`), and every one of the 15 moved more than that.
   - The handover's guess, that markets are built to move against their neighbours, explains only 6 of the 15. The other 9 also fail, because "no change we can tell" is graded against a ±3% label.
3. **Printing lost the charts and cropped the banner.**
   - Card thumbnails were drawn only when scrolled into view, so a print or PDF taken without scrolling had empty charts.
   - The Global outlook loads the one-page summary's stylesheet, whose print rules fix the banner to a letter-page height and width. That cropped the banner and its numbers.
4. **Italy:** the published build has no minimum return (`raw.gmp_minimum_return` is empty), so Italy is Dark. The walkthrough's "tried on a copy" stages feed no count or grade. Only the caption was unclear.

## Decisions
1. **Readable = Measured** (counting grade C or better, ADR-025), the rule the glossary already gave.
   - `G1.n_readable` now counts Measured markets only: **5 of 22**, not 7.
   - The hero, the overview, the G1 card and the landing page all read it, and they now say "{n_partial} more send player data we cannot read yet".
   - The growth chart keeps Japan and the UK, as pale bars labelled "data we cannot read yet", with a legend.
   - The glossary has a "Readable market" entry.
2. **Growth chart:**
   - Both ±51% lines are on the axis, labelled once, "±51%: change needed to count".
   - The caption adds that every market points up ({n_up} of {n_with_data}), as weak evidence of a shared trend and not a reading.
   - The headline says "markets with player data".
3. **Guess chart:**
   - The headline says "The true number fell inside the guessed range in 5 of 15 markets."
   - The caption explains the dot colours, explains the direction result honestly, and notes that a guess resting on one comparable is a single number.
   - Those single-number guesses (Argentina, Brazil, Colombia) now show a tick, and the thumbnail has a legend.
4. **Italy's caption:** "Italy sends no data yet; its walkthrough uses a test copy to show the onboarding steps, and no count or grade comes from it."
5. **Printing:**
   - Every thumbnail renders once the page is idle, and again on `beforeprint`.
   - The site's banners reset the summary's print sizing.
   - A banner number never wraps away from its unit.

## Open: for Anna to decide (settled by ADR-045: option A)
How the guess's direction is graded. Today a scenario that says "no change we can tell" is scored against a ±3% truth label, so it can never be right in this test world. There are two fairer gradings:
- **Option A:** score only markets whose true move exceeds the same noise floor.
- **Option B:** grade the scenario's direction as "not stated" when it says FLAT.

Either changes an ADR-025 evaluation rule after seeing the result, so it needs its own ADR and is not done here.
