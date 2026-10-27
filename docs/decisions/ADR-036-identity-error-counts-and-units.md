# ADR-036: Identity error counts are uncapped, and every sibling or twin figure states its unit

- **Status:** Accepted, 2026-10-27, from a review of the Identity section of `trust.html`. Matching and the chosen thresholds are unchanged (ADR-003); only how the errors are counted and labelled changed.
- **Synthetic data.** Every figure here is graded against the generator's answer key.

## What the review found
- **The error table counted a capped list.** `eval_errors` keeps only the 200 highest-scoring errors of each kind per matcher and stage (for the error analysis), and the site and `print_headline` counted its rows. Two counts were therefore truncated:
  - the uncorrected matcher's false merges showed 200 (38 + 162) instead of **972** pairs;
  - the rules matcher's missed matches showed 200 instead of **2,621** pairs.

  The final matcher's counts were below the cap and correct.
- **Two units were mixed.**
  - The matcher table and the sibling chart count **clusters**: predicted people who wrongly hold two children of one household (`eval_clusters`, `eval_threshold_sweep`).
  - The error table counts **record pairs**: merging one child's *a* records with another's *b* makes *a* × *b* pairs.

  The figures reconcile once the unit is known: the final matcher's 7 clusters at the automatic scope (all twins) hold 38 twin pairs, and the uncorrected matcher's 153 clusters hold 677 sibling and 239 twin pairs.
- **The 38 in both matchers' rows was a coincidence.** The final matcher's 38 twin pairs are its full count. The uncorrected matcher's 38 sibling pairs were simply how many siblings fell inside its capped 200. No join carried rows between matchers: every join in the model is on the matcher.
- **A label was wrong.** `TWIN` showed as "Twins or siblings", and `SIBLING` had no label at all, so its raw code reached the page.

## Decisions
1. **`eval_errors_all`** holds every classified error, with no cap. **`eval_error_categories`** counts it in record pairs at the automatic scope; the site and `print_headline` read this. `eval_errors` is now the capped list taken from `eval_errors_all`, and its rows are identical to before.
2. **Labels:**
   - `TWIN` is "Twins" and `SIBLING` is "Siblings (not twins)", for every matcher.
   - The error table gains a scope column (automatic merges only).
   - Cluster columns say "(clusters)", and the matcher table gains "Of which twins (clusters)".
   - A caption under the error table derives the cluster-to-pair reconciliation from the data.
3. **Unmapped codes stop the build.** `STRICT_LABELS` in `scripts/site_render.py` names the columns whose every code must have a plain label.
4. **Charts:**
   - Both threshold charts use the same numeric 0.50 to 1.00 axis.
   - Each shows a dashed line at the chosen automatic-merge threshold and shades the probable band sent for review. Both values are read from `reference.match_thresholds` (now governance metadata the site may read), never typed.
   - Chart 1's title names the matcher (final), the scope (automatic merges only) and the unit (record pairs), and its legend sits below the plot.
   - Chart 2 is a step line counting clusters.

## Consequences
- No other number changed: `eval_clusters`, `eval_threshold_sweep`, `eval_pairwise`, `eval_errors` and the identity bounds are identical to before this change. The restatement log has the same rows as before.
- `docs/phase2_results.md` now reports the uncapped counts.
