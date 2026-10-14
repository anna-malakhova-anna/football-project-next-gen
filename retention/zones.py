"""Phase 5 retention versus deletion in the identity and linkage zones (spec section 10). SYNTHETIC data; every period is an ASSUMPTION (see retention.job).

  uv run python -m retention.zones            # runs the experiment on a COPY of the warehouse; the warehouse itself is never deleted from

The v1 job (retention/job.py) works on the retention-managed store. This module applies the same age-out rule to the zones the identity resolution and the household linkage leave behind:
  identity.idr_input_records, intermediate.int_registrations_unioned, marts.dim_participant, marts.participant_identifiers, linkage.int_household.
A participant who was ever a minor in the data and has passed (Dec 31 of birth year + age_out_age) + grace_months is ANONYMIZED, irreversibly: names, name keys, date of birth, email, phone and the
exact postal code are removed (postal code kept to three characters); the child's rows in the identifier and household-link tables are deleted. The pseudonymous participant id, birth year, sex, country,
seasons and divisions stay: these are the coarsened facts the retention analytics are built from. Counts only are logged.
The experiment then answers: what survives? It rebuilds the Phase 4 retention marts (a) from the anonymized facts and (b) after re-running identity resolution on the anonymized inputs, and compares both with the
baseline (retention_audit.deletion_runs, read by mart_retention_vs_deletion). The warehouse is copied first because raw is immutable by convention and the dbt build recreates every zone from raw: a real deletion
would also have to reach raw, which is an open question (docs/questions-for-stakeholders.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import tempfile
from pathlib import Path

import duckdb

from retention.job import params_from_config

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"

FACTS_SELECT = ["fct_registration", "fct_participant_year", "retention_spells", "mart_retention_cohorts", "mart_retention_survival"]
IDENTITY_SELECT = ["path:models/identity", "dim_participant", "participant_identifiers", "bridge_registration_participant", *FACTS_SELECT]
IDENTITY_EXCLUDE = ["idr_input_records"]

# direct identifiers removed from a zone table's rows for an aged-out participant (postal code is cut to three characters, not removed)
ANONYMIZE = {
    "identity.idr_input_records": ("first_name", "last_name", "first_name_key", "last_name_key", "dob", "contact_email", "contact_phone"),
    "intermediate.int_registrations_unioned": ("first_name", "last_name", "first_name_key", "last_name_key", "dob", "contact_email", "contact_phone"),
    "marts.dim_participant": ("first_name", "last_name", "dob", "contact_email", "contact_phone"),
}
POSTAL_CUT = ("identity.idr_input_records", "intermediate.int_registrations_unioned")
DELETE_ROWS = {"marts.participant_identifiers": "participant_id", "linkage.int_household": "participant_id"}


def plan(con, p: dict) -> int:
    """Temp table _zone_due(participant_id): ever a minor in the data, and past age-out plus grace on the OLDEST plausible birth year among their records (a typo that makes a child look younger cannot extend retention)."""
    con.execute(f"""
        create or replace temp table _zone_due as
        select b.participant_id
        from marts.bridge_registration_participant b join identity.idr_input_records i on i.match_record_id = b.match_record_id
        where b.registration_key = b.match_record_id
        group by 1
        having bool_or(i.is_minor)
           and min(i.birth_year) filter (where i.birth_year >= 1900) is not null
           and cast(make_date(min(i.birth_year) filter (where i.birth_year >= 1900) + {int(p['age_out_age'])}, 12, 31) + to_months({int(p['grace_months'])}) as date) <= cast('{p['as_of']}' as date)""")
    return con.execute("select count(*) from _zone_due").fetchone()[0]


def apply(con, p: dict) -> dict[str, int]:
    """Anonymize / delete in the zones. Returns counts only."""
    dt.date.fromisoformat(p["as_of"])
    out = {"participants": plan(con, p)}
    keyed = {"identity.idr_input_records": ("match_record_id", "select match_record_id from marts.bridge_registration_participant where participant_id in (select participant_id from _zone_due)"),
             "intermediate.int_registrations_unioned": ("registration_key", "select registration_key from marts.bridge_registration_participant where participant_id in (select participant_id from _zone_due)"),
             "marts.dim_participant": ("participant_id", "select participant_id from _zone_due")}
    for table, cols in ANONYMIZE.items():
        key, subq = keyed[table]
        n = con.execute(f"select count(*) from {table} where {key} in ({subq})").fetchone()[0]
        sets = ", ".join(f"{c} = null" for c in cols)
        if table in POSTAL_CUT:
            sets += ", postal_code = left(postal_code, 3)"
        con.execute(f"update {table} set {sets} where {key} in ({subq})")
        out[table] = n
    for table, key in DELETE_ROWS.items():
        n = con.execute(f"select count(*) from {table} where {key} in (select participant_id from _zone_due)").fetchone()[0]
        con.execute(f"delete from {table} where {key} in (select participant_id from _zone_due)")
        out[table] = n
    return out


def survivors(con) -> dict[str, int]:
    """Independent check: rows of due participants that still carry a direct identifier. Every value must be 0."""
    q = {
        "identity.idr_input_records": "select count(*) from identity.idr_input_records where match_record_id in (select match_record_id from marts.bridge_registration_participant where participant_id in (select participant_id from _zone_due)) and (first_name is not null or last_name is not null or dob is not null or contact_email is not null or contact_phone is not null or length(postal_code) > 3)",
        "intermediate.int_registrations_unioned": "select count(*) from intermediate.int_registrations_unioned where registration_key in (select registration_key from marts.bridge_registration_participant where participant_id in (select participant_id from _zone_due)) and (first_name is not null or last_name is not null or dob is not null or contact_email is not null or contact_phone is not null or length(postal_code) > 3)",
        "marts.dim_participant": "select count(*) from marts.dim_participant where participant_id in (select participant_id from _zone_due) and (first_name is not null or last_name is not null or dob is not null or contact_email is not null or contact_phone is not null)",
        "marts.participant_identifiers": "select count(*) from marts.participant_identifiers where participant_id in (select participant_id from _zone_due)",
        "linkage.int_household": "select count(*) from linkage.int_household where participant_id in (select participant_id from _zone_due)",
    }
    return {t: con.execute(s).fetchone()[0] for t, s in q.items()}


METRICS = {
    "participants": "select count(distinct participant_id) from facts.fct_participant_year",
    "participant_years": "select count(*) from facts.fct_participant_year",
    "participants_with_two_or_more_seasons": "select count(*) from (select participant_id from facts.fct_participant_year group by 1 having count(*) >= 2)",
    "youth_then_adult_participants": "select count(*) from (select participant_id from facts.fct_participant_year group by 1 having bool_or(is_youth) and bool_or(age_at_cutoff >= 18))",
    "retention_entrants": "select count(*) from retention.retention_spells",
    "retention_at_step_1": "select survival from retention.mart_retention_survival where segment_type = 'ALL' and years_since_entry = 1",
    "retention_at_step_2": "select survival from retention.mart_retention_survival where segment_type = 'ALL' and years_since_entry = 2",
    "retention_at_step_3": "select survival from retention.mart_retention_survival where segment_type = 'ALL' and years_since_entry = 3",
}


def measure(con) -> dict[str, float]:
    return {m: float(con.execute(s).fetchone()[0]) for m, s in METRICS.items()}


def _dbt(profiles: Path, target: Path, select: list[str], exclude: list[str] | None = None) -> None:
    cmd = ["uv", "run", "dbt", "run", "--profiles-dir", str(profiles), "--target-path", str(target), "--select", *select]
    if exclude:
        cmd += ["--exclude", *exclude]
    subprocess.run(cmd, cwd=ROOT / "dbt", check=True, capture_output=True)


def experiment(src: Path = DB, identity_rebuild: bool = True, p: dict | None = None) -> dict:
    """Copy the warehouse, delete in the copy, rebuild, measure. Returns {'zone_counts', 'survivors', 'metrics': {scenario: {metric: value}}}. The source warehouse is only read."""
    p = p or params_from_config()
    tmp = Path(tempfile.mkdtemp(prefix="deletion_copy_"))
    try:
        copy = tmp / "flag_copy.duckdb"
        shutil.copy(src, copy)
        (tmp / "profiles.yml").write_text(f"counting_flag_football:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n      path: {copy}\n      threads: 4\n", encoding="utf-8")
        result: dict = {"metrics": {}}
        con = duckdb.connect(str(copy))
        try:
            result["metrics"]["BASELINE"] = measure(con)
            result["zone_counts"] = apply(con, p)
            result["survivors"] = survivors(con)
        finally:
            con.close()
        _dbt(tmp, tmp / "target", FACTS_SELECT)
        con = duckdb.connect(str(copy), read_only=True)
        try:
            result["metrics"]["FACTS_ONLY"] = measure(con)
        finally:
            con.close()
        if identity_rebuild:
            _dbt(tmp, tmp / "target", IDENTITY_SELECT, IDENTITY_EXCLUDE)
            con = duckdb.connect(str(copy), read_only=True)
            try:
                result["metrics"]["IDENTITY_REBUILT"] = measure(con)
            finally:
                con.close()
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def persist(result: dict, p: dict, db: Path = DB) -> None:
    """Write the scenario metrics and the zone counts (counts only) to retention_audit in the real warehouse."""
    con = duckdb.connect(str(db))
    try:
        con.execute("create schema if not exists retention_audit")
        con.execute("create or replace table retention_audit.deletion_runs (scenario varchar, metric varchar, value double)")
        con.executemany("insert into retention_audit.deletion_runs values (?, ?, ?)",
                        [(sc, m, v) for sc, ms in result["metrics"].items() for m, v in ms.items()])
        con.execute("create or replace table retention_audit.zone_deletion_log (as_of varchar, age_out_age integer, grace_months integer, zone_table varchar, rows_affected bigint, rows_still_identifying bigint)")
        con.executemany("insert into retention_audit.zone_deletion_log values (?, ?, ?, ?, ?, ?)",
                        [(p["as_of"], p["age_out_age"], p["grace_months"], t, n, result["survivors"].get(t, 0)) for t, n in result["zone_counts"].items() if t != "participants"]
                        + [(p["as_of"], p["age_out_age"], p["grace_months"], "(participants due)", result["zone_counts"]["participants"], 0)])
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts-only", action="store_true", help="skip the identity re-run")
    args = ap.parse_args()
    p = params_from_config()
    res = experiment(identity_rebuild=not args.facts_only, p=p)
    persist(res, p)
    print("zone counts:", res["zone_counts"])
    print("still identifying:", res["survivors"])
    for sc, ms in res["metrics"].items():
        print(sc, {k: round(v, 4) for k, v in ms.items()})
    return 1 if any(res["survivors"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
