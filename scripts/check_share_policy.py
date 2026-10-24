"""Enforce the audience access policy on the share schemas.

Checks (any failure exits non-zero):
  COLUMN_NOT_ALLOWED     a column in a share table is not listed as allowed for that audience and model
  COLUMN_DENIED          a column is explicitly denied (allowed = N) for that audience, for the model or for '*'
  POLICY_COLUMN_MISSING  the policy allows a column the table does not have (the policy is stale)
  MODEL_NOT_IN_POLICY    a share table has no policy rows at all
  POLICY_MODEL_MISSING   the policy names a share model that does not exist
  SELECT_STAR            `select *` (or `alias.*`) in the compiled SQL or the source of a share model
  PII_TAG_MISSING        a share column has no meta.pii tag (direct | quasi | none)
  DIRECT_IN_EXEC_ANALYST a column tagged pii: direct is in share_exec or share_analyst
  LINKAGE_LEAK           a share model has a model of the restricted `linkage` schema anywhere upstream and is not an approved aggregate
                         (ADR-009): only aggregated, suppressed models in share_exec / share_analyst may reach an audience
  QUASI_IN_CLUB_PRIVACY  a column tagged pii: direct or quasi is in share_club or share_privacy (aggregates only: no identifying column of either kind)
  CLUB_LINEAGE           a share_club model reads, directly, anything but an approved aggregate mart (APPROVED_CLUB_MARTS)
  CLUB_COLUMN_UNTREATED  a share_club / share_privacy column is neither a dimension, a suppression flag, nor a catalogued metric (treatment VALUE is allowed only in share_privacy)
  METRIC_NOT_IN_CATALOG  a share_club / share_privacy column treated as a metric is not in dbt/seeds/metric_catalog.csv
  LINKAGE_IN_MARKETING   share_marketing or share_media depends on `linkage` at all. Nothing linked reaches them: the both-sides consent path
                         (consent_marketing TRUE on the registration AND the fan account) is not implemented
This compares what is ACTUALLY in the database (information_schema) with the policy, so it tests what is absent, not
only what is present.

  uv run python -m scripts.check_share_policy
"""
from __future__ import annotations

import csv
import json
import re
import sys

import duckdb
from scripts.common import DB, ROOT

POLICY = ROOT / "dbt" / "seeds" / "audience_column_policy.csv"
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
COMPILED = ROOT / "dbt" / "target" / "compiled" / "counting_flag_football" / "models" / "shares"
SOURCE = ROOT / "dbt" / "models" / "shares"
NO_DIRECT = {"share_exec", "share_analyst"}
NO_IDENTIFYING = {"share_club", "share_privacy"}                  # neither direct nor quasi identifiers
CATALOG = ROOT / "dbt" / "seeds" / "metric_catalog.csv"
# The only models a share_club model may read directly: aggregate marts built for it (spec section 11). Row-level or linkage models are never on this list.
APPROVED_CLUB_MARTS = {"mart_market_coverage", "mart_activation_funnel", "mart_missingness_bias", "dq_scorecard_market", "mart_activation_funnel_loss",
                       "dq_scorecard_source", "dq_trend", "mart_dq_impact", "dq_scorecard_org", "mart_uncertainty_decomposition"}      # Phase 5.1: source- and rule-level aggregates for headline numbers (no organization key is selected; dq_scorecard_org only feeds league counts by channel and size band)
# Aggregated, small-cell-suppressed share models that may be built from `linkage` models (ADR-009). Everything else may not.
APPROVED_LINKAGE_AGGREGATES = {
    "share_exec__fan_engagement_effect", "share_exec__household_link_rate", "share_exec__fan_funnel", "share_exec__acquisition_incrementality", "share_exec__fan_value",
    "share_exec__addressable_audience", "share_exec__market_quadrants", "share_exec__roadmap_gates",
    "share_club__market_year", "share_club__market_missingness", "share_club__activation_funnel", "share_club__chart_insights", "share_ops__league_scorecard", "share_ops__league_fix_list", "share_privacy__chart_insights", "share_privacy__conversion_funnel_by_tier", "share_privacy__consent_provenance", "share_privacy__minimization_frontier",
    "share_exec__fan_rfm", "share_exec__fan_survival", "share_exec__fan_value_uplift", "share_exec__consent_capture", "share_analyst__fan_event_study", "share_analyst__fan_acquisition_event_study", "share_analyst__fan_market_year",
}
NO_LINKAGE_AT_ALL = {"share_marketing", "share_media"}
STAR = re.compile(r"\bselect\s+(distinct\s+)?\*|\b\w+\.\*", re.IGNORECASE)


def strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.DOTALL)


def audience_of(schema: str) -> str:
    return schema.removeprefix("share_")


def check(policy: list[dict], columns: list[tuple], sql_files: dict[str, str], pii_tags: dict) -> list[tuple[str, str]]:
    """policy rows, (schema, table, column) tuples, {file: sql}, {(schema, table, column): pii tag or None}."""
    problems: list[tuple[str, str]] = []
    allowed, denied, policy_models = {}, {}, set()
    for r in policy:
        key = (r["audience"], r["model"])
        if r["allowed"] == "Y":
            allowed.setdefault(key, set()).add(r["column"])
            policy_models.add(key)
        else:
            denied.setdefault(key, set()).add(r["column"])
    actual: dict[tuple, set] = {}
    for schema, table, column in columns:
        aud = audience_of(schema)
        actual.setdefault((aud, table), set()).add(column)
        ok = allowed.get((aud, table), set())
        if column not in ok:
            problems.append(("COLUMN_NOT_ALLOWED", f"{schema}.{table}.{column}"))
        if column in denied.get((aud, table), set()) | denied.get((aud, "*"), set()):
            problems.append(("COLUMN_DENIED", f"{schema}.{table}.{column}"))
        tag = pii_tags.get((schema, table, column))
        if tag not in {"direct", "quasi", "none"}:
            problems.append(("PII_TAG_MISSING", f"{schema}.{table}.{column}"))
        if tag == "direct" and schema in NO_DIRECT:
            problems.append(("DIRECT_IN_EXEC_ANALYST", f"{schema}.{table}.{column}"))
        if tag in {"direct", "quasi"} and schema in NO_IDENTIFYING:
            problems.append(("QUASI_IN_CLUB_PRIVACY", f"{schema}.{table}.{column}"))
    for key, cols in allowed.items():
        if key not in actual:
            problems.append(("POLICY_MODEL_MISSING", f"{key[0]}.{key[1]}"))
        else:
            for c in sorted(cols - actual[key]):
                problems.append(("POLICY_COLUMN_MISSING", f"{key[0]}.{key[1]}.{c}"))
    for key in actual:
        if key not in policy_models:
            problems.append(("MODEL_NOT_IN_POLICY", f"{key[0]}.{key[1]}"))
    for name, sql in sql_files.items():
        if STAR.search(strip_comments(sql)):
            problems.append(("SELECT_STAR", name))
    return sorted(set(problems))


def check_club_and_metrics(policy: list[dict], catalog: set[str], manifest: dict | None) -> list[tuple[str, str]]:
    """share_club / share_privacy: every column is a dimension, a suppression flag or a catalogued metric; share_club reads only approved aggregate marts."""
    problems: list[tuple[str, str]] = []
    for r in policy:
        if r["audience"] not in {"club", "privacy"} or r["allowed"] != "Y":
            continue
        where = f"share_{r['audience']}.{r['model']}.{r['column']}"
        if r["treatment"].startswith(("AGGREGATE", "DERIVED")):
            if r["column"] not in catalog:
                problems.append(("METRIC_NOT_IN_CATALOG", where))
        elif r["treatment"] == "VALUE":
            if r["audience"] == "club":
                problems.append(("CLUB_COLUMN_UNTREATED", where))
        elif r["treatment"] not in {"DIMENSION", "SUPPRESSION_FLAG"}:
            problems.append(("CLUB_COLUMN_UNTREATED", where))
    if manifest:
        nodes = manifest["nodes"]
        for node in nodes.values():
            if node["resource_type"] == "model" and node["schema"] == "share_club":
                for parent in node["depends_on"]["nodes"]:
                    pn = nodes.get(parent) or manifest.get("sources", {}).get(parent)
                    name = pn["name"] if pn else parent
                    if pn and pn.get("resource_type") == "seed":
                        continue                                   # configuration (privacy_params), not data
                    if name not in APPROVED_CLUB_MARTS:
                        problems.append(("CLUB_LINEAGE", f"{node['name']} <- {name}"))
    return problems


