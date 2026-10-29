# ADR-042: A key to counting grades A to D on the Global outlook

- **Status:** Accepted, 2026-10-27, at Anna's request ("add a legend for grading A-D").

## Decision
The map (G0) and the market tiles (G1, card and slide) carry a key above the chart:
- **Grades:** each grade's colour, plain meaning and lowest score.
- **Readable:** which grades make a market readable (A to C).
- **No data:** the two no-data outlines.

Every value is read from `reference.dq_grade_bands` and the Measured bar in `p7_params`, through a new governance dataset `gmp_grade_bands`, so the key follows the bands if they change. The map's slides keep their own colour legend as well.

## Extension, 2026-10-28: Club markets
At Anna's request, the first card on Club markets ("How's my market?") carries the same kind of key, built by `render_grade_key` in `scripts/site_phase5.py`:
- grades A to D, each with its colour, plain meaning and lowest score, from `dq_grade_bands`;
- a note that the score is out of 100 for the chosen use;
- the tile states with no grade that occur ("No data yet"; "Too few players to show" only when a market is suppressed).

It appears on the card and on every slide of the card.
