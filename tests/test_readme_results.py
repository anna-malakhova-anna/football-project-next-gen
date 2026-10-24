"""The README results table and the Phase 5 results bullets are generated from the warehouse (scripts/build_readme_results.py, `make docs`)."""
import re

import duckdb
import pytest

from scripts import build_readme_results as brr
from scripts.common import DB

needs_wh = pytest.mark.skipif(not DB.exists(), reason="needs a built warehouse (make all-phases)")


@pytest.fixture(scope="module")
def regions():
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return brr.render_regions(con)
    finally:
        con.close()


@needs_wh
def test_the_readme_results_match_the_warehouse(regions):
    text = brr.README.read_text(encoding="utf-8")
    assert brr.apply(text, regions) == text, "run `make docs` (scripts.build_readme_results --diff shows which numbers moved)"


@needs_wh
def test_check_fails_when_a_number_in_the_readme_is_wrong(regions):
    text = brr.README.read_text(encoding="utf-8")
    cur = brr.current_regions(text)[brr.TABLE_TAG]
    first_number = re.search(r"\*\*(\d[\d,]*)\*\*", cur).group(1)
    tampered = text.replace(first_number, "9,999,999", 1)
    assert brr.apply(tampered, regions) != tampered
    assert brr.changed_numbers(brr.current_regions(tampered)[brr.TABLE_TAG], regions[brr.TABLE_TAG])


@needs_wh
def test_every_placeholder_is_filled_and_no_number_is_missing(regions):
    for body in regions.values():
        assert not re.search(r"\{[a-z_0-9]+\}", body)
        assert "None" not in body and "nan" not in body.lower().split()


def test_the_readme_carries_both_marked_regions():
    text = brr.README.read_text(encoding="utf-8")
    for tag in (brr.TABLE_TAG, brr.P5_TAG):
        assert text.count(brr.marker(tag)) == 1 and text.count(brr.marker(tag, end=True)) == 1


def test_make_docs_regenerates_the_readme_results():
    make = (brr.ROOT / "Makefile").read_text(encoding="utf-8")
    assert "scripts.build_readme_results" in make[make.index("\ndocs:"):make.index("\nclean:")]
