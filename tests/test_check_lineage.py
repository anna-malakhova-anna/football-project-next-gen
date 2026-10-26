import copy

from scripts import check_lineage as cl


def _model(name, path, deps=()):
    return {"name": name, "resource_type": "model", "original_file_path": path, "depends_on": {"nodes": list(deps)}}


def _manifest(extra=None, patch=None):
    nodes = {
        "model.p.stg_us": _model("stg_us", "models/staging/stg_us.sql"),
        "model.p.dim_participant": _model("dim_participant", "models/marts/dim_participant.sql", ["model.p.stg_us"]),
        "model.p.stg_school_headcounts": _model("stg_school_headcounts", "models/staging/stg_school_headcounts.sql"),
        "model.p.fct_reported_headcount": _model("fct_reported_headcount", "models/facts/fct_reported_headcount.sql", ["model.p.stg_school_headcounts"]),
        "model.p.mart_reported_headcount": _model("mart_reported_headcount", "models/measurement/mart_reported_headcount.sql",
                                                  ["model.p.fct_reported_headcount", "model.p.dim_participant"]),
        "model.p.mart_kpi_scorecard": _model("mart_kpi_scorecard", "models/measurement/mart_kpi_scorecard.sql", ["model.p.mart_reported_headcount"]),
        "model.p.mart_restatement_log": _model("mart_restatement_log", "models/measurement/mart_restatement_log.sql"),
        "model.p.eval_headcount_overlap": _model("eval_headcount_overlap", "models/evaluation/eval_headcount_overlap.sql"),
        "model.p.stg_gmp_proxy": _model("stg_gmp_proxy", "models/phase7/stg_gmp_proxy.sql"),
        "model.p.stg_gmp_minimum_return": _model("stg_gmp_minimum_return", "models/phase7/stg_gmp_minimum_return.sql"),
    }
    nodes.update(extra or {})
    m = {"nodes": nodes, "sources": {}}
    if patch:
        patch(m)
    return m


def test_the_reporting_layer_may_see_both_sides():
    assert cl.find_violations(_manifest()) == []


def test_a_participant_model_reading_the_aggregate_fact_is_a_violation():
    leak = {"model.p.mart_participation_global": _model("mart_participation_global", "models/measurement/mart_participation_global.sql",
                                                        ["model.p.fct_reported_headcount"])}
    out = cl.find_violations(_manifest(leak))
    assert len(out) == 1 and "mart_participation_global" in out[0] and "fct_reported_headcount" in out[0]


def test_a_leak_is_found_through_intermediate_models():
    mid = {"model.p.int_x": _model("int_x", "models/intermediate/int_x.sql", ["model.p.stg_school_headcounts"]),
           "model.p.fct_participant_year": _model("fct_participant_year", "models/facts/fct_participant_year.sql", ["model.p.int_x"])}
    out = cl.find_violations(_manifest(mid))
    assert any("fct_participant_year" in p for p in out)


def test_the_aggregate_fact_reading_participants_is_a_violation():
    def patch(m):
        m["nodes"]["model.p.fct_reported_headcount"]["depends_on"]["nodes"].append("model.p.dim_participant")
    out = cl.find_violations(_manifest(patch=patch))
    assert any("fct_reported_headcount (aggregate-only) depends on participant models" in p for p in out)


def test_a_renamed_guarded_model_is_reported_not_silently_ignored():
    def patch(m):
        del m["nodes"]["model.p.fct_reported_headcount"]
        m["nodes"]["model.p.mart_reported_headcount"]["depends_on"]["nodes"] = ["model.p.dim_participant"]
    out = cl.find_violations(copy.deepcopy(_manifest(patch=patch)))
    assert any("fct_reported_headcount" in p and "not a model" in p for p in out)
