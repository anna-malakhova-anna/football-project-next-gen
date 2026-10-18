# The feedback loop: how monitoring changes the roadmap

> One worked example. **The first four links are real outputs of this build (Phase 5 and 6); the last link is a proposal, labelled as one.** Synthetic data; every role is fictional.

**The loop in words:** the product-health and scorecard views show a gap; the gap is traced to a cause; the cause is fixed at its source (a fix list, a standard); the next season shows whether it worked; the result changes what the next version of the product does.

## The worked example: leagues that send no file

1. **Monitoring shows a gap (DP4 and DP1 health).** The US league source grades C for both counting players and placing them on the map, with the same score, 82.1 (draft target X: at least 85). One check sets it: *Arrived on time*, which is the share of known US leagues that sent a file (82.1%). Every other check is A or B. At the market level, DP4 reports 14 of 76 known leagues sent no file, and 5 markets at grade C and 5 at D for placing players on the map. The weakest individual leagues are disproportionately the ones that send spreadsheets: 3 of 8 spreadsheet leagues are graded C for the map, against 1 of 40 on the recommended software.
2. **A cause is found (the fix list).** For 14 US leagues the top fix is "send this season's registration file, in any format" (the second most common first fix for a US league, after "the form never mentioned marketing", which is the first fix for 44 leagues). The fix list gives each league its few most costly problems in plain words (`share_ops__league_fix_list`, Phase 5 `dq_fix_list`).
3. **The fix is applied at the source (the fix list, not a new standard).** The data standard already asks for what the products need (the 3-digit ZIP is REQUIRED, ADR-018), so the standard does not change. What changes is that each league is sent its fix list.
4. **The next season shows whether it worked (a simulation, labelled).** The Phase 5 fix-list demo (`make fix-list-demo`) simulates half of the struggling leagues acting on their fix list in the final season. In that **simulated** scenario the leagues that acted rose from 97.2 to 99.1 for counting and from 91.3 to 95.5 for placing players on the map, and from 59.5 to 63.2 for contacting families, while the struggling leagues that did not act went from 94.1 to 91.8 for the map. It is a scenario on a copy of the warehouse, not an observed result. It also narrows the girls' share bounds only slightly: the larger uncertainty is the leagues that send no file at all, which a fix list does not remove.
5. **The roadmap changes (proposal, not built).** Because the largest remaining gap is leagues that send no file, DP1's next minor version would add a "no file received" alert to the league scorecard and a one-page request to the league (the fix-list letter on the Data quality page), and DP4's next version would show, beside each market's grade, how much of the grade is limited by leagues that sent nothing. Neither is built; both would be scored in `product_prioritization.csv` like any other item.

## Where each link lives
| Link | Artifact |
|---|---|
| Health and gaps | `phase6.mart_product_health`, `share_ops__league_scorecard`, the Data quality page |
| Cause | `share_ops__league_fix_list`, `dq_fix_list` |
| Fix at the source | `docs/data-standard.md`, ADR-018 |
| Did it work | `scripts/fix_list_demo.py`, `docs/reports/fix_list_demo.md` (simulation) |
| Roadmap change | `docs/product/roadmap.md`, `dbt/seeds/product_prioritization.csv` |
