# Counting Flag Football — Phase 3 Spec: Measurement & Privacy

**Phase 3 goal:** Turn resolved participants into numbers an executive can trust and data that each audience is allowed to see. Specifically:
1. A defined, versioned methodology for counting participants
2. Participation marts that implement it in SQL
3. Honest uncertainty: what identity resolution and source coverage do to the count
4. Audience-specific data shares with privacy controls (minors, consent, small cells) enforced by tests
5. A KPI scorecard and a publish/restatement process

**Builds on:** Phase 2 (`bridge_registration_participant`, `dim_participant`, `idr_match_edges`, `idr_review_queue`, `idr_cluster_integrity`, evaluation models).

**The question this phase answers:** "How many people play flag football in our program, and how sure are we?" This is the global participation methodology the role describes.

---

## 0. Pre-flight

1. Run `make phase2` and confirm all Phase 2 tests and the eval-isolation check pass.
2. Read the actual Phase 2 model and column names. **Use what Phase 2 built.** Note any differences from this spec in `ADR-005`.
3. Print the Phase 2 headline evaluation table and save it to `docs/phase2_results.md` (it gets referenced in the memo). **Pause for Anna to review** before continuing.
4. Confirm the clustering logic in `idr_clusters` can be called against an arbitrary edge set. If it's inline SQL, refactor it into a macro `connected_components(edges_relation)` with no change in output, and verify that `participant_id` sets are identical before and after the refactor. Section 5 needs this.

---

## 1. Principles

1. **Definitions before numbers.** Every metric in a mart or report must exist in the metric catalog with a definition, grain, and owner. A test enforces it.
2. **One counting engine.** All participant counts come from the same fact tables. No report computes its own logic.
3. **Additive vs non-additive is explicit.** Global unique participants are **not** the sum of country counts when people play in two countries. Both views exist, and each is labelled.
4. **Count with bounds.** Point estimates ship with an identity-resolution range, and the coverage limitation is always stated.
5. **Least privilege by default.** Each audience gets a schema containing only the columns and rows it needs. Tests verify what is *absent*, not just what is present.
6. **NULL consent is not consent.** Carried over from Phases 1–2, and now enforced at the point of use.
7. **Published numbers are versioned.** Once published, a number only changes through a logged restatement.

---

## 2. Repo additions

```
dbt/
├── seeds/
│   ├── metric_catalog.csv              # metric_id, name, definition, grain, additivity, owner, methodology_version
│   ├── reporting_periods.csv           # period_id, period_type, start_date, end_date, cutoff_date
│   ├── audience_column_policy.csv      # audience, model, column, allowed (Y/N), treatment
│   ├── privacy_params.csv              # k_min (small-cell threshold), minor_age, etc.
│   └── population_denominators.csv     # OPTIONAL, see section 4.5
├── models/
│   ├── facts/
│   │   ├── fct_registration.sql
│   │   ├── fct_participant_year.sql
│   │   ├── fct_participant_us_season.sql
│   │   └── _facts.yml
│   ├── measurement/
│   │   ├── mart_participation_global.sql
│   │   ├── mart_participation_by_country.sql
│   │   ├── mart_participation_segments.sql
│   │   ├── mart_identity_uncertainty.sql
│   │   ├── mart_kpi_scorecard.sql
│   │   ├── mart_restatement_log.sql
│   │   └── _measurement.yml
│   ├── shares/
│   │   ├── exec/        share_exec__*.sql
│   │   ├── analyst/     share_analyst__*.sql
│   │   ├── ops/         share_ops__*.sql
│   │   ├── marketing/   share_marketing__*.sql
│   │   └── media/       share_media__*.sql
│   └── evaluation/
│       └── eval_participation_accuracy.sql
├── macros/
│   ├── connected_components.sql
│   ├── suppress_small_cells.sql
│   └── pseudonymize.sql
published/                              # versioned scorecard snapshots (committed)
scripts/
├── publish.py                          # snapshot scorecard -> published/
├── check_share_policy.py               # information_schema vs audience_column_policy
└── render_report.py                    # formats the exec report from marts (no calculations)
docs/
├── methodology/
│   ├── counting-a-participant.md       # THE MEMO (see section 9)
│   └── CHANGELOG.md
├── metrics.md                          # generated from metric_catalog.csv
├── access_policy.md                    # audience × data matrix, rationale
├── reports/
│   └── participation_report_<year>.md  # rendered output
└── decisions/
    ├── ADR-005-counting-rules.md
    ├── ADR-006-privacy-controls.md
    └── ADR-007-publish-and-restatement.md
```

