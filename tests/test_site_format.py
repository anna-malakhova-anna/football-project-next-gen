"""Table cell formatting on the results site (scripts/site_render.py)."""
import decimal

from scripts import site_render


def test_whole_decimal_amounts_read_as_counts_with_separators():
    assert site_render.fmt_cell(decimal.Decimal("87000"), "consent_gap_value") == "87,000"
    assert site_render.fmt_cell(decimal.Decimal("100.0"), "label_position") == "100"


def test_a_fractional_decimal_is_left_as_stored():
    assert site_render.fmt_cell(decimal.Decimal("0.500"), "threshold") == "0.500"


def test_the_uncertainty_table_hides_the_code_beside_its_plain_label():
    assert site_render.TABLE_HIDE["unc_decomp"] == {"component", "component_order"}
    assert site_render.COLUMN_LABELS["component_label"] == "Source of doubt"
