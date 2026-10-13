.PHONY: p5-score p5-feeds audience fan-value acquisition funnel fan-status all-phases phase4 site fan linkage retention measure eval-measure shares report publish phase3 test-phase3 test-phase4 contracts steward-demo steward-reset setup generate load load-eval build idr eval test test-phase2 all phase2 clean docs isolation id-stability

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
	$(DBT) seed --profiles-dir . --select p5_params p5_dq_rules p5_consent_wording_map
	$(DBT) run --profiles-dir . --select tag:phase5
	$(DBT) test --profiles-dir . --select tag:phase5
	$(PY) -m scripts.print_p5_scorecard

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

# Phases 3 and 4 are built together (see all-phases)
phase3: all-phases
phase4: all-phases

docs:
	$(PY) -m scripts.build_data_dictionary
	$(PY) -m scripts.build_metrics_doc
	$(PY) -m scripts.build_access_policy

clean:
	rm -rf data/raw/* data/ground_truth/* warehouse/* dbt/target dbt/logs dbt/dbt_packages