Makefile additions:
```
make measure     # dbt run --select facts measurement
make shares      # dbt run --select shares + policy check
make report      # render exec report from current marts
make publish YEAR=2025   # snapshot scorecard; refuses if tests fail
make phase3      # phase2 + measure + shares + tests + report
```

---

## 3. Counting rules (methodology v1.0)

These rules are the content of the memo and of ADR-005. Implement them exactly. Where a rule involves judgment, the alternative is listed so the memo can explain the choice.

| # | Question | Rule (v1.0) | Alternative considered |
|---|---|---|---|
| C1 | What is a participant? | A resolved person (`participant_id`) with ≥1 valid registration in the period | Counting registrations (overstates multi-league players) |
| C2 | What is a valid registration? | Not an exact duplicate, not a junk row, and the registration date is within the period. Records with impossible DOBs **count** (the person is real; only the DOB is bad). | Excluding flagged records (undercounts) |
| C3 | Global reporting period | **Participation year** = calendar year. US spring + fall roll up into one year. | US-style seasons (not comparable with CA/INTL annual seasons) |
| C4 | US seasonal view | Separate spring and fall counts for US only, in `fct_participant_us_season`. Never blended with annual sources. | — |
| C5 | Person registered in two leagues in one year | Counted once in global counts and in each org's own count | — |
| C6 | Person registered in two countries in one year | Counted once globally. **Country-attributed view (additive):** assigned to the country of their most recent registration in the year. **Country-presence view (non-additive):** counted in each country they played in. | Attribution by first registration |
| C7 | Age | Age at December 31 of the participation year (ADR-002). For CA birth-year-only records, age = year − birth_year. | — |
| C8 | Person in two divisions in one year (playing up, or spring/fall crossing a boundary) | **Primary division** = the division with the most registrations in the year; ties go to the most recent. All divisions are retained in an array. | Oldest division |
| C9 | Sex | From `dim_participant`. `U` is reported as its own category and never imputed. | Proportional imputation |
| C10 | Youth vs adult | Youth = age ≤ 17 at cutoff | — |
| C11 | New participant | `participant_id`'s first valid registration year = this year. **2023 is excluded from new/returning metrics** because it's the first year of data (left-censored). | — |
| C12 | Returning participant | Valid registration this year **and** the prior year | "Ever played before" |
| C13 | Reactivated | Valid registration this year, none last year, at least one earlier | — |
| C14 | Records in clusters with open integrity issues | Counted, and the count of such participants is reported alongside | Excluded |
| C15 | What a count represents | **Registered participants in onboarded sources.** It is not total flag football participation. Informal play, non-partner leagues, and attendance are out of scope. | — |

**Registration ≠ play.** No attendance data exists. The memo must say plainly that a registered participant may not have played a game.

---

## 4. Fact tables and measurement marts

### 4.1 `fct_registration`
One row per registration (grain of `bridge_registration_participant`), joined to registration attributes: `participant_id`, `participation_year`, `us_season_term` (nullable), `organization_id`, `country_code`, `canonical_division`, `age_at_cutoff`, `is_valid_registration`, `invalid_reason`, `link_method`, `match_probability`.

### 4.2 `fct_participant_year`
One row per `participant_id` × `participation_year` with ≥1 valid registration.

| Column | Rule |
|---|---|
| `participant_id`, `participation_year` | |
| `valid_registration_count` | |
| `org_count`, `is_multi_org` | C5 |
| `countries_played` (array), `attributed_country_code` | C6 |
| `age_at_cutoff`, `age_band`, `is_youth` | C7, C10 |
| `primary_division`, `all_divisions` (array) | C8 |
| `sex` | C9 |
| `status` | `NEW` / `RETURNING` / `REACTIVATED` / `CENSORED` (2023) — C11–C13 |
| `has_open_integrity_issue` | C14 |
| `resolution_confidence` | From `dim_participant` |

### 4.3 `fct_participant_us_season`
Same idea, at the US season grain (C4). New/returning are defined against the same term in the prior year (spring vs spring).

