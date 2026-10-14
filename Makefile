.PHONY: markets consent nuance dq p5-demo p5-retention p5-minimization p5-score p5-feeds audience fan-value acquisition funnel fan-status all-phases phase4 site fan linkage retention measure eval-measure shares report publish phase3 test-phase3 test-phase4 contracts steward-demo steward-reset setup generate load load-eval build idr eval test test-phase2 all phase2 clean docs isolation id-stability

PY  := uv run python
DBT := cd dbt && uv run dbt
# Phase 1 builds and tests everything except the Phase 2 and Phase 3 models and their tests (dbt tags).
P1  := --exclude tag:phase2 tag:phase3 tag:phase4 tag:phase5
P2  := --exclude tag:phase3 tag:phase4 tag:phase5
P3  := --exclude tag:phase4 tag:phase5

setup: dbt/profiles.yml
	uv sync

dbt/profiles.yml:
	cp dbt/profiles.yml.example dbt/profiles.yml

generate:
	$(PY) -m generator.main
	$(PY) -m generator.export_config_seed

load:
	$(PY) -m loader.load_raw

# Ground truth goes to schema eval, never raw. Separate from `make load` on purpose.
load-eval:
	$(PY) -m loader.load_eval

isolation: dbt/profiles.yml
	$(DBT) parse --profiles-dir .
	$(PY) -m scripts.check_eval_isolation
	$(PY) -m scripts.check_lineage

build: dbt/profiles.yml
	$(DBT) seed --profiles-dir .
	$(DBT) run --profiles-dir . $(P1)

# Phase 2: identity resolution, marts and evaluation (needs `make load-eval` first for the evaluation models)
idr: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select identity marts

eval: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select evaluation --exclude tag:phase3
	$(PY) -m scripts.print_headline

test: dbt/profiles.yml
	uv run pytest
	$(PY) -m scripts.validate_contracts
	$(DBT) test --profiles-dir . $(P1)
	$(DBT) parse --profiles-dir .
	$(PY) -m scripts.check_eval_isolation
	$(PY) -m scripts.check_lineage

test-phase2: dbt/profiles.yml
	$(DBT) test --profiles-dir . $(P2)
	$(PY) -m scripts.check_eval_isolation
	$(PY) -m scripts.check_lineage

test-phase3: dbt/profiles.yml
	$(DBT) test --profiles-dir . $(P3)
	$(PY) -m scripts.check_eval_isolation
	$(PY) -m scripts.check_lineage
	$(PY) -m scripts.check_share_policy

# Optional demo of the review loop. The steward is SIMULATED from ground truth; POST_REVIEW rows are not matcher performance.
steward-demo:
	$(PY) -m scripts.simulate_steward --n 20
	$(DBT) seed --profiles-dir . --select review_decisions
	$(DBT) run --profiles-dir . --select identity marts evaluation facts measurement shares
	$(PY) -m scripts.print_headline

steward-reset:
	$(PY) -m scripts.simulate_steward --reset
	$(DBT) seed --profiles-dir . --select review_decisions
	$(DBT) run --profiles-dir . --select identity marts evaluation facts measurement shares
	$(PY) -m scripts.print_headline

id-stability:
	$(PY) -m scripts.check_id_stability

# Phase 5, step 1: six US registration feeds (own random stream; no Phase 1-4 file changes), their raw landing and quarantined truth
p5-feeds:
	$(PY) -m generator.phase5.feeds
	$(PY) -m generator.phase5.export_seed
	$(PY) -m loader.load_phase5

# Phase 5, step 2: staging, resolution, the rules-as-data scorecard, fix list and their tests (needs `make p5-feeds`, `make load-eval`, and the Phase 1 to 4 build for reference seeds)
p5-score: dbt/profiles.yml
	$(DBT) seed --profiles-dir . --full-refresh --select tag:phase5
	$(DBT) run --profiles-dir . --select tag:phase5
	$(DBT) test --profiles-dir . --select tag:phase5
	$(PY) -m scripts.print_p5_scorecard

# Phase 5, step 6: the age-out and revocation retention job on the retention-managed copy (schema pii_store). Rebuilds the copy from the dbt models, runs the job as of
# phase5.retention.as_of, logs counts only, and exits non-zero if anything over the threshold survives. Never touches raw, eval or the published snapshots.
p5-retention:
	$(PY) -m retention.job

