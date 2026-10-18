"""Phase 6: product health and goal scorecard are built from real outputs, adoption is never faked, and simulation is refused without approval."""
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from scripts import log_usage, validate_products as vp

ROOT = Path(__file__).resolve().parent.parent
needs_wh = pytest.mark.skipif(not vp.DB.exists(), reason="needs a built warehouse (make all-phases)")


def test_simulation_is_refused_without_approval():
    r = subprocess.run([sys.executable, "-m", "scripts.log_usage", "--simulate"], cwd=ROOT, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home())})
    assert r.returncode == 2 and "needs the program owner's approval" in r.stderr


def test_log_usage_rejects_an_unknown_event():
    con = duckdb.connect(":memory:")
    with pytest.raises(ValueError):
        log_usage.log_usage(con, "DP4", "club_market_view", "Club youth and community manager", "PURCHASE")


@needs_wh
def test_health_covers_every_product_with_quality_privacy_and_trust():
    con = duckdb.connect(str(vp.DB), read_only=True)
    try:
        rows = con.execute("select product_id, area from phase6.mart_product_health").fetchall()
    except duckdb.Error as e:
        pytest.skip(f"product health not built: {e}")
    areas = {}
    for p, a in rows:
        areas.setdefault(p, set()).add(a)
    assert set(areas) == {"DP1", "DP2", "DP3", "DP4", "DP5"}
    assert all({"quality", "privacy", "pipeline", "cost"} <= a for a in areas.values())
    assert all("trust" in areas[p] for p in ("DP2", "DP3", "DP4", "DP5"))


@needs_wh
def test_adoption_has_no_real_events_and_says_so():
    con = duckdb.connect(str(vp.DB), read_only=True)
    try:
        rows = con.execute("select real_events, status from phase6.mart_product_adoption").fetchall()
    except duckdb.Error as e:
        pytest.skip(f"adoption not built: {e}")
    assert rows and all(n == 0 and s == "AWAITING_REAL_USERS" for n, s in rows)


@needs_wh
def test_goal_scorecard_names_a_product_and_a_trust_companion_for_every_measured_kpi():
    con = duckdb.connect(str(vp.DB), read_only=True)
    try:
        rows = con.execute("select kpi_id, product_id, trust_label, value, status from phase6.mart_goal_scorecard").fetchall()
    except duckdb.Error as e:
        pytest.skip(f"scorecard not built: {e}")
    assert {r[0] for r in rows} >= {"fan_engagement_uplift", "fans_created_by_flag", "activatable_households", "youth_to_adult_fan_transition", "global_participants", "girls_share_of_youth"}
    for kpi, prod, trust, value, status in rows:
        assert prod and trust, kpi
        if status == "MEASURED":
            assert value is not None, kpi
    assert [r for r in rows if r[0] == "youth_to_adult_fan_transition"][0][4] == "NOT_MEASURABLE_BY_DESIGN"
