from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _wf():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_ci_runs_the_full_build_then_the_site_and_fits_the_ten_minute_budget():
    wf = _wf()
    build = wf["jobs"]["build"]
    runs = [s["run"] for s in build["steps"] if "run" in s]
    assert runs.index("make all-phases") < runs.index("make site")
    assert build["timeout-minutes"] <= 10
    assert any("setup-uv" in s.get("uses", "") and s.get("with", {}).get("enable-cache") for s in build["steps"])   # the uv environment is cached


def test_the_site_is_deployed_only_from_main_and_only_after_the_build():
    wf = _wf()
    deploy = wf["jobs"]["deploy"]
    assert deploy["needs"] == "build" and "refs/heads/main" in deploy["if"] and "push" in deploy["if"]
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    assert wf["permissions"] == {"contents": "read"}                  # the build job gets no write access
    assert not any("publish" in s.get("run", "") for j in wf["jobs"].values() for s in j.get("steps", []))      # CI never runs `make publish`


def test_all_phases_covers_every_check_the_spec_names():
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    block = make[make.index("all-phases: dbt/profiles.yml"):make.index("# Phases 3 and 4 are built together")]
    for needed in ("validate_contracts", "dbt/profiles.yml", "$(DBT) test", "pytest", "check_eval_isolation", "check_lineage", "check_share_policy", "check_id_stability"):
        assert needed in block, needed
