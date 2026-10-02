.PHONY: setup generate load build test all clean docs

PY  := uv run python
DBT := cd dbt && uv run dbt

setup: dbt/profiles.yml
	uv sync

dbt/profiles.yml:
	cp dbt/profiles.yml.example dbt/profiles.yml

generate:
	$(PY) -m generator.main
	$(PY) -m generator.export_config_seed

load:
	$(PY) -m loader.load_raw

build: dbt/profiles.yml
	$(DBT) seed --profiles-dir .
	$(DBT) run --profiles-dir .

test: dbt/profiles.yml
	uv run pytest
	$(DBT) test --profiles-dir .

all: generate load build test

docs:
	$(PY) -m scripts.build_data_dictionary

clean:
	rm -rf data/raw/* data/ground_truth/* warehouse/* dbt/target dbt/logs dbt/dbt_packages
