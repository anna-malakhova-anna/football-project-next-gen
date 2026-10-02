# Counting Flag Football — Phase 2 Spec: Identity Resolution

**Phase 2 goal:** Turn registrations into people. Decide which records across seasons, leagues, clubs, and countries belong to the same participant, using SQL only, without ever looking at the answer key. Then measure how well that worked against the answer key.

**Builds on:** Phase 1 (`int_registrations_unioned`, seeds, macros, ground truth in `data/ground_truth/`).

**Why this phase matters (put this in the README):** Every participation number in Phase 3 depends on it. Two kinds of error matter:
- **Under-merging** (one kid split into two records) inflates participation and breaks retention.
- **Over-merging** (two kids collapsed into one) undercounts participation. Worse, it can apply one child's consent preferences to a sibling.

That second risk is why this project **biases toward precision**. A sibling false merge is a privacy incident; a missed match is a reporting error.

---

## 0. Pre-flight (do this before writing any Phase 2 code)

1. Read the actual Phase 1 models and confirm the column names in `int_registrations_unioned` match section 7.4 of the Phase 1 spec. If they differ, **use what Phase 1 built** and note any differences in `docs/decisions/ADR-003-identity-resolution.md`. Don't rename Phase 1 columns.
2. Run `make all` and confirm Phase 1 still passes.
3. Confirm `data/ground_truth/registration_truth.parquet` covers **every** source record, including injected duplicates. If not, fix the generator first.
4. **Generator amendment: twins.** Add twins to the population. About 0.5% of youth households should have twins: same guardian email, same DOB, same last name, same league and season, different first names (and sometimes the same sex). This is the hardest false-merge trap and the evaluation needs it. Add a pytest that confirms twins exist.
5. **Generator amendment: name-change edge case.** About 0.3% of adult women's players in INTL should appear with a different family name in a later season (marriage or hyphenation). This gives you a deliberate known-hard false negative to discuss in error analysis.
6. Re-run `make all` after the amendments and confirm Phase 1 tests still pass. Defect-rate checks may need updated expected values.

---

## 1. Principles

1. **The matcher never sees ground truth.** Ground truth is loaded into a separate `eval` schema and is referenced **only** by models in `models/evaluation/`. A test enforces this (section 9).
2. **Everything is explainable.** Every link between two records carries the reason it was made: which rule or which feature weights. No black-box scores.
3. **Two matchers, compared honestly.** Build a simple deterministic **rules baseline** first, then a **probabilistic (Fellegi–Sunter) matcher**. The evaluation compares them. "Here's the baseline, here's what probabilistic matching bought us" is the story.
4. **Precision first.** Thresholds are chosen to keep sibling and twin false merges near zero, and the trade-off is documented.
5. **Stable IDs.** Re-running the pipeline on the same data produces the same `participant_id` values.
6. **Humans close the loop.** Uncertain matches go to a review queue, and steward decisions feed back as overrides.

---

## 2. New repo structure (additions only)

```
dbt/
├── seeds/
│   ├── nickname_map.csv               # given name <-> nickname pairs, EN + FR + ES
│   ├── match_m_probabilities.csv      # assumed m-probabilities per feature level
│   ├── match_thresholds.csv           # tier cut-offs (one row per matcher version)
│   └── review_decisions.csv           # steward overrides (starts empty, header only)
├── models/
│   ├── identity/
│   │   ├── idr_input_records.sql
│   │   ├── idr_deterministic_links.sql
│   │   ├── idr_candidate_pairs.sql
│   │   ├── idr_pair_features.sql
│   │   ├── idr_u_probabilities.sql
│   │   ├── idr_pair_scores_rules.sql
│   │   ├── idr_pair_scores_fs.sql
│   │   ├── idr_match_edges.sql
│   │   ├── idr_clusters.sql
│   │   ├── idr_cluster_integrity.sql
│   │   ├── idr_review_queue.sql
│   │   └── _identity.yml
│   ├── marts/
│   │   ├── dim_participant.sql
│   │   ├── bridge_registration_participant.sql
│   │   ├── participant_identifiers.sql
│   │   └── _marts.yml
│   └── evaluation/
│       ├── eval_truth_pairs.sql
│       ├── eval_blocking.sql
│       ├── eval_pairwise.sql
│       ├── eval_threshold_sweep.sql
│       ├── eval_clusters.sql
│       ├── eval_segments.sql
│       ├── eval_errors.sql
│       └── _evaluation.yml
├── macros/
│   ├── name_similarity.sql
│   └── dob_agreement_level.sql
loader/
│   └── load_eval.py                   # ground truth -> eval schema
scripts/
│   ├── check_eval_isolation.py        # reads dbt manifest, fails on leakage
│   └── simulate_steward.py            # optional; see section 8
docs/
├── identity_resolution.md             # business-facing explainer
└── decisions/
    ├── ADR-003-identity-resolution.md
    └── ADR-004-participant-id-stability.md
```

