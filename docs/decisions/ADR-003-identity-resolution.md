# ADR-003: Identity resolution in SQL

- **Status:** Accepted (Phase 2)
- **Context:** Phase 1 produced one row per registration. Participation numbers need people. The task is to decide,
  in SQL only and without the matcher ever seeing the answer key, which registrations across seasons, leagues, clubs
  and countries belong to the same participant, then to measure the result against the (synthetic) truth. Two errors
  matter: **under-merging** inflates participation and breaks retention; **over-merging** undercounts, and worse, can
  apply one child's consent to a sibling. The project therefore **biases toward precision**.
> **Data window.** The figures in this ADR were measured on the original three-year window (2023 to 2025). Phase 4 extended the data to
> 2021 to 2025 (ADR-008), which changed them; the current figures are in `docs/phase2_results.md` and the scorecard. The decisions here
> stand; the thresholds were re-read on the new data, not re-tuned.

- All data is synthetic. Every number below comes from `make phase2` at the default configuration (seed 42).

## 1. Pre-flight findings

- `int_registrations_unioned` matched section 7.4 of the Phase 1 spec exactly, plus six lineage/DQ helper columns
  (`record_occurrence`, `source_file`, `source_row`, `is_exact_duplicate`, `is_near_duplicate`, `is_impossible_dob`).
  `registration_key` hashes the occurrence number as well as source system and record id, so exact copies have their
  own key. No Phase 1 column was renamed.
- `registration_truth` covers every registration, duplicates included. It must be joined on
  `(source_system, source_record_id)`, **not** on `source_file`: a CA pagination-overlap copy sits on a different page
  from the record the truth row points at.
- **Generator amendments.** *Twins:* 27 twin households (54 children, about 0.5% of youth households): same DOB,
  guardian, last name, league, club and seasons, different first names, sometimes the same sex. *Name changes:* the
  spec's 0.3% is under one person at this population size, so a minimum of 3 INTL adult women get a hyphenated or new
  family name in a later season. They **also get a new Player ID**, otherwise the source id would link them and there
  would be no false negative to study. Phase 1 tests still pass.
- **A later generator amendment (made during Phase 3, to exercise country counting):** half of the 100 cross-border
  movers also register in both countries in the year they move, so 55 participant-years span two countries. It shifted
  every number in this ADR slightly (the random draws changed), so all figures below are from the amended data. The
  evolution table in section 6 and the sweep selection in section 7 were measured *before* the amendment and are marked as
  such; the thresholds were re-read afterwards, not re-tuned.

## 2. Architecture

```
int_registrations_unioned
  -> idr_input_records          exact duplicates collapsed, impossible DOBs nulled, keys carried
  -> idr_deterministic_links    same member_uuid (CA); same Player ID (INTL, except Panama via a dbt var)
  -> idr_blocking_keys -> idr_candidate_pairs -> idr_pair_features        (levels, not scores)
  -> idr_pair_scores_rules  |  idr_u_probabilities -> idr_pair_scores_fs  (three matchers)
  -> idr_match_edges -> idr_clusters (recursive CTE) -> idr_cluster_integrity, idr_review_queue
  -> marts: bridge_registration_participant, dim_participant, participant_identifiers
evaluation/ (the only models that read ground truth): truth pairs, blocking, pairwise, clusters, sweep, segments, errors
```

`idr_blocking_keys`, the `eval_record_truth` helper and the `matcher` / `stage` / `scope` columns on edges and clusters are
additions to the spec tree: they let one run evaluate both matchers, before and after steward review, and at AUTO
versus AUTO + PROBABLE, on **final clusters**. The marts read only `var('matcher')` (default `fs`) at POST_REVIEW / AUTO.

## 3. Ground-truth isolation

