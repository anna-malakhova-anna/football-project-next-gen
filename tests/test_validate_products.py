"""Phase 6: the product specs validate, and the validator refuses what it should."""
import copy

import duckdb
import pytest

from scripts import validate_products as vp

pytestmark = pytest.mark.skipif(not vp.MANIFEST.exists(), reason="needs a dbt manifest (make all-phases)")


def good():
    return vp.load()


def test_the_real_specs_validate_with_live_quality_indicators():
    con = duckdb.connect(str(vp.DB), read_only=True) if vp.DB.exists() else None
    try:
        assert vp.validate(good(), con) == []
    finally:
        if con is not None:
            con.close()


def _mut(fn):
    p = copy.deepcopy(good())
    fn(p)
    return vp.validate(p)


def test_a_missing_required_field_is_refused():
    assert any("missing field owner_role" in b for b in _mut(lambda p: p["DP4"].pop("owner_role")))


def test_a_bad_version_is_refused():
    assert any("not semver" in b for b in _mut(lambda p: p["DP4"].__setitem__("version", "1.0")))


def test_an_output_port_that_is_not_a_share_model_is_refused():
    assert any("not in the dbt manifest" in b or "not a share schema" in b for b in _mut(lambda p: p["DP4"]["output_ports"][0].__setitem__("model", "dq_scorecard_market")))


def test_a_metric_that_is_not_in_the_catalog_is_refused():
    assert any("not in metric_catalog" in b for b in _mut(lambda p: p["DP4"]["metrics"].append("made_up_metric")))


def test_a_prohibited_use_without_an_enforcing_test_is_refused():
    def f(p):
        p["DP4"]["privacy"]["prohibited_uses"][0]["enforced_by"] = []
    assert any("names no enforcing test" in b for b in _mut(f))

    def g(p):
        p["DP4"]["privacy"]["prohibited_uses"][0]["enforced_by"] = [{"kind": "dbt_test", "name": "no_such_test"}]
    assert any("does not exist" in b for b in _mut(g))


def test_every_goal_needs_a_driver_product():
    def f(p):
        for x in p.values():
            if "G3" in x["goals"]:
                x["value_proposition"] = "enabler"
    assert any("goal G3 has no driver product" in b for b in _mut(f))