Makefile additions:
```
make load-eval   # load ground truth into eval schema
make idr         # dbt run --select identity marts
make eval        # dbt run --select evaluation + print headline metrics
make phase2      # all + load-eval + idr + eval + tests + isolation check
```

---

## 3. Input and deterministic links

### `idr_input_records`
One row per registration from `int_registrations_unioned`, with:
- **Exact duplicates collapsed** (keep the earliest `registered_at`; carry the collapsed keys forward so the bridge table can still map every registration)
- **Records flagged `is_impossible_dob` kept in**, with DOB nulled for matching. They can still match on name, email, and phone.
- A `match_record_id` (the surviving registration key)

### `idr_deterministic_links`
Links that need no scoring, because the source itself says "same person":
- **CA_CLUB:** same `source_person_id` (`member_uuid`). It's stable within a club.
- **INTL_FED:** same `source_person_id` for countries where IDs are stable across years. Panama is excluded; read the exclusion from a seed or config, not a hardcoded value.
- **US_LEAGUE:** none (the source has no person ID)

Each link gets `link_method = 'SOURCE_ID'` and `link_tier = 'DETERMINISTIC'`.

---

## 4. Blocking (candidate generation)

Comparing every record with every other record is ~n²/2 pairs. Blocking limits comparisons to plausible candidates. Use the **union** of these blocks, then deduplicate pairs and always order them so `record_a < record_b`.

| Block | Key | Catches |
|---|---|---|
| B1 | `birth_year` + first 3 chars of `last_name_key` | Most re-registrations, typos in first name |
| B2 | `contact_email` + `birth_year` | Re-registrations with name changes or nicknames |
| B3 | `contact_phone` + `birth_year` | Email changed between seasons |
| B4 | `last_name_key` + `first_name_key` (any birth year) | Swapped day/month, CA birth-year-off-by-one, cross-border |
| B5 | `contact_email` + first initial | Birth-year errors where the email is stable |

Rules:
- Exclude pairs already linked deterministically
- **Don't block on exact `dob` alone.** It's too coarse for common birthdays.
- Record which block(s) produced each pair (`blocks_hit` list). The evaluation uses it.
- Log block sizes. If any single block key produces > 500 records, the key is too weak. Report it in `eval_blocking` and in the ADR.

Output: `idr_candidate_pairs` (`record_a`, `record_b`, `blocks_hit`).

---

## 5. Comparison features

`idr_pair_features`: one row per candidate pair. Each feature is an **agreement level**, not a raw score, so it can feed both matchers.

| Feature | Levels |
|---|---|
| `first_name_level` | `EXACT` (keys equal) · `NICKNAME` (via `nickname_map`, both directions) · `FUZZY_HIGH` (Jaro–Winkler ≥ 0.92) · `FUZZY_LOW` (≥ 0.85) · `DIFFERENT` · `MISSING` |
| `last_name_level` | `EXACT` · `FUZZY_HIGH` · `FUZZY_LOW` · `DIFFERENT` · `MISSING` |
| `dob_level` | `EXACT` · `DAY_MONTH_SWAPPED` · `SAME_YEAR_ONLY` (one or both records have YEAR precision and the years match) · `YEAR_OFF_BY_ONE` · `DIFFERENT` · `MISSING` |
| `email_level` | `EXACT` · `DIFFERENT` · `MISSING` |
| `phone_level` | `EXACT` · `DIFFERENT` · `MISSING` |
| `postal_level` | `EXACT` · `PREFIX` (US zip3 / CA FSA) · `DIFFERENT` · `MISSING` |
| `sex_level` | `AGREE` · `DISAGREE` · `UNKNOWN` (either is U) |
| `context_level` | `SAME_ORG_SAME_SEASON` · `SAME_SEASON_DIFF_ORG` · `DIFF_SEASON` |
| `source_pair` | e.g. `US-US`, `CA-CA`, `US-CA` (descriptive, not scored) |

