# Phase 2 results: identity resolution

> **Generated** by `scripts/print_headline.py` (run `make eval`); do not edit by hand. All data is synthetic.
> Cited by the Phase 3 methodology memo. Method and caveats: [ADR-003](decisions/ADR-003-identity-resolution.md) and
> [identity_resolution.md](identity_resolution.md).

## Headline: matcher quality before any steward review

Pairwise precision, recall and F1 are measured on **final clusters** against the generator's answer key. "AUTO" merges
only automatic matches; "AUTO_PLUS_PROBABLE" also merges every probable pair.

| Matcher | Stage | Scope | Precision | Recall | F1 | Sibling/twin merges | Predicted vs true participants |
|---|---|---|---|---|---|---|---|
| rules | PRE_REVIEW | AUTO | 1.00000 | 0.91645 | 0.95640 | 0 | 14415 vs 13368 |
| rules | PRE_REVIEW | AUTO_PLUS_PROBABLE | 1.00000 | 0.93503 | 0.96643 | 0 | 14208 vs 13368 |
| fs_naive | PRE_REVIEW | AUTO | 0.96989 | 0.99809 | 0.98379 | 153 | 13222 vs 13368 |
| fs_naive | PRE_REVIEW | AUTO_PLUS_PROBABLE | 0.91229 | 0.99809 | 0.95326 | 270 | 12897 vs 13368 |
| fs | PRE_REVIEW | AUTO | 0.99824 | 0.99688 | 0.99756 | 7 | 13395 vs 13368 |
| fs | PRE_REVIEW | AUTO_PLUS_PROBABLE | 0.98635 | 0.99710 | 0.99169 | 13 | 13314 vs 13368 |

The committed `review_decisions` seed holds 0 decisions, so POST_REVIEW rows equal PRE_REVIEW rows. A simulated
steward (`make steward-demo`) uses the answer key; its rows are never matcher performance.

## Scale

- 30,051 registrations resolve to 13,395 participants (9,910 are minors at the latest season).
- Blocking: 153,170 candidate pairs of 440,466,040 possible
  (reduction ratio 0.99965); pair completeness **0.997**
  (31,369 true pairs, 3,413 linked by a source id,
  82 missed by blocking).

## Thresholds in use

| matcher_version | t_auto | t_review | prior_odds |
|---|---|---|---|
| fs | 0.99700 | 0.85000 | 0.10000 |
| fs_naive | 0.99000 | 0.50000 | 0.10000 |

## Errors at the AUTO scope (before review)

| matcher | error_type | likely_cause | pairs |
|---|---|---|---|
| fs | FALSE_NEGATIVE | BELOW_THRESHOLD | 7 |
| fs | FALSE_NEGATIVE | BLOCKING_MISS | 62 |
| fs | FALSE_NEGATIVE | GUARD_OVERRIDE | 29 |
| fs | FALSE_POSITIVE | OTHER | 9 |
| fs | FALSE_POSITIVE | TRANSITIVE_CHAIN | 8 |
| fs | FALSE_POSITIVE | TWIN | 38 |
| fs_naive | FALSE_NEGATIVE | BLOCKING_MISS | 60 |
| fs_naive | FALSE_POSITIVE | SIBLING | 38 |
| fs_naive | FALSE_POSITIVE | TWIN | 162 |
| rules | FALSE_NEGATIVE | BELOW_THRESHOLD | 189 |
| rules | FALSE_NEGATIVE | BLOCKING_MISS | 7 |
| rules | FALSE_NEGATIVE | GUARD_OVERRIDE | 3 |
| rules | FALSE_NEGATIVE | NAME_CHANGE | 1 |

`fs_naive` false positives are capped at the first 200 pairs per kind.

## Review queue and cluster integrity

| item_type | suggested_action | items |
|---|---|---|
| CLUSTER_CONFLICT | SPLIT_CLUSTER | 14 |
| PROBABLE_PAIR | CONFIRM_MATCH | 148 |
| PROBABLE_PAIR | CONFIRM_NON_MATCH | 110 |

14 clusters carry an open integrity issue (`idr_cluster_integrity`).

## What this means for counting

- The final matcher (`fs`) counts participants almost exactly (see the Predicted vs true column), but that is partly two
  wrong merges and two wrong splits cancelling out; Phase 3 reports an identity range instead of a single number.
- At AUTO + PROBABLE the matcher merges some siblings (see Sibling/twin merges); the point estimate uses AUTO only.
- This is a synthetic population: phone numbers never change, one nickname list covers every generated nickname, and
  blocking completeness of 1.000 is a property of this data.
