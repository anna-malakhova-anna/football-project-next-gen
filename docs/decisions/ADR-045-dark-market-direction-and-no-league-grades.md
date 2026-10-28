# ADR-045: The guess's direction is graded only beyond the minimum detectable change; markets with no league keep their grade

- **Status:** Accepted, 2026-10-28, by Anna. It settles the two open questions in ADR-039 and ADR-044.
- **Synthetic data.**

## 1. Grading the dark-market guess's direction (ADR-039, option A)
**Changes an ADR-025 evaluation rule after its result was seen.** This is that rule, named here as ADR-025 requires.

- **Before:** ADR-025 section 6 scored the scenario's direction against the answer key's direction in every dark market. The scenario says "flat" unless its comparables move beyond the minimum detectable change (z·σ, ±51% in this build). The answer key calls a market flat only within ±3% (`phase7.truth.flat_band`). So "flat" was wrong by construction: 15 of 15.
- **Now:** direction is graded only where the true move is larger than the same minimum detectable change. A smaller move is one the method never claimed it could see, so it is "not gradable" (`direction_match` is NULL), not wrong. The direction error is over graded markets only.
- **Result in this build:** no dark market's true move reaches ±51% (the largest is Italy, −35%), so the direction is graded in 0 of 15. The card says so in a sentence written to be true for any count. The range result ("inside the range in 5 of 15") and the club activity result are unchanged.
- **Rejected:** option B, scoring "flat" as "no direction stated". It tests nothing when every guess is flat, and it would let a flat guess pass a large real move.

## 2. Markets with players but no league (ADR-044 item 9)
Markets such as Texas market 2 receive players by ZIP3 weight but have no league of their own (ADR-016). **They keep their grade.**
- The market grade answers one question: are the records placed here good?
- Whether a league is assigned is a different question. The tile already answers it: "Players placed here by ZIP code; no league is assigned to this market yet".
- One letter for both would mix them. No model changes.

## Consequences
- `eval_gmp_scenario` gains `true_growth`, `minimum_detectable_change` and `direction_gradable`; `eval_gmp_scenario_summary` gains `direction_graded` and `minimum_detectable_change`. The G3 insights gain `n_direction_graded` and `direction_result`.
- The Global outlook's evaluation table shows "Direction graded" beside "Direction wrong".