Implementation notes:
- Put name comparison logic in the `name_similarity` macro and DOB logic in `dob_agreement_level`. Each macro gets singular tests with handwritten edge cases (accents, hyphens, Japanese name order, swapped day/month, Feb 29).
- DuckDB has `jaro_winkler_similarity`, `damerau_levenshtein`, and `strip_accents`. List the Snowflake equivalents in ADR-003 (`JAROWINKLER_SIMILARITY` returns 0–100, so the scale differs).
- For the INTL Japan sheet, also compare against the **swapped** first/last name and take the better match. Record `name_order_swapped = true` when that wins.

### The sibling and twin signal
`SAME_ORG_SAME_SEASON` combined with a `DIFFERENT` first name and the same email is a strong **non-match** signal: two kids in the same family registered together. Make sure it's represented. It's the main thing the rules baseline will get wrong.

---

## 6. Matcher A — rules baseline

`idr_pair_scores_rules`: an ordered list of rules. The first match wins. Each rule assigns a tier and a `rule_id`.

| Rule | Condition | Tier |
|---|---|---|
| R1 | first EXACT/NICKNAME + last EXACT + dob EXACT | AUTO_MATCH |
| R2 | first EXACT/NICKNAME + last EXACT + dob SAME_YEAR_ONLY + (email or phone EXACT) | AUTO_MATCH |
| R3 | first FUZZY_HIGH + last EXACT + dob EXACT/DAY_MONTH_SWAPPED | PROBABLE |
| R4 | email EXACT + dob EXACT + first DIFFERENT | **NON_MATCH** (sibling/twin guard) |
| R5 | last EXACT + dob YEAR_OFF_BY_ONE + first EXACT + (email or phone EXACT) | PROBABLE |
| R6 | everything else | NON_MATCH |

Keep it deliberately simple. Its job is to be a credible baseline, not to win.

---

## 7. Matcher B — probabilistic (Fellegi–Sunter)

The core SQL showcase of Phase 2.

### 7.1 u-probabilities (estimated from data)
`u` = the probability that two **random non-matching** records agree at a given level.

`idr_u_probabilities`:
- Sample ~200,000 random record pairs **across the whole input, not from blocks**, using a deterministic sample (`USING SAMPLE … REPEATABLE (42)` or a hash-based filter)
- Compute the same feature levels on the sample
- `u(feature, level) = count at level / total sampled pairs`
- Random pairs are overwhelmingly non-matches, so this is a standard, label-free estimate. State that assumption in the ADR.

### 7.2 m-probabilities (assumed, documented)
`m` = the probability that two records of the **same** person agree at a given level. Set these in `match_m_probabilities.csv`, with a `rationale` column for each value. Example: `first_name EXACT m = 0.88` because nicknames and typos break exact matches about 12% of the time. Values must be reasoned from the source descriptions, **not** tuned against ground truth. Tuning m against the answer key would be leakage.

Optional stretch (only if time allows): estimate m with EM in SQL, and compare it against the assumed values in the ADR.

### 7.3 Scoring
`idr_pair_scores_fs`: for each pair and feature,
`weight = log2(m / u)` for the observed level. `MISSING` contributes 0.

`match_weight = Σ weights`, and
`match_probability = 2^w × λ / (1 + 2^w × λ)`, where λ is the prior odds of a match among candidate pairs. Set λ from a stated assumption and document it.

Keep a per-feature weight breakdown column (struct or JSON) so any score can be explained line by line.

### 7.4 Hard overrides (applied after scoring)
- `sex_level = DISAGREE` **and** both are F/M: cap at PROBABLE
- `context_level = SAME_ORG_SAME_SEASON` **and** `first_name_level = DIFFERENT`: force NON_MATCH (twin/sibling guard)
- `dob_level = DIFFERENT` with both records at DAY precision, and the years > 1 apart: force NON_MATCH

