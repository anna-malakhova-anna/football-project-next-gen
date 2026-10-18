# Decommissioning: a worked example (DRY RUN)

> **This is a dry run.** Nothing is retired. It shows how a retirement would be carried out, using a real candidate: the school and recreation headcount aggregate (Phase 4, source `SCHOOL_AGGREGATES`, shown on the Appendix page). That source counts programs, not people; it is a stretch source that is never added to participants and serves none of goals G1 to G3 directly. Synthetic project; every role is fictional.

**Decision (hypothetical):** retire the school headcount aggregate from the portfolio. It is reviewed and approved by the data product manager, with the privacy lead consulted (RACI, `roles.md`: "retire a product").

| Step | What would happen | Where it lives |
|---|---|---|
| 1. Notice to consumers | A notice goes to everyone who reads the Appendix page and the reported-headcount share: what is going away, from which version, and what to use instead (nothing replaces it; the participant counts are unaffected). Notice period: one full publish cycle. | The Appendix page banner; `docs/source_inventory.md` status set to Deprecated |
| 2. Deprecation version | The consuming product (DP3) goes to the next **major** version, because an output column set changes. DP3 would move from 0.9.0 to 1.0.0 only if it had already shipped; the dry run labels it `next major`. | `products/DP3/product.yml`, `products/CHANGELOG.md` |
| 3. Removal of the share model | `share_exec__reported_headcount` is removed from `models/shares/exec/`, its rows are removed from `audience_column_policy.csv` and `metric_catalog.csv`, and the share-policy check must pass without it. | `dbt/models/shares/exec/`, `dbt/seeds/` |
| 4. Data disposal | The staged and modelled school tables are dropped, and the raw files are disposed of under the retention rules (`docs/retention.md`, ADR-017). A deletion request cannot be shown to reach raw data here (an open question, ADR-017), so the dry run records disposal of the derived tables only. | `contracts/SCHOOL_AGGREGATES.yml` set to retired; `docs/retention.md` |
| 5. Changelog entry | A line in `products/CHANGELOG.md` and in the methodology CHANGELOG, stating the removal and that no participant count changed. | `products/CHANGELOG.md`, `docs/methodology/CHANGELOG.md` |

**Check that would have to pass before step 3 is committed:** `scripts/check_share_policy.py`, the contract coverage test, and `make site-check` (the Appendix page and the footer link are removed together).

**Why a dry run:** nothing in the repo is being retired. The Phase 5 chain of identity models is a candidate for a real retirement (ADR-021, "Phase 5 identity input"), and would follow the same five steps, but that decision is the program owner's.
