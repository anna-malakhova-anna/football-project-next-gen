# ADR-031: The Global outlook tab on the results site

- **Status:** Accepted for step 9 of the Phase 7 spec, 2026-10-26. **Copy approved as final by Anna on 2026-10-26** (`site_src/copy/charts.yml`, cards G1 to G5 and the `global` page intro). Card G5's headline and caution were reworded the same day, once Anna accepted the rubric's scores (ADR-029): the scores are agreed, and most lanes are still a plan to review.
- **Synthetic data.** Flag football only. The markets are the 22 of the NFL Global Markets Program; clubs are anonymous (ADR-024).

## Decisions
1. **A new page, `global.html`, with a top-level navigation entry** ("Global outlook", next to Data product), built by `scripts/site_global.py`. The module imports no other site module, so it sits at the bottom of the site's layers (`tests/test_site_layout.py`).
2. **One card per question of the spec:**

   | Card | Question | Reads |
   |---|---|---|
   | G1 | Which markets can we read? | the three regime market ports (status, grade) |
   | G2 | Is any market growing? | the market ports (like-for-like growth against the change needed) |
   | G3 | What would a number for a dark market have said? | `eval_gmp_scenario` and its summary: tagged as a synthetic evaluation |
   | G4 | How do we make a market readable? | the three regime quality-trend ports |
   | G5 | What do we do next, and how? | the board port and the walkthrough port (Canada and Italy, step by step) |

3. **The site's rules hold unchanged:**
   - every number comes from a registered dataset, and the page reads only DP6's exec ports, two whitelisted evaluation summaries and governance metadata (the market list, grade bands, the Phase 7 parameters);
   - every label, order and threshold is worked out in SQL;
   - chart specs only map fields to marks;
   - every headline number is filled from an insight export.

   The headline numbers come from a new `share_exec__gmp_chart_insights` for G1, G2, G4 and G5. G3's numbers read the answer key, so they are added to `eval_chart_insights` and never enter a share.
4. **The planning scenario appears only in G3, against the truth of the synthetic test world**, never on the same chart as a measured value. The page states plainly that a market with no data gets a plan, not a number (Anna's decision D3).
5. **The partner report card is not on the site.** Each federation receives only its own card (ADR-027). G4 explains this and works out "one more club" from exec data (each market's trend and the grade band).
6. **`scripts/site_check.py` checks the page** (layout at three widths, the copy rules, the viewer). It is in the CI page list, and it reads the new insight export when it checks headline numbers.

## What the page says today
- **G1:** we can read 7 of 22 markets; 6 send nothing.
- **G2:** none of the 7 shows a change we can tell from noise; a change has to beat 51%.
- **G3:** a guess for markets with no data was right in 5 of 15, and its direction was wrong in all 15.
- **G4:** Japan and the UK are each one more club filing away from readable.
- **G5:** four markets are in the first lane of the board; scores follow one agreed rule.
