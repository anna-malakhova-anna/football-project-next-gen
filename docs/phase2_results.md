# Phase 2 results: identity resolution

> **Generated** by `scripts/print_headline.py` (run `make eval`); do not edit by hand. All data is synthetic.
> Cited by the Phase 3 methodology memo. Method and caveats: [ADR-003](decisions/ADR-003-identity-resolution.md) and
> [identity_resolution.md](identity_resolution.md).

## Headline: matcher quality before any steward review

Pairwise precision, recall and F1 are measured on **final clusters** against the generator's answer key. "AUTO" merges
only automatic matches; "AUTO_PLUS_PROBABLE" also merges every probable pair.

| Matcher | Stage | Scope | Precision | Recall | F1 | Sibling/twin merges | Predicted vs true participants |
|---|---|---|---|---|---|---|---|
| rules | PRE_REVIEW | AUTO | 0.99938 | 0.92276 | 0.95954 | 2 | 6513 vs 6000 |
| rules | PRE_REVIEW | AUTO_PLUS_PROBABLE | 0.99940 | 0.94766 | 0.97284 | 2 | 6358 vs 6000 |
| fs_naive | PRE_REVIEW | AUTO | 0.96349 | 0.99993 | 0.98137 | 86 | 5906 vs 6000 |
| fs_naive | PRE_REVIEW | AUTO_PLUS_PROBABLE | 0.93419 | 0.99993 | 0.96594 | 152 | 5808 vs 6000 |
| fs | PRE_REVIEW | AUTO | 0.99907 | 0.99964 | 0.99936 | 2 | 6000 vs 6000 |
| fs | PRE_REVIEW | AUTO_PLUS_PROBABLE | 0.99470 | 0.99975 | 0.99722 | 5 | 5983 vs 6000 |

The committed `review_decisions` seed holds 0 decisions, so POST_REVIEW rows equal PRE_REVIEW rows. A simulated
steward (`make steward-demo`) uses the answer key; its rows are never matcher performance.

## Scale

- 17,530 registrations resolve to 6,000 participants (4,133 are minors at the latest season).
- Blocking: 66,826 candidate pairs of 149,861,328 possible
  (reduction ratio 0.99955); pair completeness **1.000**
  (27,951 true pairs, 3,661 linked by a source id,
  6 missed by blocking).

## Thresholds in use

| matcher_version | t_auto | t_review | prior_odds |
|---|---|---|---|
| fs | 0.99700 | 0.85000 | 0.10000 |
| fs_naive | 0.99000 | 0.50000 | 0.10000 |

## Errors at the AUTO scope (before review)

| matcher | error_type | likely_cause | pairs |
|---|---|---|---|
| fs | FALSE_NEGATIVE | BELOW_THRESHOLD | 3 |
| fs | FALSE_NEGATIVE | GUARD_OVERRIDE | 5 |
| fs | FALSE_NEGATIVE | NAME_CHANGE | 2 |
| fs | FALSE_POSITIVE | OTHER | 4 |
| fs | FALSE_POSITIVE | SIBLING | 16 |
| fs | FALSE_POSITIVE | TRANSITIVE_CHAIN | 6 |
| fs_naive | FALSE_NEGATIVE | NAME_CHANGE | 2 |
| fs_naive | FALSE_POSITIVE | SIBLING | 102 |
| fs_naive | FALSE_POSITIVE | TWIN | 98 |
| rules | FALSE_NEGATIVE | BELOW_THRESHOLD | 197 |
| rules | FALSE_NEGATIVE | GUARD_OVERRIDE | 3 |
| rules | FALSE_POSITIVE | SIBLING | 16 |

`fs_naive` false positives are capped at the first 200 pairs per kind.

## Review queue and cluster integrity

| item_type | suggested_action | items |
|---|---|---|
| CLUSTER_CONFLICT | SPLIT_CLUSTER | 13 |
| PROBABLE_PAIR | CONFIRM_MATCH | 22 |
| PROBABLE_PAIR | CONFIRM_NON_MATCH | 81 |

13 clusters carry an open integrity issue (`idr_cluster_integrity`).

## What this means for counting

- The final matcher (`fs`) counts participants almost exactly (see the Predicted vs true column), but that is partly two
  wrong merges and two wrong splits cancelling out; Phase 3 reports an identity range instead of a single number.
- At AUTO + PROBABLE the matcher merges some siblings (see Sibling/twin merges); the point estimate uses AUTO only.
- This is a synthetic population: phone numbers never change, one nickname list covers every generated nickname, and
  blocking completeness of 1.000 is a property of this data.