Ground truth lives in schema `eval`, loaded by `make load-eval` (separate from `make load`) and declared as the dbt
source `ground_truth`. `scripts/check_eval_isolation.py` parses `target/manifest.json` and fails if any node outside
`models/evaluation/` has that source anywhere upstream. It is wired into `make test` and `make phase2`, has pytest
coverage on synthetic manifests, and was checked against a deliberately leaking model (it failed, as it should).

## 4. Blocking

Union of five blocks, de-duplicated, `record_a < record_b`, minus deterministic links: B1 birth year + last-name
prefix (3); B2 email + birth year; B3 phone + birth year; B4 last + first name; B5 email + first initial. No block on
exact DOB alone.

| Measure | Value |
|---|---|
| True pairs among 14,113 input records | 14,936 |
| Linked deterministically (never scored) | 1,599 |
| Found by blocking | 13,333 |
| Missed by blocking | **4** |
| **Pair completeness** (target 0.98) | **0.9997** |
| Candidate pairs / possible pairs | 44,611 / 99.6 M (reduction ratio 0.9996) |
| Largest block key | 40 records (limit 500) |
| True pairs found *only* by a block | B3 27, B4 16, B5 11, B1 0, B2 0 |

The 4 missed pairs belong to two people: one adult woman whose family name changed (a new surname, a new federation ID and
no contact data give every block nothing to share) and one person whose three pairs are still linked through other records.

**Caveat.** Synthetic phone numbers never change and guardian emails change in only 6% of re-registrations, so blocking
is easier here than it would be on real data. A completeness of 0.9997 is a property of this data, not a promise.

## 5. Features

Agreement **levels**, so both matchers share them (`macros/pair_features.sql`): first name (`EXACT`, `NICKNAME` through
`nickname_map` both ways, `FUZZY_HIGH` Jaro-Winkler >= 0.92, `FUZZY_LOW` >= 0.85, `DIFFERENT`, `MISSING`), last name
(same, no nickname; a hyphenated or compound surname that contains the other counts as `FUZZY_HIGH`), DOB (`EXACT`,
`DAY_MONTH_SWAPPED`, `SAME_YEAR_ONLY`, `YEAR_OFF_BY_ONE`, `DIFFERENT`, `MISSING`), email, phone, postal code (with a
zip3 / FSA `PREFIX` level), sex, and context (same org and season, same season elsewhere, different season). Name and
DOB logic live in macros with singular tests (accents, hyphens, nicknames both ways, swap order, leap day, siblings a
year apart). For Japan the swapped first/last comparison is also tried (`name_order_swapped`); in this data it never
fires because Japanese records link deterministically by Player ID.

