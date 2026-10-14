# ADR-013: Phase 5 reconciliation (v1 built from the handover, v2 specified in phase-5-spec.md)

- **Status:** **Accepted 2026-10-13.** Anna answered the seven questions at the end with "use your defaults"; the defaults are recorded under *Decisions taken* below. Written 2026-10-13.
- **Synthetic data.** Every artifact named here is synthetic; assumptions about NFL, RCX, vendor or club systems are labelled as such in the files that make them.
- **Numbering (a deviation from the spec).** The spec calls this ADR-011, and its later ADRs ADR-012 to ADR-016. Those numbers are taken: ADR-011 is "Measuring fan acquisition at market level" and ADR-012 is "Phase 5 scope and design" (v1). I propose the spec's six ADRs become **ADR-013 to ADR-018** in the same order (013 reconciliation, 014 rules registry and scoring, 015 uncertainty decomposition, 016 club market mapping, 017 retention versus deletion, 018 minimization and the chosen standard), and that ADR-012 stays as the v1 record with a "superseded in part by ADR-013" note. Every reference in the spec to ADR-011..016 reads as ADR-013..018.

## Context
**Phase 5 v1** was built from `phase-5-handover.md` (steps 1 to 7, commits `bd684ae` to `360b40c`), before the spec author had seen Phases 1 to 4. It is complete and verified (`make all-phases` passes: 407 dbt tests, 180 pytest tests, the build checks, the retention job and the demo). **`phase-5-spec.md`** now asks for a larger Phase 5 that builds on Phases 1 to 4 conventions. Where the two diverge the spec says: *Phase 1 to 4 conventions win; do not build a second DQ engine; extra feeds must be contracted through the playbook; keep v1's consent model, data standard and retention job if they work, moved into the new structure.*

**Pre-flight status:** step 1 (`make all-phases` passes) is done. Step 3 (publish the current scorecard for every year) is **deliberately not done yet**: published snapshots are immutable committed files (ADR-007), each year takes about five minutes, and the reconciliation below may change what should be published first. It needs a go-ahead.

## The reconciliation

Decisions: `KEEP`, `MERGE INTO <model>`, `RENAME`, `RETIRE`. "Replace" means the spec asks for a different method, so the v1 artifact is retired and its idea carried into the new model.

### Sources and generator

| v1 artifact | Relation to Phases 1 to 4 and the spec | Decision |
|---|---|---|
| `generator/phase5/feeds.py`: six feeds (`matrix_export`, `vendor_reg_a`, `vendor_reg_b`, `pop_warner_feed`, `pal_chapter_csv`, `school_program`) landing in `raw.p5_*` | The spec says US_LEAGUE is the analogue of the fragmented network, and says extra feeds like these need a contract and onboarding log. They have neither (`source_registry.csv` lists five sources; the six are not in it). They are derived from the same true US youth as US_LEAGUE, so putting them in the counting facts would double count. | **KEEP as extra sources, onboard through the playbook now** (six contracts, six onboarding logs, `source_registry` rows) to **`Contracted`, not `Modelled`**: they stay out of `int_registrations_unioned` and the counts until Anna decides (Question 2). |
| `raw.p5_revocations` (parent revocation requests) | Not a source in the spec; consent events there come from registrations. | **KEEP**, contracted as a consent-side input (with the onboarding of the six). |
| `raw.p5_league_catalog`, `raw.p5_league_alias_map` | Spec section 3.3 wants an org registry of known organizations, including those that send nothing. | **MERGE INTO `org_registry.csv`** (the catalog becomes the registry of known orgs, plus a reporting-this-season flag); the alias map stays as the free-text name resolver. |
| ADR-012 decision 1, "isolated scope: no Phase 1 to 4 number changes" | Spec section 3 amends the generator for US_LEAGUE, CA and INTL and expects a full rebuild and a restatement (`NEW_SOURCE_DATA`). | **RETIRE** that constraint. v1 feeds are drawn from the registry with their own random stream, so they follow the rebuild. |
| Revocation, retention and consent-wording generator config under `phase5.*` | The spec adds org profiles, MNAR, unreporting orgs, consent variants, a fix-list scenario to the same config file. | **KEEP**, reorganised: one `phase5` config block, new keys added beside the old. |

