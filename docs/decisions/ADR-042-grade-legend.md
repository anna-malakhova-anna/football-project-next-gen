# ADR-042: A key to counting grades A to D on the Global outlook

- **Status:** Accepted, 2026-10-27, at Anna's request ("add a legend for grading A-D").

## Decision
The map (G0) and the market tiles (G1, card and slide) carry a key above the chart:
- **Grades:** each grade's colour, plain meaning and lowest score.
- **Readable:** which grades make a market readable (A to C).
- **No data:** the two no-data outlines.

Every value is read from `reference.dq_grade_bands` and the Measured bar in `p7_params`, through a new governance dataset `gmp_grade_bands`, so the key follows the bands if they change. The map's slides keep their own colour legend as well.
