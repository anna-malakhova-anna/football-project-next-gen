# ADR-041: Counting score as one chart per market; the market board as a roadmap; small-multiple panels have a fixed height

- **Status:** Accepted, 2026-10-27, at Anna's request ("there is no visual for Japan"; "represent Now, Next ... as a roadmap"). No score, lane or rule changed.

## What was wrong
- **Japan was hidden on the counting-score chart (G4).** Its 2024 and 2025 scores (66.67) are exactly the UK's, so its line sat under the UK's. The site's five-colour palette also repeated across seven markets.
- **Small charts in a grid could be flattened.** Panels sized to their grid cell's height ("container") rendered at the wrong height in the left column. That is why Japan and Canada looked empty in the G4 thumbnail, and why Georgia market 2 and California markets 2 and 3 drew no line on the Club markets growth card (M2, noted in ADR-037).

## Decisions
1. **G4 is one small chart per market**, the markets close to readable (Partial) first.
   - Each panel shows the score by season and the dashed bar to clear. A point is blue at or above the bar, red below it.
   - The slide shows all seven markets; the thumbnail shows the first six.
2. **G5's board is a roadmap.**
   - **Lanes:** Now, Next and Later are arrow-headed columns, then Keep for the readable markets. Each header has the lane's count and a one-line meaning (`pages.global.board_lanes`, new copy).
   - **Cards:** each card has the market's status dot (the map's colours), its next action, and its milestone with a progress bar from `share_exec__gmp_board`.
   - **Thumbnail:** names only.
   - **Phone:** the lanes stack.
3. **Small-multiple panels have a fixed height** (64px in a thumbnail, 170px in a slide), and only their width fits the cell. The grid renderer also draws the charts after every cell is in place. This fixes both G4 and M2.

## Consequences
- The site check passes, including all pages at phone width; thumbnails stay within 320px.