### Staging, identity, evaluation

| v1 artifact | Relation | Decision |
|---|---|---|
| `stg_p5_registrations` (one model for six feeds) | Phase 1 convention is one `stg_<source>_registrations` per source. | **RENAME / split** into six `stg_*` models when the sources are contracted. |
| `p5_idr_input_records`, `p5_blocking_keys`, `p5_candidate_pairs`, `p5_pair_scores`, `p5_clusters`, `p5_clusters_probable` | A parallel copy of the Phase 2 pipeline, reusing its macros. The spec wants the Phase 2 models themselves to accept coarsened inputs through a `minimization_variant` var, no code forks. | **MERGE INTO `idr_input_records`** (macro-level treatment) for the minimization runs. The separate Phase 5 chain is **KEPT only while the six feeds are not in the counting facts**, then retired if they never join. |
| `idr_rules_rule_id` macro (R1 to R6, extracted from `idr_pair_scores_rules`) | Already shared; output verified unchanged. | **KEEP**. R7 (feeds with no DOB) **KEEP**, documented as a Phase 5 extension. |
| `eval_p5_resolution`, `eval_p5_households_and_consent`, `eval_p5_market_estimate` | Evaluation models in `models/evaluation/`, isolation-checked. | **KEEP the first two (RENAME to `eval_*` without `p5`)**; the third is **RETIRED** with the heuristic band (below) and replaced by `eval_uncertainty_decomposition`. |
| `p5_*` ground-truth tables (`eval.p5_registration_truth`, `eval.p5_defect_manifest`) | Spec section 3: write all new truth to `data/ground_truth/`. | **KEEP**. |

### Data quality engine

| v1 artifact | Relation | Decision |
|---|---|---|
| `p5_dq_rules` seed (21 rules, thresholds for two purposes) | The spec's single registry `dq_rule_registry` has seven dimensions, five purposes (`COUNT`, `SEGMENT`, `GEO`, `RETAIN`, `ACTIVATE`), severity, owner, origin. | **MERGE INTO `dq_rule_registry`** (v1 "participation reporting" maps to `COUNT` + `SEGMENT` + `GEO`, "club activation" to `ACTIVATE`; each rule is re-assigned deliberately, not mechanically). **RETIRE** `p5_dq_rules`. |
| Phase 1 flags (`dq_flag_severity`, `dq_defect_log`) and contract `quality:` rules | Spec: migrate into the registry with `origin = PHASE1 / CONTRACT`; do not duplicate. v1 did not touch them. | **New work** in spec step 3 (v1 never built a second engine for them; it built one beside them). |
| `p5_record_quality` | Spec's `dq_record_fitness` (a `fit_for_<purpose>` boolean and a failing-rules list per record). | **RENAME + MERGE INTO `dq_record_fitness`**. |
| `dq_rule_results_league`, `dq_rule_results_market` | Spec's long fact `dq_rule_results` (rule x grain key x run). | **MERGE INTO `dq_rule_results`**. |
| `dq_score_league`, `dq_score_market` (mean of dimension scores, overall score) | Spec: purpose score is the **minimum** of dimension scores, small orgs get a Wilson interval and are graded on its lower bound. | **RENAME to `dq_scorecard_org` / `dq_scorecard_market` and CHANGE the method.** v1 grades will move; ADR-014 explains why the minimum replaces the mean. |
| (none) | Spec wants `dq_scorecard_source`, `dq_trend` (SPC), impact-ranked fix list. | **New work.** |
| `dq_fix_list` (top three by shortfall x failures) | Spec: ranked by impact in participants and households (`mart_dq_impact`). | **KEEP name, CHANGE ranking.** Fix text moves into the registry's `fix_guidance`. |
| `p5_params` (grade bands, lateness, ages, thresholds) | Spec: grade bands live in a seed; purposes seed. | **MERGE**: bands into a `dq_grade_bands` seed; the rest stay as config-exported parameters. |
| `p5_data_standard` seed, `p5_standardized_records`, `p5_standard_conformance`, `p5_standard_summary`, `p5_standard_check` macro | Spec: `data_standard_fields.csv` and a `validate_against_standard` macro whose results land in `dq_rule_results` with `origin = STANDARD`. | **RENAME + MERGE**; add the PII-class and evidence columns. `docs/data-standard.md` is **KEPT** and gains the evidence link to the minimization frontier. |

