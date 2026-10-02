from scripts.build_data_dictionary import OUT_PATH, render


def test_data_dictionary_is_in_sync_with_dbt_yaml():
    assert OUT_PATH.read_text(encoding="utf-8") == render(), "run `make docs` to regenerate docs/data_dictionary.md"


def test_every_column_has_the_required_metadata():
    import yaml
    from scripts.build_data_dictionary import YAML_PATH
    cols = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))["models"][0]["columns"]
    for c in cols:
        assert c["description"] and c["data_type"], c["name"]
        m = c["meta"]
        assert {"group", "nullable", "pii", "derivation", "source_mapping"} <= set(m), c["name"]
        assert m["pii"] in {"Direct identifier", "Quasi-identifier", "Non-PII"}, c["name"]
        assert set(m["source_mapping"]) == {"US_LEAGUE", "CA_CLUB", "INTL_FED"}, c["name"]
