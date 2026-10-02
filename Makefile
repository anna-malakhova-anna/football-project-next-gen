.PHONY: steward-demo steward-reset setup generate load load-eval build idr eval test test-phase2 all phase2 clean docs isolation id-stability

PY  := uv run python
DBT := cd dbt && uv run dbt
# Phase 1 builds and tests everything except the Phase 2 models (identity, marts, evaluation) and their tests.
P1  := --exclude tag:phase2

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

build: dbt/profiles.yml
	$(DBT) seed --profiles-dir .
	$(DBT) run --profiles-dir . $(P1)

# Phase 2: identity resolution, marts and evaluation (needs `make load-eval` first for the evaluation models)
idr: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select identity marts

eval: dbt/profiles.yml
	$(DBT) run --profiles-dir . --select evaluation
	$(PY) -m scripts.print_headline

test: dbt/profiles.yml
	uv run pytest
	$(DBT) test --profiles-dir . $(P1)
	$(DBT) parse --profiles-dir .
	$(PY) -m scripts.check_eval_isolation

test-phase2: dbt/profiles.yml
	$(DBT) test --profiles-dir .
	$(PY) -m scripts.check_eval_isolation

# Optional demo of the review loop. The steward is SIMULATED from ground truth; POST_REVIEW rows are not matcher performance.
steward-demo:
	$(PY) -m scripts.simulate_steward --n 20
	$(DBT) seed --profiles-dir . --select review_decisions
	$(DBT) run --profiles-dir . --select identity marts evaluation
	$(PY) -m scripts.print_headline

steward-reset:
	$(PY) -m scripts.simulate_steward --reset
	$(DBT) seed --profiles-dir . --select review_decisions
	$(DBT) run --profiles-dir . --select identity marts evaluation
	$(PY) -m scripts.print_headline

id-stability:
	$(PY) -m scripts.check_id_stability

all: generate load build test

# Everything: Phase 1, then ground truth load, identity resolution, evaluation, all tests, isolation, id stability
phase2: all load-eval idr eval test-phase2 id-stability

docs:
	$(PY) -m scripts.build_data_dictionary

clean:
	rm -rf data/raw/* data/ground_truth/* warehouse/* dbt/target dbt/logs dbt/dbt_packages