### Consent, households, activation

| v1 artifact | Relation | Decision |
|---|---|---|
| `p5_consent_event` | Spec: `int_consent_event`: household/contact x source x text version x purposes x captured_at x method. Phase 4 already has `stg_fan_consent_events` and `fct_fan_consent_history` (channel-level fan consent) and `mart_consent_capture`. | **RENAME to `int_consent_event`** and **extend** to registration consent of US_LEAGUE, CA and INTL (v1 covers only its six feeds). The fan channel consent stays Phase 4's and is not merged: different grain and purpose. |
| `p5_consent_purposes` (5 purposes: `LEAGUE_OPERATIONS`, `LEAGUE_COMMUNICATIONS`, `NFL_CLUB_MARKETING`, `THIRD_PARTY_DISCLOSURE`, `PROFILING`) | Spec's `consent_purposes.csv`: `LEAGUE_OPS`, `LEAGUE_COMMS`, `CLUB_MARKETING`, `PARTNER_DISCLOSURE`, `PROFILING`, `PHOTO_MEDIA`. | **RENAME the values and ADD `PHOTO_MEDIA`** (US_LEAGUE already has `photo_consent`). |
| `p5_consent_wording_map` | Same idea as consent text versions. | **KEEP**, feeds `consent_text_version`. |
| Numeric provenance score (0 to 3) | Spec: grade `KNOWN_FULL` / `KNOWN_PARTIAL` / `UNKNOWN`. | **RENAME** to the grade; the three questions (what, when, which wording) map to purpose, timestamp, text version. |
| `p5_household`, `p5_household_child`, `p5_record_person` | Phase 4 `linkage.int_household` already builds households from guardian contacts, with a shared-inbox guard (`household_max_members`). v1's version has no guard. | **MERGE INTO `linkage.int_household`** for the registration sources; v1's own household model is retired once the six feeds are decided (Question 2). The restricted-zone split is **KEPT**. |
| `p5_household_purpose_status`, `p5_household_activation`, `p5_consent_funnel`, `p5_purpose_limitation` | Spec: `mart_activation_funnel` per year and per club market, each step typed `loss_type` = `DQ` or `PRIVACY`. | **MERGE INTO `mart_activation_funnel`**: v1's stages map to the spec's, `loss_type` is added (v1 already separates the two in prose). The tests (child never joined; consent-email is not a marketing opt-in; blank is not FALSE) are **KEPT** and extended. |

### Club market lens and the estimate

| v1 artifact | Relation | Decision |
|---|---|---|
| `p5_club`, `p5_club_territory` (synthetic clubs over the 28 existing synthetic US markets) | Spec section 9.1: `club_market_map.csv`, ZIP3 to **32 club markets** plus `NO_CLUB_MARKET`, shared markets with weights summing to 1, labelled an approximation. The project has **28** US markets, not 32. | **REPLACE** with `club_market_map.csv` per the spec. **Question 3:** build the 32 as new "club markets" over ZIP3 (a project approximation), or keep the 28 existing markets. |
| `p5_youth_population_zip3` (a **synthetic stub** of Census youth population) | Spec section 9.2 and the Phase 3 rule: *never invent figures*; rates only if Anna populates `population_denominators.csv`; otherwise "denominator not loaded". The stub invents denominators. | **RETIRE**. Every participation *rate* in v1 (market estimate, club views, demo, README) goes, or shows "denominator not loaded". Optional `scripts/fetch_acs_youth_population.py` for Anna to run. |
| `p5_market_estimate` (placed + allocated children; completeness-driven rule-of-thumb band) | Spec: coverage component = known-but-unreporting orgs x participants-per-org (with an interval), shown **separately** from identity and DQ components, never summed. | **RETIRE the heuristic band** and the "9 of 20, then 20 of 20 after the fact" result with it; **KEEP the idea of allocating unplaced children** as an explicit `UNPLACED` handling in `mart_market_coverage`, pending Anna (Question 4). |
| `phase5_club.p5_club_market_view`, `p5_club_market_age_view`, `p5_market_age_cells`, `p5_club_view_policy` seed | Spec: schema `share_club`, explicit columns, `audience_column_policy.csv`, the share-policy check, `suppress_small_cells` with primary + secondary suppression. | **RENAME to `share_club`** and **MERGE the column policy into `audience_column_policy.csv`**; **RETIRE** `p5_club_view_policy` and the bespoke `p5_club_view_is_aggregate_only` test in favour of the existing `check_share_policy` plus its extensions. The suppression behaviour is **KEPT**. |

