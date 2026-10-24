from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _wf():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_ci_runs_the_full_build_then_the_site_and_fits_the_time_budget():
    wf = _wf()
    build = wf["jobs"]["build"]
    runs = [s["run"] for s in build["steps"] if "run" in s]
    assert runs.index("make all-phases") < runs.index("make site")
    assert build["timeout-minutes"] <= 25            # the rework made the full build about 6 minutes locally (was 2.5); a hosted runner is slower
    assert any("setup-uv" in s.get("uses", "") and s.get("with", {}).get("enable-cache") for s in build["steps"])   # the uv environment is cached


def test_ci_does_not_deploy_and_fails_when_the_committed_public_is_stale():
    wf = _wf()
    assert list(wf["jobs"]) == ["build"]                              # Render serves the committed public/; there is no Pages deploy job
    assert wf["permissions"] == {"contents": "read"}                  # the build job gets no write access
    runs = [s["run"] for s in wf["jobs"]["build"]["steps"] if "run" in s]
    assert not any("publish" in r for r in runs)                      # CI never runs `make publish`
    assert not any("pages" in s.get("uses", "") or "deploy" in s.get("uses", "") for s in wf["jobs"]["build"]["steps"])
    check = [r for r in runs if r.startswith("make public")]
    assert len(check) == 1 and "git diff" in check[0] and "exit 1" in check[0] and "public/" in check[0]
    assert any("upload-artifact" in s.get("uses", "") and s.get("if") == "failure()" for s in wf["jobs"]["build"]["steps"])   # the rebuilt public/ can be downloaded
    assert runs.index("make all-phases") < runs.index(check[0])       # public/ is rebuilt from the full build's warehouse


def test_all_phases_covers_every_check_the_spec_names():
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    block = make[make.index("all-phases: dbt/profiles.yml"):make.index("# Phases 3 and 4 are built together")]
    for needed in ("validate_contracts", "dbt/profiles.yml", "$(DBT) test", "pytest", "check_eval_isolation", "check_lineage", "check_share_policy", "check_id_stability"):
        assert needed in block, needed
