# Phase 2 results: identity resolution

> **Generated** by `scripts/print_headline.py` (run `make eval`); do not edit by hand. All data is synthetic.
> Cited by the Phase 3 methodology memo. Method and caveats: [ADR-003](decisions/ADR-003-identity-resolution.md) and
> [identity_resolution.md](identity_resolution.md).

## Headline: matcher quality before any steward review

Pairwise precision, recall and F1 are measured on **final clusters** against the generator's answer key. "AUTO" merges
only automatic matches; "AUTO_PLUS_PROBABLE" also merges every probable pair.

| Matcher | Stage | Scope | Precision | Recall | F1 | Sibling/twin merges | Predicted vs true participants |
|---|---|---|---|---|---|---|---|
| rules | PRE_REVIEW | AUTO | 0.99995 | 0.92735 | 0.96229 | 0 | 16044 vs 15000 |
| rules | PRE_REVIEW | AUTO_PLUS_PROBABLE | 0.99996 | 0.94855 | 0.97358 | 0 | 15750 vs 15000 |
| fs_naive | PRE_REVIEW | AUTO | 0.96622 | 1.00000 | 0.98282 | 213 | 14765 vs 15000 |
| fs_naive | PRE_REVIEW | AUTO_PLUS_PROBABLE | 0.90735 | 1.00000 | 0.95142 | 352 | 14395 vs 15000 |
| fs | PRE_REVIEW | AUTO | 0.99810 | 0.99985 | 0.99897 | 9 | 14991 vs 15000 |
| fs | PRE_REVIEW | AUTO_PLUS_PROBABLE | 0.98732 | 0.99987 | 0.99355 | 18 | 14905 vs 15000 |

The committed `review_decisions` seed holds 0 decisions, so POST_REVIEW rows equal PRE_REVIEW rows. A simulated
steward (`make steward-demo`) uses the answer key; its rows are never matcher performance.

## Scale

- 37,677 registrations resolve to 14,991 participants (11,172 are minors at the latest season).
- Blocking: 244,977 candidate pairs of 692,459,505 possible
  (reduction ratio 0.99965); pair completeness **1.000**
  (47,173 true pairs, 5,777 linked by a source id,
  16 missed by blocking).

## Thresholds in use

| matcher_version | t_auto | t_review | prior_odds |
|---|---|---|---|
| fs | 0.99700 | 0.85000 | 0.10000 |
| fs_naive | 0.99000 | 0.50000 | 0.10000 |

## Errors at the AUTO scope (before review)

| matcher | error_type | likely_cause | pairs |
|---|---|---|---|
| fs | FALSE_NEGATIVE | BELOW_THRESHOLD | 1 |
| fs | FALSE_NEGATIVE | GUARD_OVERRIDE | 6 |
| fs | FALSE_POSITIVE | OTHER | 18 |
| fs | FALSE_POSITIVE | TRANSITIVE_CHAIN | 9 |
| fs | FALSE_POSITIVE | TWIN | 63 |
| fs_naive | FALSE_POSITIVE | TWIN | 200 |
| rules | FALSE_NEGATIVE | BELOW_THRESHOLD | 195 |
| rules | FALSE_NEGATIVE | BLOCKING_MISS | 3 |
| rules | FALSE_NEGATIVE | GUARD_OVERRIDE | 1 |
| rules | FALSE_NEGATIVE | NAME_CHANGE | 1 |
| rules | FALSE_POSITIVE | OTHER | 2 |

`fs_naive` false positives are capped at the first 200 pairs per kind.

## Review queue and cluster integrity

| item_type | suggested_action | items |
|---|---|---|
| CLUSTER_CONFLICT | SPLIT_CLUSTER | 29 |
| PROBABLE_PAIR | CONFIRM_MATCH | 256 |
| PROBABLE_PAIR | CONFIRM_NON_MATCH | 173 |

29 clusters carry an open integrity issue (`idr_cluster_integrity`).

## What this means for counting

- The final matcher (`fs`) counts participants almost exactly (see the Predicted vs true column), but that is partly two
  wrong merges and two wrong splits cancelling out; Phase 3 reports an identity range instead of a single number.
- At AUTO + PROBABLE the matcher merges some siblings (see Sibling/twin merges); the point estimate uses AUTO only.
- This is a synthetic population: phone numbers never change, one nickname list covers every generated nickname, and
  blocking completeness of 1.000 is a property of this data.