### Minimization, retention, docs, tooling

| v1 artifact | Relation | Decision |
|---|---|---|
| `scripts/p5_minimization.py`, `p5_standard_shape` var in `p5_idr_input_records` (two variants: full vs birth year + ZIP3) | Spec: five variants (`V0_FULL` to `V4_HASHED_CONTACT`) in `minimization_variants.csv`, a `minimization_variant` var on `idr_input_records`, risk metrics on k-anonymity, `eval_minimization_tradeoff`. | **REPLACE.** v1's result (about 4 points of recall for birth year + ZIP3, no precision loss) becomes the V2 point to be re-measured, not carried as a finding. |
| `retention/job.py`, `retention/sql/*`, `pii_store`, `retention_log`, `suppression_list` | Spec section 10: `ops_age_out_retention`, delete or anonymize in the **identity and linkage zones**, a test that Phase 4 retention marts rebuild after deletion within tolerance, `mart_retention_vs_deletion`. v1 deletes from a derived copy of the **Phase 5 feeds only**; Phase 4's retention marts (`retention.*`) and linkage zone are untouched. | **KEEP the job design and tests; EXTEND** to the identity/linkage-zone copies, add the rebuild-after-deletion test and the mart. v1's ADR-012 decision 14 (raw stays immutable) stands: the spec deletes in the zones, not in raw. Rename the entry point to `ops_age_out_retention`. |
| `docs/data-standard.md`, `docs/retention.md`, `docs/questions-for-stakeholders.md` | Spec lists the first and third as deliverables. | **KEEP**; add the spec's fifth question (territory definitions differ?) and the evidence links. |
| `docs/market-estimate.md`, `docs/phase5-demo.md` | The first describes retired methods; the second contains talking points, which the spec says **Anna writes**. | `market-estimate.md`: **RETIRE** after step 9, folded into ADR-015/016. `phase5-demo.md`: **RENAME** its content into `docs/demo_script.md` as a *skeleton* marked `<!-- DRAFT: Anna to write the talking points -->`. |
| `docs/decisions/ADR-012-phase-5-scope-and-design.md` | v1's design record. | **KEEP** as history, add "superseded in part by ADR-013". |
| `scripts/print_p5_scorecard.py`, `scripts/p5_demo.py` | The demo is one market end to end. | **KEEP** (the demo is a different artifact from the spec's 15-minute path; reconcile at step 15). |
| Makefile `p5-feeds`, `p5-score`, `p5-minimization`, `p5-retention`, `p5-demo` | Spec: `make dq`, `nuance`, `markets`, `minimize`, `phase5`, and `all-phases` updated. | **RENAME** to the spec names; keep `p5-*` as aliases for one release. |
| dbt tag `phase5`, schemas `phase5`, `phase5_restricted`, `phase5_club`, `pii_store` | Phase 1 to 4 schemas are named by layer (`staging`, `quality`, `linkage`, `share_*`). | **RENAME** schemas into the layer names as models move (`quality`, `linkage`, `share_club`); the tag stays. |
| `CLAUDE.md` "Phase 5 conventions" | Must match the final structure. | **UPDATE** at step 15. |

## What this means for the spec's build order
Spec steps 2 to 16 proceed after review. The reconciliation changes three of them: step 3 (registry) absorbs `p5_dq_rules`; step 8 (consent/funnel) absorbs v1's consent, household and funnel models and adds registration-source consent; step 9 (markets) **replaces** v1's territory and estimate and **removes** the synthetic denominator. Steps 10 and 11 extend v1's minimization experiment and retention job.

## Decisions taken (Anna: "use your defaults for all of them")
1. ADR numbering: **ADR-013 to ADR-018** for the spec's six ADRs.
2. The six v1 feeds: **onboarded to `Contracted`, kept out of the counting facts** (no double counting of the same children).
3. Club markets: **build the spec's 32 club markets plus `NO_CLUB_MARKET` over ZIP3**, an approximation labelled as such (ADR-016).
4. Unplaced children: **keep an explicit, labelled `UNPLACED` handling** in `mart_market_coverage` (allocation by league, then state, reported separately and never mixed silently into a market's figure).
5. Denominators: **the synthetic stub is retired**; rates show "denominator not loaded" until `population_denominators.csv` is populated.
6. Publishing: **publish the current scorecard for all five years before the generator amendments** (pre-flight step 3).
7. Scoring: **switch outright** to minimum-of-dimensions with Wilson intervals; the v1 grades are recorded in this ADR's history (commit `360b40c`), not carried in the new tables.

## The questions as asked
1. **ADR numbering:** accept ADR-013 to ADR-018 for the spec's six ADRs?
2. **The six v1 feeds:** onboard them to `Contracted` and keep them out of the counts (my recommendation: they are the same children as US_LEAGUE, so joining them would double count), or fold them into US_LEAGUE-style sources and counts (a larger change to Phase 2 and the published numbers), or retire them in favour of applying the new organization quality profiles to US_LEAGUE only?
3. **Club markets:** build the spec's 32 markets plus `NO_CLUB_MARKET` over ZIP3 as a new approximation, or keep the 28 existing synthetic US markets?
4. **Unplaced children** (no usable ZIP): keep v1's allocation by league and state as an explicit handling in `mart_market_coverage`, or show them only as a separate "unplaced" count?
5. **Population denominators:** confirm retiring v1's synthetic stub, so no rate is shown until you load `population_denominators.csv` (or run the ACS fetch script yourself).
6. **Publishing:** go-ahead to publish the current scorecard for all five years (about 25 minutes, immutable files committed) before the generator amendments, so the restatement log shows the change?
7. **Scoring change:** v1's grades will move when the mean becomes the minimum and Wilson intervals apply; fine, or keep the v1 grades visible beside the new ones for one release?

## Progress addendum, 2026-10-14

Built and verified (commits on `main`): the generator amendments with a rebuild (spec step 2; the restatement is `NEW_SOURCE_DATA`, 90 KPI rows, 56 requiring restatement, `docs/reports/restatement_demo.md` Example 5), the rule registry and scorecards (3 to 4), the data standard and validation macro (5), impact ranking and fix list (6), the uncertainty decomposition and missingness bias (7), consent provenance and the activation funnel (8, ADR-019), the club-market lens (9, ADR-016), the minimization frontier (10, ADR-018), retention versus deletion (11, ADR-017), `share_club` and `share_privacy` (12), the fix-list demo (13), the site pages (14) and the documentation (15).

Done from the reconciliation tables: the v1 market estimate, the club territory seeds and views, the v1 league/market scores and rule-result models, and `docs/market-estimate.md` are **retired**; `p5_demo.py` and `print_p5_scorecard.py` now read the v2 outputs; the demo talk track moved to `docs/demo_script.md` as a skeleton for Anna's talking points.

Still open, stated plainly:
- **`p5_dq_rules` and `p5_record_quality` are not retired.** They still evaluate the six channel feeds, and `dq_record_base` reads their record flags; moving those rules into `dq_rule_registry` is follow-up work. Until then there are two places a rule can live for those feeds.
- **The data standard's point on the minimization frontier is not chosen** (Anna decides; ADR-018).
- **No new scorecard snapshot is published** (ADR-007 keeps publishing a deliberate step); the restatement log shows the difference live.
- **The ACS fetch script is untested against the live API** (`scripts/fetch_acs_youth_population.py`); `population_denominators` stays empty until Anna loads it.
- **The CI `all-phases` target runs the reduced minimization set** (see step 16 below).
