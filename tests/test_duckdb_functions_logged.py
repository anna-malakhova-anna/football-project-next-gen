"""CLAUDE.md: "Keep dbt portable (Snowflake later); log every DuckDB-specific function in docs/decisions/ADR-001-stack.md."

Every function called in dbt SQL must be either a standard function that runs unchanged on Snowflake (PORTABLE below) or named in ADR-001's
table with its Snowflake equivalent. When this fails, add a row to the ADR (construct, where, Snowflake equivalent); add a name to PORTABLE
only if it really behaves the same on Snowflake.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DBT = ROOT / "dbt"
ADR = ROOT / "docs" / "decisions" / "ADR-001-stack.md"

PORTABLE = set("""
abs any_value avg bool_and bool_or cast ceil ceiling coalesce concat concat_ws contains corr count count_if current_date current_timestamp date date_part
date_trunc day dense_rank exp extract first_value floor greatest grouping iff ifnull lag last_value lead least left length len ln log lower lpad
ltrim max md5 median min mod mode month nullif nvl percentile_cont percentile_disc position power rank replace right round row_number rpad rtrim
sign split_part sqrt stddev stddev_pop stddev_samp substr substring sum trim trunc try_cast upper var_pop var_samp variance year ntile
""".split())

SQL_WORDS = set("""
select from where and or not in as with join on group by order having union all case when then else end over partition window filter values
exists insert into create table view is null distinct using lateral by asc desc nulls first last limit qualify rows range between preceding
following current row interval
""".split())


def _strip(src: str) -> str:
    src = re.sub(r"\{#.*?#\}", " ", src, flags=re.S)              # jinja comments
    src = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", " ", src, flags=re.S)  # jinja expressions and tags
    src = re.sub(r"--[^\n]*", " ", src)                            # SQL comments
    src = re.sub(r"'(?:[^']|'')*'", "''", src)                      # string literals
    return src.lower()


def _local_names(files: list[Path]) -> set[str]:
    """CTE names, macro names and model names: called with a parenthesis but not SQL functions."""
    names = {f.stem.lower() for f in files}
    for f in files:
        text = f.read_text(encoding="utf-8").lower()
        names |= set(re.findall(r"\b([a-z_][a-z0-9_]*)\s+as\s*\(", text))            # CTEs
        names |= set(re.findall(r"\b([a-z_][a-z0-9_]*)\s*\([^()]*\)\s+as\s*\(", text))  # CTEs with a column list: cases(a, b) as (
        names |= set(re.findall(r"\bmacro\s+([a-z_][a-z0-9_]*)\s*\(", text))         # macros
        names |= set(re.findall(r"\)\s*(?:as\s+)?([a-z_][a-z0-9_]*)\s*\(", text))     # table aliases with column lists: ... ) t(a, b)
    return names


def test_every_duckdb_specific_function_is_logged_in_adr_001():
    files = [p for d in ("models", "macros", "tests") for p in (DBT / d).rglob("*.sql")]
    adr = ADR.read_text(encoding="utf-8").lower()
    local = _local_names(files)
    unlogged: dict[str, set[str]] = {}
    for f in files:
        for name in re.findall(r"\b([a-z_][a-z0-9_]*)[ \t]*\(", _strip(f.read_text(encoding="utf-8"))):
            if name in PORTABLE or name in SQL_WORDS or name in local:
                continue
            if re.search(rf"`[^`]*\b{re.escape(name)}\b[^`]*`", adr):
                continue
            unlogged.setdefault(name, set()).add(f.stem)
    assert not unlogged, "functions used in dbt SQL but not logged in ADR-001 (add a row with the Snowflake equivalent): " + "; ".join(
        f"{n} ({', '.join(sorted(fs)[:3])})" for n, fs in sorted(unlogged.items()))
