"""Table cell formatting on the results site (scripts/build_site.py)."""
import decimal

from scripts import build_site


def test_whole_decimal_amounts_read_as_counts_with_separators():
    assert build_site.fmt_cell(decimal.Decimal("87000"), "consent_gap_value") == "87,000"
    assert build_site.fmt_cell(decimal.Decimal("100.0"), "label_position") == "100"


def test_a_fractional_decimal_is_left_as_stored():
    assert build_site.fmt_cell(decimal.Decimal("0.500"), "threshold") == "0.500"


def test_the_uncertainty_table_hides_the_code_beside_its_plain_label():
    assert build_site.TABLE_HIDE["unc_decomp"] == {"component", "component_order"}
    assert build_site.COLUMN_LABELS["component_label"] == "Source of doubt"