# Phase 5 spec, steps 3 and 4: the rule registry, rule results, record fitness, the source and organization scorecards and the trend, with their tests, then the printed summary
dq: dbt/profiles.yml
	$(PY) -m scripts.build_rule_registry
	$(DBT) seed --profiles-dir . --full-refresh --select tag:phase5
	$(DBT) run --profiles-dir . --select dq_record_base dq_org_season_base dq_standardized_records dq_standard_conformance dq_standard_summary dq_rule_results dq_record_fitness dq_scorecard_org dq_scorecard_source dq_trend mart_dq_impact dq_fix_list eval_scorecard_vs_profile
	$(DBT) test --profiles-dir . --select dq_rule_registry dq_purposes dq_grade_bands dq_severity_weights consent_text_versions dq_registry_rules_are_defined_as_data dq_every_phase1_flag_has_exactly_one_registry_rule dq_rule_results_match_the_registry dq_record_fitness_follows_the_registry dq_scorecards_obey_the_scoring_rules dq_trend_limits_are_consistent dq_impact_and_fix_list_are_consistent dq_standard_and_standardized_records_agree dq_standard_conformance_is_complete_and_consistent data_standard_fields
	$(PY) -m scripts.print_dq

# Phase 5 spec, step 9: the club-market lens (ZIP3 -> club market allocation, market coverage, market scorecard, funnel and missingness by market) with its tests. Needs `make p5-feeds` seeds loaded.
markets: dbt/profiles.yml
	$(PY) -m generator.phase5.export_seed
	$(DBT) seed --profiles-dir . --full-refresh --select club_market_map population_denominators
	$(DBT) run --profiles-dir . --select int_participant_year_market int_dark_org_coverage dq_market_rule_results dq_scorecard_market mart_market_coverage mart_activation_funnel_loss mart_activation_funnel mart_missingness_bias
	$(DBT) test --profiles-dir . --select club_market_map population_denominators market_lens_is_consistent activation_outputs_never_touch_the_child dq_decomposition_and_missingness_are_consistent
	$(PY) -m scripts.print_markets

# Phase 5 spec, step 8: consent events (household-keyed), household-year consent status, record provenance grade and the activation funnel (DQ vs PRIVACY losses), with their tests
consent: dbt/profiles.yml
	$(DBT) seed --profiles-dir . --full-refresh --select consent_purposes p5_params
	$(DBT) run --profiles-dir . --select int_consent_event int_household_year_consent mart_activation_funnel mart_activation_funnel_loss dq_record_fitness
	$(DBT) test --profiles-dir . --select consent_purposes consent_purpose_limitation_holds activation_outputs_never_touch_the_child
	$(PY) -m scripts.print_consent

# Phase 5 spec, step 7: the uncertainty decomposition (identity, DQ exclusions, coverage; shown side by side) and the missingness bias (Manski bounds, tests), with their evaluations
nuance: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select mart_uncertainty_decomposition mart_missingness_tests mart_missingness_bias eval_uncertainty_decomposition eval_missingness_bias
	$(DBT) test --profiles-dir . --select macro_stats dq_decomposition_and_missingness_are_consistent
	$(PY) -m scripts.print_nuance

# Phase 5, step 7: the one-market demo, end to end (feeds, resolution, scorecard, consent funnel, estimate, standard, retention). Needs the Phase 1 to 4 build and `make load-eval` first.
p5-demo: p5-feeds p5-score p5-retention
	$(PY) -m scripts.p5_demo

# Phase 5, step 3: the cost of minimization (resolution with the full DOB and ZIP5 vs birth year and ZIP3 only); rebuilds the default at the end
p5-minimization:
	$(PY) -m scripts.p5_minimization

# Phase 5 spec 7: the minimization frontier. Runs the identity chain once per variant (about 30 seconds each), then the label-free risk and fitness and the evaluation.
# MIN_VARIANTS="V0_FULL V2_BIRTH_YEAR V4_HASHED_CONTACT" runs the reduced set (CI); the default is every variant of the seed.
minimize: dbt/profiles.yml
	$(DBT) seed --profiles-dir . --select minimization_variants
	$(PY) -m scripts.p5_minimization_runs $(if $(MIN_VARIANTS),--variants $(MIN_VARIANTS))
	$(DBT) run --profiles-dir . --select mart_reidentification_risk mart_minimization_fitness eval_minimization_tradeoff eval_minimization_checks
	$(DBT) test --profiles-dir . --select minimization_variants mart_reidentification_risk mart_minimization_fitness eval_minimization_tradeoff eval_minimization_checks
	$(PY) -m scripts.print_minimize

# Phase 4: validate every source's raw table against its data contract (writes quality.dq_contract_results)
contracts:
	$(PY) -m scripts.validate_contracts

test-phase4: dbt/profiles.yml
	$(PY) -m scripts.validate_contracts
	$(DBT) test --profiles-dir .
	$(PY) -m scripts.check_eval_isolation
	$(PY) -m scripts.check_lineage
	$(PY) -m scripts.check_share_policy

# Phase 4: household -> fan account linkage (restricted `linkage` schema) and its evaluation (needs `make load-eval`)
linkage: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select linkage eval_household_formation eval_household_linkage
	$(PY) -m scripts.print_linkage