### 4.4 Marts
- **`mart_participation_global`**: by year. Unique participants, registrations, registrations per participant, multi-org participants, and new / returning / reactivated counts.
- **`mart_participation_by_country`**: year × country, with **both** `participants_attributed` (additive) and `participants_present` (non-additive). Add a test: the sum of attributed counts = the global count. The sum of present counts is ≥ the global count, and the difference equals the number of multi-country participants (also a test).
- **`mart_participation_segments`**: year × country × age band × primary division × sex × youth flag. Use `GROUPING SETS` (or `CUBE`) so subtotals come from the same query, and add `grouping_id` columns so consumers can tell subtotal rows apart. Include girls' share of youth participation as a column at each level.

### 4.5 Optional: per-capita rates
`population_denominators.csv`, with required columns: `country_code`, `region_code`, `age_band`, `year`, `population`, `source_name`, `source_table_id`, `source_url`, `retrieved_date`.
- **Claude Code must not invent real-looking population figures.** If the seed is empty, skip rate columns and say so in the report.
- If Anna populates the seed from StatCan, US Census, or similar, rates are computed with a prominent label: *"Illustrative only — synthetic participant counts over real population denominators."*

---

## 5. Identity uncertainty

`mart_identity_uncertainty`: for each participation year (and each country under the attributed view), report three counts, all computed with the same `connected_components` macro:

| Bound | Edge set | Meaning |
|---|---|---|
| **Low** | Deterministic + AUTO_MATCH + **all PROBABLE pairs** + steward MATCH | If every uncertain pair is really one person |
| **Point** | Production edges (Phase 2 `idr_match_edges`) | The reported number |
| **High** | Production edges **minus any edge inside a cluster with an open integrity issue** | If every flagged cluster is really several people |

Also report:
- `review_queue_open_items` and the share of participants touched by them
- `pct_participants_high_confidence`
- `range_pct = (high − low) / point`

This is **label-free**: it uses no ground truth, so it would work in production. Then:

### `eval_participation_accuracy` (evaluation only)
For each year: true participant count (from ground truth) versus low / point / high, and whether truth falls inside the range. Also the true count of multi-country and multi-org participants versus the predicted counts. This is the only Phase 3 model allowed to use `ground_truth`, and the isolation check must still pass.

The memo reports both the bounds and, separately and clearly labelled, how they compared with the synthetic truth.

---

## 6. KPI scorecard

`mart_kpi_scorecard`: one row per year × KPI, in long format: `kpi_id`, `value`, `prior_year_value`, `yoy_change`, `low`, `high`, `methodology_version`, `computed_at`.

KPI tree (all must be in `metric_catalog.csv`):

```
North star: Unique global participants (year)
├── Growth
│   ├── New participants
│   ├── Returning participants   →  Year-over-year retention rate = returning / prior-year participants
│   └── Reactivated participants
├── Reach
│   ├── Youth girls' participants and girls' share of youth
│   ├── International participants (attributed, outside US)
│   └── Countries with ≥1 participant
├── Depth
│   └── Multi-org participants, registrations per participant
└── Data trust (reported alongside, not hidden)
    ├── Identity range % (from section 5)
    ├── % participants high-confidence
    ├── Open review items
    ├── Sources onboarded vs known (from source inventory)
    └── Registrations failing DQ rules (%)
```

The **data trust** KPIs go in the executive report beside the headline numbers, not in an appendix. That pairing is the governance point of the whole project.

---

## 7. Privacy controls and data shares

### 7.1 Audiences

| Audience | Purpose | Grain | Identifiers | Rows |
|---|---|---|---|---|
| **exec** | Program reporting | Aggregates only | None | All, with small-cell suppression |
| **analyst** | Analysis and modelling | Participant-year | Pseudonymous key only; no names or contact info; `birth_year` not DOB; postal prefix only | All |
| **ops** | Running leagues, resolving data issues | Registration + participant | Full identifiers | All, plus review queue |
| **marketing** | Outreach | Contact list | Contact email/name | **Only** adults with `consent_marketing = TRUE`, and guardians of minors where guardian marketing consent is TRUE. **No minor's own contact details, ever.** |
| **media** | Photo/video clearance | Roster | Name, org, season | Only `consent_photo = TRUE`. The list is "cleared"; anyone absent is **not** cleared, including NULL. |

These are **project policies informed by** regimes like COPPA, CASL, and GDPR, not legal interpretations. The access policy doc must say so.

