import csv

from scripts import build_access_policy, build_metrics_doc


def test_metrics_doc_is_in_sync_with_the_catalog():
    assert build_metrics_doc.OUT.read_text(encoding="utf-8") == build_metrics_doc.render(), "run `make docs`"


def test_access_policy_doc_is_in_sync_with_the_policy_seed():
    assert build_access_policy.OUT.read_text(encoding="utf-8") == build_access_policy.render(), "run `make docs`"


def test_every_catalog_metric_appears_in_the_metrics_doc():
    text = build_metrics_doc.render()
    with open(build_metrics_doc.CATALOG, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            assert f"`{r['metric_id']}`" in text


def test_access_policy_names_every_audience_and_states_it_is_not_legal_advice():
    text = build_access_policy.render()
    for a in ("exec", "analyst", "ops", "marketing", "media"):
        assert f"### {a}" in text
    assert "not legal interpretations" in text and "NULL consent is not consent" in text