def check_linkage(manifest: dict) -> list[tuple[str, str]]:
    """Share models whose lineage touches the restricted `linkage` schema, other than the approved aggregates."""
    nodes = {**manifest["nodes"], **manifest.get("sources", {})}

    def upstream(node_id: str, seen: set) -> set:
        for parent in nodes.get(node_id, {}).get("depends_on", {}).get("nodes", []):
            if parent not in seen:
                seen.add(parent)
                upstream(parent, seen)
        return seen

    problems = []
    for node_id, node in manifest["nodes"].items():
        if node["resource_type"] != "model" or not node["original_file_path"].startswith("models/shares/"):
            continue
        touches = sorted(nodes[u]["name"] for u in upstream(node_id, set()) if u in nodes and nodes[u].get("schema") == "linkage")
        if not touches:
            continue
        if node["schema"] in NO_LINKAGE_AT_ALL:
            problems.append(("LINKAGE_IN_MARKETING", f"{node['schema']}.{node['name']} <- {touches[0]}"))
        elif node["name"] not in APPROVED_LINKAGE_AGGREGATES:
            problems.append(("LINKAGE_LEAK", f"{node['schema']}.{node['name']} <- {touches[0]}"))
    return problems


def load() -> tuple[list[dict], list[tuple], dict[str, str], dict]:
    with open(POLICY, newline="", encoding="utf-8") as f:
        policy = list(csv.DictReader(f))
    con = duckdb.connect(str(DB), read_only=True)
    try:
        columns = con.execute("select table_schema, table_name, column_name from information_schema.columns "
                              "where table_schema like 'share\\_%' escape '\\' order by 1, 2, ordinal_position").fetchall()
    finally:
        con.close()
    sql_files = {}
    for base in (COMPILED, SOURCE):
        if base.exists():
            for p in sorted(base.rglob("*.sql")):
                if any(part.endswith(".yml") for part in p.parts):    # dbt's compiled generic-test queries, not share models
                    continue
                sql_files[f"{base.name}/{p.relative_to(base).as_posix()}" + (" (compiled)" if base is COMPILED else " (source)")] = p.read_text(encoding="utf-8")
    pii_tags: dict = {}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
        for node in manifest["nodes"].values():
            if node["resource_type"] == "model" and node["original_file_path"].startswith("models/shares/"):
                for col, meta in node["columns"].items():
                    pii_tags[(node["schema"], node["name"], col)] = (meta.get("meta") or {}).get("pii")
    return policy, columns, sql_files, pii_tags


KINDS = ["COLUMN_NOT_ALLOWED", "COLUMN_DENIED", "POLICY_COLUMN_MISSING", "MODEL_NOT_IN_POLICY", "POLICY_MODEL_MISSING", "SELECT_STAR", "PII_TAG_MISSING", "DIRECT_IN_EXEC_ANALYST",
         "QUASI_IN_CLUB_PRIVACY", "CLUB_LINEAGE", "CLUB_COLUMN_UNTREATED", "METRIC_NOT_IN_CATALOG", "LINKAGE_LEAK", "LINKAGE_IN_MARKETING"]


def record_results(problems: list[tuple[str, str]], n_columns: int, n_tables: int) -> None:
    """Write the number of violations per check kind (counts only) for share_privacy__policy_checks. Best effort: a read-only or locked warehouse must not fail the check itself."""
    try:
        con = duckdb.connect(str(DB))
    except duckdb.Error:
        return
    try:
        con.execute("create schema if not exists audit_share_policy")
        con.execute("create or replace table audit_share_policy.policy_check_results (check_name varchar, violations integer, columns_checked integer, share_tables_checked integer)")
        counts = {k: 0 for k in KINDS}
        for kind, _ in problems:
            counts[kind] = counts.get(kind, 0) + 1
        con.executemany("insert into audit_share_policy.policy_check_results values (?, ?, ?, ?)", [(k, v, n_columns, n_tables) for k, v in sorted(counts.items())])
    finally:
        con.close()


def main() -> int:
    policy, columns, sql_files, pii_tags = load()
    if not columns:
        print("no share_* schemas found: run `make shares` first", file=sys.stderr)
        return 2
    problems = check(policy, columns, sql_files, pii_tags)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else None
    if manifest:
        problems = sorted(set(problems + check_linkage(manifest)))
    with open(CATALOG, newline="", encoding="utf-8") as f:
        catalog = {r["metric_id"] for r in csv.DictReader(f)}
    problems = sorted(set(problems + check_club_and_metrics(policy, catalog, manifest)))
    tables = {(s, t) for s, t, _ in columns}
    record_results(problems, len(columns), len(tables))
    if problems:
        print(f"SHARE POLICY VIOLATIONS ({len(problems)}):", file=sys.stderr)
        for kind, detail in problems:
            print(f"  {kind:24s} {detail}", file=sys.stderr)
        return 1
    print(f"share policy OK: {len(columns)} columns in {len(tables)} share tables across "
          f"{len({s for s, _ in tables})} audiences, all listed, none denied, no select *, every column tagged, "
          f"no direct identifier in exec or analyst, nothing from the restricted linkage schema except approved aggregates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
