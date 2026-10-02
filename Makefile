.PHONY: linkage retention measure eval-measure shares report publish phase3 test-phase3 test-phase4 contracts steward-demo steward-reset setup generate load load-eval build idr eval test test-phase2 all phase2 clean docs isolation id-stability

PY  := uv run python
DBT := cd dbt && uv run dbt
# Phase 1 builds and tests everything except the Phase 2 and Phase 3 models and their tests (dbt tags).
P1  := --exclude tag:phase2 tag:phase3 tag:phase4
P2  := --exclude tag:phase3 tag:phase4
P3  := --exclude tag:phase4

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

# Phase 3: phase 2, then facts + marts, shares + policy check, every test, the executive report
phase3: phase2 measure eval-measure shares test-phase3 report

docs:
	$(PY) -m scripts.build_data_dictionary
	$(PY) -m scripts.build_metrics_doc
	$(PY) -m scripts.build_access_policy

clean:
	rm -rf data/raw/* data/ground_truth/* warehouse/* dbt/target dbt/logs dbt/dbt_packages