### 7.2 Implementation in DuckDB
DuckDB has no per-user grants, so:
- Each audience gets its own schema (`share_exec`, `share_analyst`, `share_ops`, `share_marketing`, `share_media`) via dbt `+schema` config.
- Share models select **explicit columns** only. `select *` is banned in `models/shares/`; enforce it with a check in `check_share_policy.py` that greps the compiled SQL.
- `audience_column_policy.csv` lists every allowed column per share model. `check_share_policy.py` compares `information_schema.columns` against the policy and fails on **any column not explicitly allowed**.
- Tag PII columns in dbt YAML `meta` (`pii: direct | quasi | none`). The check also fails if any column tagged `direct` appears in `share_exec` or `share_analyst`.

### 7.3 Pseudonymization (`pseudonymize` macro)
`analyst_key = sha256(participant_id || salt)`, where the salt comes from an environment variable (`FLAG_PSEUDO_SALT`), is never committed, and has a documented dev default. ADR-006 must state:
- Pseudonymized data is still personal data. It's re-identifiable when combined with quasi-identifiers (birth year + postal prefix + org + sex in a small league).
- That's why analyst access still requires a purpose. Name the k-anonymity risk on quasi-identifiers, and give one query result showing the smallest equivalence class size in the analyst share.

### 7.4 Small-cell suppression (`suppress_small_cells` macro)
Applied to every `share_exec` aggregate:
- **Primary:** any count < `k_min` (default 10, from `privacy_params.csv`) becomes NULL with `suppressed = 'PRIMARY'`.
- **Secondary:** within any group where a subtotal is published, if exactly one cell is primary-suppressed, also suppress the next smallest cell in that group (`suppressed = 'SECONDARY'`), so the hidden value can't be recovered by subtraction.
- Derived rates (girls' share, etc.) are suppressed whenever their numerator or denominator is suppressed.
- ADR-006 acknowledges that this is a simplified approach. Production would use a proper statistical disclosure control method; name one, such as a tool like sdcMicro or tau-Argus.

### 7.5 Snowflake mapping (ADR-006)
A table mapping each control to its Snowflake equivalent: schemas/shares → roles + secure views or data shares; column policy → masking policies + tag-based masking; marketing/media row filters → row access policies; PII `meta` tags → object tagging; policy check → `ACCESS_HISTORY` / tag reference queries. This is design only, not implemented.

---

## 8. Publish and restatement

- `make publish YEAR=2025` runs all tests, then writes `published/scorecard_<year>_<timestamp>.parquet` with `methodology_version`, git commit SHA, and the row counts of the source raw tables. It refuses to publish if any test fails.
- `mart_restatement_log` compares the current scorecard with the latest published snapshot for each year, and lists KPIs whose value changed, along with old value, new value, delta, and a `likely_cause`:
  - `NEW_SOURCE_DATA` (raw row counts changed)
  - `IDENTITY_CHANGE` (participant links changed)
  - `METHODOLOGY_CHANGE` (version changed)
  - `UNKNOWN`
- ADR-007 defines the restatement policy: when a published number gets reissued (e.g. change > 1% or a methodology version bump), who approves it, and how the CHANGELOG records it.
- **Demonstrate it:** publish 2025, then apply one steward decision (or add a late registration file), rebuild, and show the restatement log catching the change. Save the output in `docs/reports/restatement_demo.md`.

---

## 9. The methodology memo (`docs/methodology/counting-a-participant.md`)

**Audience:** a program executive and a privacy lead. 3–4 pages. Plain language, no SQL.

**Claude Code's job:** produce a **draft skeleton** with every section heading, each counting rule from section 3, and every number pulled from the marts. **Anna writes the final prose.** Mark every prose paragraph `<!-- DRAFT: Anna to rewrite -->`.

Sections:
1. **What we count, and what we don't.** A registered participant in onboarded sources, not total participation. Registration ≠ play.
2. **Who counts as one person.** Identity resolution in two paragraphs, linking to `identity_resolution.md`.
3. **The counting rules.** C1–C15 in plain language, with one worked example: a girl who plays spring and fall in two Texas leagues, then moves to Ontario and plays there the next year. Show how she appears in each count.
4. **Global versus country numbers.** Why country totals don't add up to the global total in the presence view, and which view to use for what.
5. **How sure are we?** Bounds from section 5, and what they do and don't cover (identity only; not coverage, not data entry errors in the sources themselves).
6. **Privacy by design.** The audience model, small-cell suppression, the consent rules, and the minors rule.
7. **When numbers change.** Restatement policy.
8. **Known limitations and next steps.** Coverage, aggregate-only sources (coming in Phase 4: they'll be reported as a separate, non-deduplicated "reported headcount" line, never mixed into resolved participants), attendance, and real-world validation.
9. **Version and change control.** v1.0, with a link to the CHANGELOG.

---

## 10. Exec report (`make report`)

`render_report.py` reads **only** from `share_exec` and `mart_kpi_scorecard`, and formats `docs/reports/participation_report_<year>.md`. It performs no calculations. Contents: headline KPIs with year-over-year change and bounds, the data trust panel beside them, a country table (attributed view, suppressed), a youth girls' trend, and a methodology version footer with a link to the memo. Charts can wait until Phase 4.

---

## 11. Tests

Generic:
- `unique` / `not_null` on fact table grains (`participant_id` + `participation_year`, etc.)
- `accepted_values` on `status`, `age_band`, `suppressed`

Singular:
- Global unique participants = sum of `participants_attributed` across countries (per year)
- Sum of `participants_present` − global count = number of multi-country participants
- `mart_participation_global.unique_participants` = row count of `fct_participant_year` for that year
- low ≤ point ≤ high in `mart_identity_uncertainty`
- Every KPI in `mart_kpi_scorecard` and every metric column in `share_exec` exists in `metric_catalog.csv`
- No unsuppressed count < `k_min` in any `share_exec` model
- No group in `share_exec` has exactly one suppressed cell alongside a published subtotal
- `share_marketing`: no row where `consent_marketing` is not TRUE; no minor's own contact details
- `share_media`: no row where `consent_photo` is not TRUE
- `share_analyst`: no column tagged `pii: direct`; no full DOB column
- No 2023 participant has status NEW or RETURNING (censoring rule)
- `check_share_policy.py` and the Phase 2 `check_eval_isolation.py` both pass

---

## 12. Build order for Claude Code

1. Pre-flight (section 0), including the `connected_components` refactor with identical-output verification. **Pause for Anna.**
2. Seeds: `metric_catalog`, `reporting_periods`, `privacy_params`, `audience_column_policy` (start with exec and analyst)
3. `fct_registration` → `fct_participant_year` → `fct_participant_us_season`, with tests
4. `mart_participation_global`, `_by_country`, and their additivity tests
5. `mart_participation_segments` with `GROUPING SETS`
6. `mart_identity_uncertainty` → `eval_participation_accuracy`. **Print and pause for Anna:** do the bounds contain the truth?
7. `mart_kpi_scorecard`
8. Macros: `pseudonymize`, `suppress_small_cells`, each with edge-case tests
9. Share models, one audience at a time (exec → analyst → ops → marketing → media), then `check_share_policy.py`
10. Publish script → restatement log → the restatement demo
11. `render_report.py` → the first report
12. Docs: memo skeleton (draft markers), `metrics.md` generated from the catalog, `access_policy.md`, ADR-005/006/007, CHANGELOG, README update

Stop after each step and confirm it runs and tests pass.

---

## 13. Phase 3 definition of done

- [ ] Every counting rule C1–C15 is implemented and traceable to a model or column
- [ ] Additivity tests pass (attributed sums to global; presence difference = multi-country count)
- [ ] Identity bounds are computed label-free; the evaluation reports whether truth falls inside them
- [ ] KPI scorecard covers the full KPI tree, including data trust KPIs; every metric is in the catalog
- [ ] Five audience shares exist; the policy check fails on any unlisted column; consent and minor tests pass
- [ ] Small-cell suppression (primary + secondary) is enforced by tests
- [ ] Publish refuses on failing tests; the restatement demo shows a caught change with a cause
- [ ] Exec report renders from `share_exec` + scorecard only, with data trust beside the headline numbers
- [ ] Memo skeleton has every section, rule, and number; **Anna has written the prose**
- [ ] ADR-005/006/007, `access_policy.md`, `metrics.md`, and CHANGELOG are written; README is updated

---

## 14. Out of scope for Phase 3

- Retention cohort curves, survival analysis, and the participant → fan funnel (Phase 4)
- Fan engagement and school aggregate sources (Phase 4; the memo describes how aggregates will be handled)
- Charts, dashboards, or a UI (Phase 4)
- Real access control or a Snowflake deployment (mapped in ADR-006, not built)
- Formal statistical disclosure control beyond primary + secondary suppression
- Legal review of consent rules (stated as project policy)
