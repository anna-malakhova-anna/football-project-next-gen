import re

from scripts import site_tables as st
from scripts.site_product import changelog_html


def test_every_table_gets_a_colgroup_and_exactly_one_flexible_column():
    html = ("<table><thead><tr><th>Product</th><th>Version</th><th>Change</th><th>Links</th></tr></thead><tbody>"
            "<tr><td>DP1 League Intake</td><td>1.0.0</td><td>A long description of what changed in this version of the product.</td><td>ADR-018, ADR-021</td></tr>"
            "<tr><td>DP2 Master</td><td>0.9.0</td><td>Another long description of a change, in plain words.</td><td>ADR-003</td></tr></tbody></table>")
    out = st.enhance(html)
    assert out.count("<colgroup>") == 1 and out.count("<col class=") == 4
    assert re.findall(r"<col class='([^']+)'>", out) == ["c-name", "c-short", "c-flex", "c-link"]
    assert "data-stack" in out and 'data-label="Version"' in out
    assert out.count("class='adr'") == 3, "each ADR reference is its own non-breaking chip"


def test_enhance_is_idempotent_and_leaves_scripts_alone():
    html = "<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>x</td><td>y</td></tr></tbody></table><script>var t='<table><tr><td>q</td></tr></table>'</script>"
    once = st.enhance(html)
    assert st.enhance(once) == once and "var t='<table><tr><td>q</td></tr></table>'" in once


def test_changelog_change_text_has_no_model_names_or_codes():
    html = changelog_html()
    visible = re.sub(r"<details class='vrow-detail'>.*?</details>", "", html, flags=re.S)
    cells = re.findall(r"<td>(.*?)</td>", visible, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", " ".join(cells))
    assert not re.search(r"\b(?:share|mart|dq|eval)_|\b[a-z]+_[a-z_]+\b|\b[A-Z]{5,}_[A-Z_]+\b", text), text
    assert "For analysts" in html
