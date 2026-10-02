"""The observation window is config-driven (config seasons.first_observed_year, read through the observation_window seed).
No model or macro may hardcode a year. dbt/tests fixtures are exempt: they invent their own values and do not depend on the
data window."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YEAR = re.compile(r"(?<![\w.-])(19|20)\d{2}(?![\w-])")


def _code(sql: str) -> str:
    return re.sub(r"--[^\n]*|/\*.*?\*/|\{#.*?#\}", " ", sql, flags=re.DOTALL)


def test_no_model_or_macro_hardcodes_a_year():
    offenders = []
    for base in ("models", "macros"):
        for p in sorted((ROOT / "dbt" / base).rglob("*.sql")):
            for n, line in enumerate(_code(p.read_text(encoding="utf-8")).split("\n"), start=1):
                if YEAR.search(line):
                    offenders.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()[:80]}")
    assert not offenders, "literal years in models/macros:\n" + "\n".join(offenders)


def test_the_checker_itself_catches_a_literal_year():
    assert YEAR.search(_code("select * from t where participation_year = 2023"))
    assert not YEAR.search(_code("select 1 -- 2023 is in a comment"))
