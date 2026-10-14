"""Load the quarantined ground truth into DuckDB schema `eval`. Separate from `make load` on purpose.

Only dbt models under dbt/models/evaluation/ may read these tables (scripts/check_eval_isolation.py enforces
it). The matcher never sees them. Tables:
  eval.person_registry      one row per true person (hidden true_person_id, household, twin group, ...)
  eval.registration_truth   every source record id -> true_person_id
  eval.defect_manifest      every injected defect by source record (for the per-defect-type evaluation)
  eval.school_truth         true program-year totals and the true overlap with registered participants (Source E)
  eval.school_overlap_truth the registered people who are also in a school or recreation program, by program-year
  eval.fan_truth            one row per household (participant or not): latent fandom, enrollment propensity, enrollment month, true uplift (Source D)
  eval.fan_account_truth    each fan account -> its true household, and which accounts have a different email or a shared phone
  eval.fan_market_truth     per market-year: launch year, new accounts, and how many the programme caused (the answer key for acquisition incrementality)
  eval.fan_consent_truth    each account's intended final consent status per channel (the answer key for the consent history)
  eval.fan_effect_truth     per participant account-month: expected events as observed and with no programme (the oracle behind the fandom estimate)
  eval.org_quality_truth    each organization's latent data-quality profile and form properties (the answer key for the scorecards)
  eval.unreported_participation_truth  participants whose organization sent no file that season: they exist here and in no source
  eval.churn_truth          the true per-season churn probability by age band (the answer key for the retention curves)
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from generator.population import load_config

TABLES = {
    "person_registry": "person_registry.parquet",
    "registration_truth": "registration_truth.parquet",
    "defect_manifest": "defect_manifest.parquet",
    "school_truth": "school_truth.parquet",
    "school_overlap_truth": "school_overlap_truth.parquet",
    "churn_truth": "churn_truth.parquet",
    "fan_truth": "fan_truth.parquet",
    "fan_account_truth": "fan_account_truth.parquet",
    "fan_market_truth": "fan_market_truth.parquet",
    "fan_consent_truth": "fan_consent_truth.parquet",
    "fan_effect_truth": "fan_effect_truth.parquet",
    "org_quality_truth": "org_quality_truth.parquet",
    "unreported_participation_truth": "unreported_participation_truth.parquet",
}


def load(truth_dir: str | None = None, db_path: str | None = None, cfg: dict | None = None) -> dict[str, int]:
    cfg = cfg or load_config()
    src = Path(truth_dir or cfg["paths"]["ground_truth_dir"])
    db = Path(db_path or cfg["paths"]["warehouse"])
    db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS eval")
        counts = {}
        for table, fname in TABLES.items():
            path = src / fname
            if not path.exists():
                raise FileNotFoundError(f"{path} not found; run `make generate` first")
            con.execute(f"CREATE OR REPLACE TABLE eval.{table} AS SELECT * FROM read_parquet('{path.as_posix()}')")
            counts[table] = con.execute(f"SELECT count(*) FROM eval.{table}").fetchone()[0]
    finally:
        con.close()
    return counts


if __name__ == "__main__":
    for table, n in load().items():
        print(f"eval.{table}: {n} rows")