**DuckDB to Snowflake** (new functions in Phase 2; Phase 1's list is in ADR-001):

| DuckDB | Snowflake |
|---|---|
| `jaro_winkler_similarity(a, b)` (0 to 1) | `JAROWINKLER_SIMILARITY(a, b)` (**0 to 100**: divide by 100, or scale the two threshold vars) |
| `damerau_levenshtein`, `strip_accents` | `EDITDISTANCE` (plain Levenshtein), accent-insensitive collation |
| `list_has_all(a, b)` | `ARRAY_CONTAINS` per token, or `ARRAYS_OVERLAP` with a size check |
| `hash(x) % n` | `ABS(HASH(x)) % n` |
| `WITH RECURSIVE` with `UNION` | `WITH RECURSIVE` (supported; `UNION` de-duplicates too) |
| `json_object(...)`, `to_json(struct_pack(...))`, `json_group_array` | `OBJECT_CONSTRUCT(...)`, `ARRAY_AGG(OBJECT_CONSTRUCT(...))` |
| `list(x)`, `list_distinct`, `list_sort`, `flatten`, `unnest` | `ARRAY_AGG`, `ARRAY_DISTINCT`, `ARRAY_SORT`, `ARRAY_FLATTEN`, `LATERAL FLATTEN` |
| `log2`, `pow` | `LOG(2, x)`, `POWER` |

## 6. Matchers

**A, rules baseline** (`idr_pair_scores_rules`): six ordered rules, first match wins; R4 is the sibling/twin guard.

**B, Fellegi-Sunter** (`idr_pair_scores_fs`): `weight = log2(m/u)` per feature level, summed; `MISSING` contributes 0;
`probability = 2^w L / (1 + 2^w L)`.

- **m** (`match_m_probabilities.csv`): assumed, every value with a written rationale from the source descriptions and
  the documented defect behaviour (for example `first_name EXACT 0.88` because typos and nicknames break exact
  equality about 12% of the time across a pair of records). **Never tuned against ground truth.**
- **u**: estimated with no labels from 204,527 random pairs drawn from *all* 99.6 M possible pairs (a hash filter, not
  from blocks), smoothed `(count + 0.5) / (n + 0.5 * levels)`. Assumption: a random pair is almost surely a non-match
  (about 15 thousand true pairs among 99.6 million).
- **L** (prior odds) = 0.1, assumed before any evaluation. Blocking later showed 30% of candidate pairs are true
  matches (odds about 0.43); I did **not** feed that back, as it would use the answer key. L only shifts probabilities, and
  the thresholds come from the sweep.
- **Hard overrides** (all variants): same org + season + different first name -> `NON_MATCH` (twin/sibling guard);
  both day-precision DOBs more than a year apart -> `NON_MATCH`; sex disagreement -> capped at `PROBABLE`.

### How the Fellegi-Sunter matcher evolved (disclosed)

The first, spec-literal version was evaluated, found wanting, and corrected. The corrections change the **model
structure**, not the m-values, but they were prompted by looking at the evaluation, so I record the sequence (all rows were
measured on the Phase 2 data *before* the Phase 3 generator amendment; the final numbers on the amended data are in
section 8):

| Step | AUTO precision | AUTO recall | Sibling/twin false-merge clusters | Merged clusters |
|---|---|---|---|---|
| `fs_naive`: independent features, three overrides (kept in the repo) | 0.9608 | 1.0000 | **80** (10.9% of 737 multi-child households; 13 twin) | 88 |
| + household guard; contact weights counted once (strongest by absolute value) | 0.9926 | 0.9996 | 2 | 21 |
| contact grouping reworked (strongest *positive* once, all *negative*); year-off-by-one cannot be AUTO | 0.9988 | 0.9996 | 1 | 9 |
| any disagreeing DOB cannot be AUTO (`DOB_DISAGREE_CAP`) | 0.9997 | 0.9996 | 0 | 3 |
| thresholds from the sweep: T_auto 0.997, T_review 0.85 | **0.99986** | 0.99959 | **0** | 2 |

**Why the naive model failed.** Fellegi-Sunter assumes features are conditionally independent given match status.
Email, phone and postal code are three views of one household, so siblings who share a guardian scored about 36 bits for
"same contact" and merged. Twins registered in a different season slipped past the same-season guard. The fixes:

1. **Count positive household evidence once, negative evidence every time.** The three contact fields agree together
   because they share a household (correlated). A changed email and a changed phone are separate events (independent).
2. **`HOUSEHOLD_GUARD`:** same email or phone with a clearly different first name is two people in one household.
3. **`DOB_DISAGREE_CAP`:** a disagreeing DOB (a year apart is exactly how siblings look) never reaches AUTO. The rules
   baseline's R5 also sends a year-off-by-one pair to review.

The trade-off is explicit: the household guard costs 9 true pairs on the amended data (6 before it; see the error analysis).

## 7. Thresholds (chosen once from the sweep)

`eval_threshold_sweep` evaluates 20 thresholds from 0.50 to 0.999 on final clusters. The choice was made on the Phase 2
data before the Phase 3 generator amendment; selected rows for `fs` (the review-queue columns were read with the initial
0.99 / 0.50 settings):

| Threshold | False merged pairs | Precision | Recall | Sibling/twin merges | Queue if T_auto | Queue if T_review |
|---|---|---|---|---|---|---|
| 0.50 | 152 | 0.9897 | 0.9996 | 0 | 30 | 112 |
| 0.85 | 29 | 0.9980 | 0.9996 | 0 | 93 | 48 |
| 0.97 | 5 | 0.9997 | 0.9996 | 0 | 112 | 23 |
| 0.99 | 5 | 0.9997 | 0.9996 | 0 | 112 | 20 |
| 0.997 | 2 | 0.9999 | 0.9996 | 0 | 115 | 12 |
| 0.999 | 2 | 0.9999 | 0.9996 | 0 | 116 | 12 |

- **T_auto = 0.997.** It removed 3 false pairs (5 to 2) at the cost of 3 review items (112 to 115).
- **T_review = 0.85.** Recall was flat from 0.50 to 0.999: the missed pairs were ruled out by the household guard, which
  no threshold can undo. A lower T_review only adds queue noise; 0.85 cut the queue from 112 to 48.

**Re-read on the amended data (not re-tuned).** After the generator amendment the sweep was read again, with the seeded
0.997 / 0.85 for the queue columns:

| Threshold | False merged pairs | Precision | Recall | Sibling/twin merges | Queue if T_auto | Queue if T_review |
|---|---|---|---|---|---|---|
| 0.50 | 148 | 0.9902 | 0.9993 | 0 | 30 | 113 |
| 0.85 | 66 | 0.9956 | 0.9993 | 0 | 30 | 64 |
| 0.97 | 43 | 0.9971 | 0.9993 | 0 | 54 | 34 |
| 0.98 | 5 | 0.9997 | 0.9993 | 0 | 63 | 22 |
| 0.997 | 4 | 0.9997 | 0.9993 | 0 | 64 | 12 |
| 0.999 | 4 | 0.9997 | 0.9993 | 0 | 64 | 12 |

The conclusion holds. Recall is flat at 0.9993 across the grid and precision is flat from 0.98 to 0.995, so 0.997 (one more
false pair removed, one more review item) and 0.85 (queue 113 to 64) sit on the same plateaus. A cut-off chosen at 0.98 would
have done almost as well, which is the honest reading: the model's probabilities are bimodal, so the exact threshold barely
matters here. Final tiers on the amended data: 13,319 `AUTO_MATCH`, 64 `PROBABLE`, 31,228 `NON_MATCH` pairs. The committed
`docs/eval/threshold_sweep.csv` is read with the final thresholds and is the input for the Phase 4 chart.

**Calibration.** 13,604 scored pairs sit at probability 0.997 or above and 13,333 of them are true matches (the rest are
sibling or look-alike pairs that a guard or cap keeps out of AUTO). Below 0.997 there are 31,007 scored pairs and **none** is a
true match. The model is confident and, on this data, right; but the review queue (62 `PROBABLE` pairs, 0 true matches) is
mostly capped look-alikes, so it demonstrates the workflow more than it finds errors.

## 8. Results and error analysis (before any steward review, amended data)

| Matcher | Scope | Precision | Recall | F1 | Sibling/twin merges | Predicted vs true participants |
|---|---|---|---|---|---|---|
| Rules baseline | AUTO | 1.0000 | 0.9219 | 0.9594 | 0 | 6,398 vs 6,000 |
| Rules baseline | AUTO + PROBABLE | 0.9996 | 0.9475 | 0.9729 | 1 | 6,267 vs 6,000 |
| FS, spec-literal (`fs_naive`) | AUTO | 0.9664 | 0.9999 | 0.9829 | 75 | 5,918 vs 6,000 |
| **FS (`fs`)** | **AUTO** | **0.99973** | **0.99933** | **0.99953** | **0** | **6,002 vs 6,000** |
| FS (`fs`) | AUTO + PROBABLE | 0.9935 | 0.9993 | 0.9964 | 3 | 5,985 vs 6,000 |

The 6,002 vs 6,000 hides 2 wrong merges and 4 wrongly separated people that partly cancel out.

**Against the metric targets.** FS AUTO precision >= 0.99: **met**. FS recall (AUTO + PROBABLE) >= 0.95: **met**. Sibling/twin
merges <= 0.1% of 737 multi-child households: **met at AUTO (0)**, **not met at AUTO + PROBABLE (3, or 0.41%)**, which is
what the review queue is for. **"FS beats the rules baseline on sibling/twin merges": not met.** At AUTO they tie at 0.
The baseline's R4 guard and its strict first-name rules already protect siblings; FS wins on recall (0.9993 vs 0.922)
and on counting people (6,002 vs 6,398), not on this metric. After a simulated steward resolved the top 20 queue items
(70 decisions) the AUTO + PROBABLE sibling merges fell from 3 to 1 and merged clusters from 19 to 16 (a simulated steward
uses the ground truth, so those rows are not matcher performance).

**Where the errors are** (`eval_errors`, `eval_segments`):

- **10 false negatives for `fs`: 9 `GUARD_OVERRIDE`, 1 `NAME_CHANGE`.** The nine are US-US pairs with the same last name,
  DOB, email and phone but a different first name on one registration, so `HOUSEHOLD_GUARD` blocked them. That is the
  price of the precision-first rule. The tenth is the name-change woman below.
- **4 false positives (`OTHER`), in 2 clusters.** CA-INTL pairs with the same first name, a near-identical surname and the
  same birth year (the CA record has year precision), and no contact data on the INTL side. Nothing in the data
  distinguishes them; the integrity checks cannot flag them either (5 clusters were flagged, all weak bridges, none truly
  merged).
- **Name changes: two of three are found.** First name plus an exact DOB (about 20 bits together) outweighs a different
  surname for the hyphenated and the unrelated-surname cases that carry any contact signal. The one missed (a new surname,
  a new federation ID and no contact data) is **never proposed as a candidate pair**, because no block shares a key: a
  genuine known-hard false negative and one of the 4 true pairs lost to blocking.
- **Rules baseline:** its recall losses are a last-name typo with exact DOB and contact (about 260 pairs), swapped
  day/month (about 245), a nulled impossible DOB (about 125) and first-name or last-name typos below the 0.92 line (about
  50 each), none of which its few rules cover. By defect type its recall is 0.00 on name typos (788 pairs) and 0.02 on
  swapped DOBs (278), against 0.99 and 1.00 for `fs`.
- **By source pair** (`fs`, AUTO): US-US recall 0.9993, US-CA (cross-border, 325 pairs) 1.000, CA-CA 1.000, INTL-INTL
  0.9988; precision 1.000 in each. The rules baseline reaches 0.910 on US-US and 0.972 on US-CA.

## 9. Limitations and the production path

- **Synthetic data flatters the matcher:** stable phones, one canonical spelling per name, and a nickname map that
  covers every nickname the generator can emit (the map is a general list of common nicknames; a real feed would hold
  nicknames it lacks).
- **No term-frequency adjustment:** `u` is one value per level, so a common surname gets the same weight as a rare one.
  A production matcher would weight by name frequency.
- **m is assumed, not estimated.** An EM estimate (not built here) would be the next step and should be compared with
  the assumed values.
- **Families with shared contacts and a shared birthday** (twins, siblings with the same first name) cannot be separated
  by any of these signals; they go to a steward.
- **Production path:** an entity-resolution library such as Splink or Zingg would give EM estimation, term-frequency
  adjustment and scale. This project shows the method in SQL.
- The simple participant-ID scheme and its production replacement are in ADR-004.

## Consequences

`make phase2` runs everything end to end (about 55 seconds): 131 dbt tests, the pytest suite, the isolation check and an ID
stability check. The model is auditable (every link carries a reason and a per-feature weight breakdown) and the
evaluation is reproducible, but its headline numbers describe this synthetic population, not real-world performance.
