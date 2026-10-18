"""Roadmap checks (Phase 6 addendum, section 3) that need no warehouse: the seeds reference each other, the gates model carries the status rules, the template holds no literal numbers."""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rows(name):
    with (ROOT / "dbt/seeds" / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_roadmap_rows_reference_products_and_gates():
    gates = {r["gate_id"] for r in rows("product_targets.csv")}
    for r in rows("product_roadmap.csv"):
        assert r["product_id"] in {"DP1", "DP2", "DP3", "DP4", "DP5"}
        assert r["horizon"] in {"DELIVERED", "NOW", "NEXT", "LATER"}
        assert not r["gate_id"] or r["gate_id"] in gates
        assert r["status"] in {"draft", "confirmed"}
        assert (r["horizon"] == "DELIVERED") == bool(r["phase_ref"]), f"only delivered cards cite a phase: {r}"


def test_every_gate_is_on_a_card_and_has_a_source_model():
    used = {r["gate_id"] for r in rows("product_roadmap.csv") if r["gate_id"]}
    for g in rows("product_targets.csv"):
        assert g["gate_id"] in used, f"{g['gate_id']} is on no roadmap card"
        assert g["source_model"] and g["kind"] in {"TARGET", "GUARDRAIL", "PASS"}
        assert (ROOT / "dbt/target/manifest.json").exists() is False or g["source_model"] in (ROOT / "dbt/target/manifest.json").read_text()


def test_gate_status_rules_are_in_the_model():
    sql = (ROOT / "dbt/models/shares/exec/share_exec__roadmap_gates.sql").read_text()
    assert "when current_value is null then 'PENDING'" in sql
    assert "'MET'" in sql and "'NOT_YET'" in sql


def test_roadmap_template_has_no_literal_numbers():
    src = (ROOT / "scripts/site_product.py").read_text()
    start, end = src.index("def _gate_html"), src.index("# ---------------------------------------------------------------- D5")
    body = re.sub(r"'[^']*'|\"[^\"]*\"", "", src[start:end])   # ignore string literals; numbers must come from columns
    code = "\n".join(l for l in body.splitlines() if not l.strip().startswith("#"))
    assert not re.search(r"(?<![\w.])\d+(\.\d+)?%", code)


def test_a_pending_gate_never_draws_a_value_or_a_bar():
    from scripts.site_product import _gate_html
    html = _gate_html(dict(gate_id="G", gate_status="PENDING", bar_fill_pct=None, target_marker_pct=80.0, status_text="Baseline pending", value_text="baseline pending"))
    assert "<i " not in html and "baseline pending" in html.lower() and "vg-pending" in html