# Phase 4: the static results site (reads share_exec and whitelisted evaluation summaries; fails if a chart computes a number in the browser)
site:
	$(PY) -m scripts.build_site

# Rework step 5: the fan status of participant households and its comparison with the truth (needs `make load-eval`)
fan-status: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select fct_household_fan_status eval_fan_status
	$(PY) -m scripts.print_fan_status

# Rework step 9: the addressable audience and the consent gap (needs `make load-eval`)
audience: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select int_fan_account_month_state int_household_audience_month mart_addressable_audience mart_consent_capture mart_opt_out_after_contact eval_consent_history
	$(PY) -m scripts.print_audience

# Rework step 8: value uplift, fan survival, lifetime value, activeness and RFM (needs `make load-eval`)
fan-value: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select int_fan_outcome_month mart_fan_value_uplift mart_fan_survival mart_fan_ltv mart_fan_activeness int_fan_rfm_scores mart_fan_rfm mart_fan_lapse_after_child_churn eval_fan_value_uplift eval_fan_lapse_after_child_churn
	$(PY) -m scripts.print_fan_value

# Rework step 7: acquisition incrementality at market level, naive vs incremental vs truth (needs `make load-eval`)
acquisition: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select int_market_year_accounts mart_acquisition_incrementality mart_acquisition_event_study mart_acquisition_summary eval_acquisition eval_acquisition_event_study
	$(PY) -m scripts.print_acquisition

# Rework step 6: the fan acquisition funnel (needs `make load-eval` only for the status comparison, not for the funnel itself)
funnel: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select int_household_funnel_base mart_fan_funnel
	$(PY) -m scripts.print_funnel

# Phase 4: fandom outcomes (naive vs matched difference-in-differences vs truth), built on the linkage (needs `make load-eval`)
fan: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select fct_household_engagement_month int_participant_household_timeline int_fan_cem_candidates int_fan_cem_matched mart_fan_naive mart_fan_did mart_fan_outcomes_summary eval_fan_effect eval_fan_matching_diagnostics
	$(PY) -m scripts.print_fan

# Phase 4: retention models and the printed comparison with the synthetic truth (needs `make load-eval`)
retention: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select retention eval_retention
	$(PY) -m scripts.print_retention

# Phase 3: counting facts and marts, audience shares (with the access-policy check)
measure: dbt/profiles.yml
	$(DBT) seed --profiles-dir .
	$(PY) -m loader.load_published
	$(DBT) run --profiles-dir . --select facts measurement

# Phase 3 evaluation: did the label-free identity bounds contain the synthetic truth? (needs `make load-eval`)
eval-measure: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select eval_participation_accuracy

shares: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select shares
	$(PY) -m scripts.check_share_policy

report:
	$(PY) -m scripts.render_report $(YEAR)

publish:
	@test -n "$(YEAR)" || (echo "usage: make publish YEAR=2025" && exit 2)
	$(PY) -m scripts.publish $(YEAR)
	$(PY) -m loader.load_published

all: generate load build test

# Everything: Phase 1, then ground truth load, identity resolution, evaluation, all tests, isolation, id stability
phase2: all load-eval idr eval test-phase2 id-stability

# Everything, from an empty checkout: generate, load (raw, ground truth, published snapshots), contract validation, every dbt model and test,
# pytest, and the build checks (eval isolation, aggregate lineage, share policy, ID stability). From Phase 4 the layers depend on each other in both
# directions (a Phase 3 scorecard reads a Phase 4 model), so Phases 3 and 4 are no longer built separately: this is the supported full build.
# `make site` then builds the results site; `make publish YEAR=...` is never part of it.
all-phases: dbt/profiles.yml
	$(PY) -m generator.main
	$(PY) -m generator.export_config_seed
	$(PY) -m loader.load_raw
	$(PY) -m loader.load_eval
	$(PY) -m loader.load_published
	$(PY) -m generator.phase5.feeds
	$(PY) -m generator.phase5.export_seed
	$(PY) -m loader.load_phase5
	$(PY) -m scripts.validate_contracts
	$(DBT) seed --profiles-dir .
	$(DBT) run --profiles-dir .
	$(DBT) test --profiles-dir .
	uv run pytest -q -n 4
	$(PY) -m scripts.check_eval_isolation
	$(PY) -m scripts.check_lineage
	$(PY) -m scripts.check_share_policy
	$(PY) -m scripts.check_id_stability
	$(PY) -m retention.job
	$(PY) -m scripts.p5_demo > /dev/null

# Phases 3 and 4 are built together (see all-phases)
phase3: all-phases
phase4: all-phases

docs:
	$(PY) -m scripts.build_data_dictionary
	$(PY) -m scripts.build_metrics_doc
	$(PY) -m scripts.build_access_policy

clean:
	rm -rf data/raw/* data/ground_truth/* warehouse/* dbt/target dbt/logs dbt/dbt_packages