### 7.5 Tiers
Read the thresholds from `match_thresholds.csv`:
- `AUTO_MATCH`: probability ≥ T_auto
- `PROBABLE`: T_review ≤ probability < T_auto → review queue
- `NON_MATCH`: below T_review

Initial values are set by reasoning. Final values are chosen with the threshold sweep (section 10), and the choice is justified in ADR-003. **Choosing thresholds from the evaluation is allowed and normal**. Make the choice once, document it, and don't iterate on m-values against truth.

---

## 8. Edges, clusters, integrity, review

### `idr_match_edges`
Union of:
- Deterministic links
- AUTO_MATCH pairs from the **active** matcher. Set it with a dbt var `matcher: fs | rules`, default `fs`.
- Steward MATCH decisions from `review_decisions.csv`

Minus steward NO_MATCH decisions. Each edge keeps `link_method` (`SOURCE_ID`, `RULES`, `FS`, `STEWARD`).

### `idr_clusters`: connected components in SQL
- Treat edges as undirected. Use a recursive CTE to compute, for each record, the set of reachable records, then `cluster_id = min(reachable record)`.
- Records with no edges become singleton clusters.
- Add a guard: if the recursion exceeds N iterations or any cluster exceeds the plausible maximum size (computed from seasons × terms × max concurrent leagues, documented), fail loudly.

### `idr_cluster_integrity`
Transitive chains are how siblings get merged (A≈B, B≈C, but A≠C). Flag clusters with:
- Two or more distinct DAY-precision DOBs more than 1 day apart (excluding swapped day/month)
- Both F and M present
- Two records in the **same org and same season** with different first names (a sibling inside a cluster)
- Size above the plausible maximum
- Any internal pair scored NON_MATCH by the active matcher (a "weak bridge")

Each flagged cluster gets an `integrity_issue` list and goes to review.

### `idr_review_queue`
One row per item, with side-by-side attributes for both records (or cluster members), the feature levels, the weight breakdown, and a `priority`:
- Conflicted clusters first
- Then PROBABLE pairs, ordered by how close they are to T_auto
- Include a `suggested_action` (`CONFIRM_MATCH`, `SPLIT_CLUSTER`, `CONFIRM_NON_MATCH`)

### `scripts/simulate_steward.py` (optional, clearly labelled)
To demo the feedback loop, this script resolves the top N queue items using ground truth, as a stand-in for a human steward, and writes them to `review_decisions.csv`. The evaluation must report metrics **before and after** steward decisions as separate rows, and the README must say the steward was simulated. Never present post-steward metrics as matcher performance.

---

## 9. Ground truth isolation

- `loader/load_eval.py` loads `person_registry.parquet` and `registration_truth.parquet` into schema `eval`. It's a separate command from `make load`.
- Declare the `eval` tables as a dbt source named `ground_truth`.
- `scripts/check_eval_isolation.py` parses `dbt/target/manifest.json`. It fails if any node outside `models/evaluation/` has `ground_truth` anywhere in its upstream lineage. Wire it into `make phase2` and `make test`.
- The Phase 1 test "ground truth never in raw schema" stays, and must still pass.

---

## 10. Evaluation (`models/evaluation/`)

Every evaluation model can be computed for both matchers (`matcher` column) and for before/after steward decisions (`stage` column: `PRE_REVIEW`, `POST_REVIEW`).

### `eval_truth_pairs`
All true matching pairs among `idr_input_records`, using `registration_truth` and accounting for collapsed duplicates. This is the denominator for recall.

### `eval_blocking`
- **Pair completeness:** % of true pairs that appear in candidate pairs. If this is low, no scoring can fix it.
- **Reduction ratio:** 1 − candidate pairs / all possible pairs
- Completeness by block: which blocks contribute unique true pairs (could any block be dropped?)
- Largest block keys

### `eval_pairwise`
Precision, recall, and F1 at the AUTO_MATCH tier and at AUTO + PROBABLE, for each matcher. Pairwise is computed on **final clusters** (pairs within the same predicted cluster versus the same true person), not just scored pairs, so transitive errors count.

