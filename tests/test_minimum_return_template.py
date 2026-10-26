"""Phase 7 (spec section 7): the minimum-return template's checks are real. The example file passes every check; each kind of mistake a federation
could make is caught by the check written for it. Uses the same validator as every contract (scripts/validate_contracts.py)."""
import csv
from pathlib import Path

import duckdb
import pytest

from scripts import validate_contracts as vc

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "contracts" / "templates" / "GMP_MINIMUM_RETURN.yml"
EXAMPLE = ROOT / "docs" / "playbook" / "templates" / "gmp_minimum_return_example.csv"


def _run(rows: list[dict]) -> dict[str, str]:
    contract = vc.load_contract(TEMPLATE)
    con = duckdb.connect()
    con.execute("create schema raw")
    cols = list(rows[0])
    con.execute(f"create table raw.gmp_minimum_return ({', '.join(f'{c} varchar' for c in cols)})")
    con.executemany(f"insert into raw.gmp_minimum_return values ({', '.join('?' for _ in cols)})", [[r[c] for c in cols] for r in rows])
    return {(r["column_name"] or r["rule"]): r["status"] for r in vc.evaluate(con, contract) if r["status"] != "PASS"}


def _example() -> list[dict]:
    with open(EXAMPLE, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_the_template_is_outside_the_contracts_that_validate_on_every_build():
    assert TEMPLATE.parent.name == "templates" and not list((ROOT / "contracts").glob("GMP_MINIMUM_RETURN*.yml"))


def test_the_example_passes_every_check():
    assert _run(_example()) == {}


@pytest.mark.parametrize("change, caught_by", [
    ({"players": "24"}, "players_equals_girls_boys_and_not_recorded"),
    ({"teams": "6"}, "every_team_has_a_minimum_roster"),
    ({"age_band": "U11"}, "age_band"),
    ({"season": "25"}, "season"),
])
def test_each_mistake_is_caught_by_its_check(change, caught_by):
    rows = _example()
    rows[0].update(change)
    assert caught_by in _run(rows)


def test_a_round_estimate_and_a_duplicate_row_are_caught():
    rows = _example()
    rows[1].update({"girls": "20", "boys": "30", "sex_not_recorded": "0", "players": "50", "teams": "5"})
    rows.append(dict(rows[0]))
    found = _run(rows)
    assert "players_is_not_a_round_estimate" in found and "season, region, age_band" in found
