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
This compares what is ACTUALLY in the database (information_schema) with the policy, so it tests what is absent, not
only what is present.

  uv run python -m scripts.check_share_policy
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
POLICY = ROOT / "dbt" / "seeds" / "audience_column_policy.csv"
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
COMPILED = ROOT / "dbt" / "target" / "compiled" / "counting_flag_football" / "models" / "shares"
SOURCE = ROOT / "dbt" / "models" / "shares"
NO_DIRECT = {"share_exec", "share_analyst"}
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


def main() -> int:
    policy, columns, sql_files, pii_tags = load()
    if not columns:
        print("no share_* schemas found: run `make shares` first", file=sys.stderr)
        return 2
    problems = check(policy, columns, sql_files, pii_tags)
    tables = {(s, t) for s, t, _ in columns}
    if problems:
        print(f"SHARE POLICY VIOLATIONS ({len(problems)}):", file=sys.stderr)
        for kind, detail in problems:
            print(f"  {kind:24s} {detail}", file=sys.stderr)
        return 1
    print(f"share policy OK: {len(columns)} columns in {len(tables)} share tables across "
          f"{len({s for s, _ in tables})} audiences, all listed, none denied, no select *, every column tagged, "
          f"no direct identifier in exec or analyst")
    return 0


if __name__ == "__main__":
    sys.exit(main())