### `eval_threshold_sweep`
Precision and recall for the FS matcher across thresholds from 0.50 to 0.999 (about 20 steps). Include the number of review-queue items each threshold would create. This is the table that justifies T_auto and T_review. Export it to CSV for a chart in Phase 4.

### `eval_clusters`
- **Split rate:** % of true people spread across more than one predicted cluster
- **Merge rate:** % of predicted clusters containing more than one true person
- **Sibling/twin false merges:** count of predicted clusters containing two true people from the same household. **Headline metric.**
- Predicted participant count versus true participant count (Phase 3 will lean on this)

### `eval_segments`
Pairwise recall and precision broken down by:
- `source_pair` (US-US, CA-CA, INTL-INTL, US-CA cross-border)
- Injected defect type behind the true pair (nickname, typo, accent stripped, day/month swap, email change, birth year off by one, name order swap, family name change), using the generator's defect metadata if available. If the generator didn't record which defects were applied to which record, add that as a generator amendment in step 0.
- Multi-league same-season kids: were their concurrent registrations correctly merged into one person?

### `eval_errors`
A listing of every false positive and false negative pair (or the top 200 of each), with a `likely_cause` category assigned by SQL rules: `SIBLING`, `TWIN`, `NAME_CHANGE`, `BLOCKING_MISS`, `BELOW_THRESHOLD`, `TRANSITIVE_CHAIN`, `OTHER`. This feeds the error-analysis section of the docs.

### Headline output
`make eval` prints a small table:

| Matcher | Stage | Precision | Recall | F1 | Sibling/twin merges | Predicted vs true participants |
|---|---|---|---|---|---|---|

---

## 11. Marts

### `dim_participant`
One row per resolved person.

| Column | Survivorship rule |
|---|---|
| `participant_id` | See ADR-004 |
| `first_name`, `last_name` | Most frequent display form. Ties go to the accented form, then the most recent. |
| `dob` | Mode of DAY-precision values. If none exist, NULL. |
| `birth_year` | From `dob` if present, else the mode of `birth_year` |
| `dob_precision` | `DAY` if `dob` is present, else `YEAR` |
| `sex` | Mode excluding U. If tied, U. |
| `home_country_code`, `home_region_code` | Most recent registration |
| `contact_email`, `contact_phone` | Most recent non-null |
| `is_minor_current` | From `birth_year` against the latest season cutoff |
| `consent_photo`, `consent_marketing` | Most recent **captured** (non-null) value, with `*_captured_at`. **Never derived from NULL. Never borrowed from another participant.** |
| `first_season`, `last_season`, `seasons_active` | |
| `registration_count`, `source_systems` (list) | |
| `resolution_confidence` | `DETERMINISTIC_ONLY`, `HIGH` (all edges AUTO), `REVIEWED` (any steward edge), `SINGLETON` |
| `has_open_integrity_issue` | boolean |

### `bridge_registration_participant`
**Every** registration in `int_registrations_unioned`, including collapsed duplicates, maps to exactly one `participant_id`, with `link_method` and `match_probability` (if applicable). This is the table Phase 3 counts from.

### `participant_identifiers`
Cross-reference of `participant_id` → source system → source person ID (CA member UUIDs, INTL player IDs) → contact emails seen. One row per identifier.

---

## 12. Participant ID stability (ADR-004)

Use `participant_id = hash(min source_record_id in cluster)` with a fixed prefix (`P-`). Document:
- It's deterministic across reruns on the same data.
- It **changes** when clusters merge or split, and the ADR explains why (a new link can change the minimum record).
- Production would need a persisted ID registry with merge/split history. Describe that design in the ADR, but don't build it. One paragraph plus a table sketch is enough. It shows you know where the simple approach breaks.

---

## 13. Tests

Generic:
- `bridge_registration_participant.registration_key`: `unique`, `not_null`, and row count equal to `int_registrations_unioned`
- `dim_participant.participant_id`: `unique`, `not_null`
- `accepted_values` on tiers, link methods, and resolution confidence

