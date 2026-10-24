"""The `make` printouts read the data window from the warehouse, as the models do (see test_no_literal_years.py).
A literal year in a print script goes stale when the generator's window moves; the one in print_funnel.py once did (cohort 2024, after the window reached 2025)."""
import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YEAR = re.compile(r"(?<![\w.-])(19|20)\d{2}(?![\w-])")


def _literal_years(source: str) -> list[str]:
    """Years in code and strings; comments are ignored."""
    found = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in (tokenize.STRING, tokenize.NUMBER, tokenize.NAME) and YEAR.search(tok.string):
            found.append(f"line {tok.start[0]}: {tok.string.strip()[:70]}")
    return found


def test_no_print_script_hardcodes_a_year():
    offenders = []
    for p in sorted((ROOT / "scripts").glob("print_*.py")):
        offenders += [f"{p.name} {o}" for o in _literal_years(p.read_text(encoding="utf-8"))]
    assert not offenders, "literal years in print scripts (read them from reference.observation_window or the mart):\n" + "\n".join(offenders)


def test_the_checker_catches_a_literal_year_and_ignores_comments():
    assert _literal_years("q('select 1 where cohort_year = 2024')")
    assert not _literal_years("x = 1  # 2024 is only in a comment")