Singular:
- Every `idr_candidate_pairs` row has `record_a < record_b`, and there are no self-pairs
- No participant has consent TRUE/FALSE when all of its registrations have NULL for that consent
- No cluster exceeds the plausible maximum size
- The twin guard holds: no AUTO_MATCH edge exists between two records with SAME_ORG_SAME_SEASON and different first names
- Rerunning `make idr` produces identical `participant_id` sets. Implement this as a script comparing two runs.
- `check_eval_isolation.py` passes

Pytest:
- The generator produces twins and name-change cases (step 0)
- `simulate_steward.py` only writes to `review_decisions.csv`

---

## 14. Docs

### `docs/identity_resolution.md` (business-facing, about 2 pages)
Written for a program lead, not an engineer:
- What problem this solves, illustrated with the twins example
- How matching works in plain language (blocking → comparing → scoring → reviewing)
- Results table from `make eval`
- Why the project chose precision over recall, framed as **consent protection** and **trustworthy counts**
- What a steward does and how decisions flow back
- Known limitations: name changes, families with shared contact details and the same birthday, and the absence of real-world validation

### ADR-003 Identity resolution
Blocking design and measured completeness, both matchers, m/u approach and assumptions, λ, overrides, the threshold choice with the sweep table, DuckDB→Snowflake function mapping, and an error-analysis summary.

### Update `source_inventory.md`
Move all three sources to `Modelled`. Add a column "Person identifier quality" based on what the evaluation showed.

---

## 15. Build order for Claude Code

1. Pre-flight (section 0), including the generator amendments, and re-run Phase 1
2. Ground-truth loader + `eval` source + isolation script (build the guardrail **before** anything that could leak)
3. Seeds: `nickname_map`, `match_m_probabilities` (with rationale), `match_thresholds`, empty `review_decisions`
4. Macros + their singular tests
5. `idr_input_records`, `idr_deterministic_links`
6. `idr_candidate_pairs` → then immediately `eval_truth_pairs` + `eval_blocking`. **Check pair completeness before building scoring.** Target ≥ 0.98; if it's lower, revise the blocks first.
7. `idr_pair_features`
8. Rules matcher → edges → clusters → `eval_pairwise` + `eval_clusters` for the baseline
9. `idr_u_probabilities` → FS matcher → threshold sweep → set thresholds → re-run evaluation
10. `idr_cluster_integrity`, `idr_review_queue`
11. Marts: bridge, dim, identifiers
12. `eval_segments`, `eval_errors`, headline output
13. Optional: `simulate_steward.py` + post-review evaluation
14. Docs and ADRs, README update

Stop after each step and confirm it runs and the tests pass. At steps 6, 8, and 9, print the metrics and **pause for Anna to review** before continuing.

---

## 16. Phase 2 definition of done

- [ ] Generator amendments are in place; Phase 1 still passes
- [ ] Ground truth is used only in `models/evaluation/`, enforced by the isolation check
- [ ] Blocking pair completeness is reported (target ≥ 0.98)
- [ ] Both matchers run; the evaluation compares them side by side
- [ ] Thresholds are chosen from the sweep, with the justification in ADR-003
- [ ] Sibling/twin false merges are reported as a headline metric, and the FS matcher beats the rules baseline on it
- [ ] Every registration maps to exactly one participant in the bridge table
- [ ] Consent survivorship never derives values from NULL or across participants (test)
- [ ] `participant_id` is stable across reruns (test)
- [ ] Review queue is populated, with priorities and weight breakdowns
- [ ] `identity_resolution.md`, ADR-003, and ADR-004 are written; the README is updated with headline metrics

**Metric targets** (aim for these, but report actuals honestly even if missed): FS AUTO_MATCH precision ≥ 0.99, FS recall (AUTO + PROBABLE) ≥ 0.95, sibling/twin false merges ≤ 0.1% of true multi-child households. Missing a target with a clear error analysis is better than hitting it by tuning against truth.

---

## 17. Out of scope for Phase 2

- Participation metrics and the methodology memo (Phase 3)
- Masked, consent-filtered, or role-based views (Phase 3)
- Persisted ID registry with merge/split history (described in ADR-004, not built)
- Retention cohorts and fan data (Phase 4)
- ML-based matchers or external entity resolution libraries (Splink, Zingg, etc.). Mention them in ADR-003 as the production path. The point here is showing you can do it in SQL.
