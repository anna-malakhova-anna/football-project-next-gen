from scripts import check_share_policy as sps
from scripts.check_share_policy import check, strip_comments

POLICY = [
    {"audience": "exec", "model": "share_exec__t", "column": "year", "allowed": "Y", "treatment": "DIMENSION"},
    {"audience": "exec", "model": "share_exec__t", "column": "n", "allowed": "Y", "treatment": "AGG"},
    {"audience": "exec", "model": "*", "column": "email", "allowed": "N", "treatment": "NOT_AVAILABLE"},
    {"audience": "ops", "model": "share_ops__t", "column": "email", "allowed": "Y", "treatment": "FULL"},
]
GOOD_COLS = [("share_exec", "share_exec__t", "year"), ("share_exec", "share_exec__t", "n"), ("share_ops", "share_ops__t", "email")]
GOOD_TAGS = {("share_exec", "share_exec__t", "year"): "none", ("share_exec", "share_exec__t", "n"): "none",
             ("share_ops", "share_ops__t", "email"): "direct"}


def kinds(problems):
    return {k for k, _ in problems}


def test_a_compliant_setup_passes():
    assert check(POLICY, GOOD_COLS, {"a.sql": "select year, n from t"}, GOOD_TAGS) == []


def test_unlisted_column_is_caught():
    cols = GOOD_COLS + [("share_exec", "share_exec__t", "extra")]
    assert "COLUMN_NOT_ALLOWED" in kinds(check(POLICY, cols, {}, {**GOOD_TAGS, ("share_exec", "share_exec__t", "extra"): "none"}))


def test_explicitly_denied_column_is_caught_even_if_someone_allowed_it():
    policy = POLICY + [{"audience": "exec", "model": "share_exec__t", "column": "email", "allowed": "Y", "treatment": "oops"}]
    cols = GOOD_COLS + [("share_exec", "share_exec__t", "email")]
    tags = {**GOOD_TAGS, ("share_exec", "share_exec__t", "email"): "none"}
    assert "COLUMN_DENIED" in kinds(check(policy, cols, {}, tags))


def test_select_star_is_caught_but_count_star_and_comments_are_not():
    assert "SELECT_STAR" in kinds(check(POLICY, GOOD_COLS, {"bad.sql": "select * from t"}, GOOD_TAGS))
    assert "SELECT_STAR" in kinds(check(POLICY, GOOD_COLS, {"bad.sql": "select t.* from t"}, GOOD_TAGS))
    assert "SELECT_STAR" in kinds(check(POLICY, GOOD_COLS, {"bad.sql": "SELECT DISTINCT * from t"}, GOOD_TAGS))
    assert check(POLICY, GOOD_COLS, {"ok.sql": "select count(*) from t -- select * is banned\n/* select * */"}, GOOD_TAGS) == []
    assert "select" not in strip_comments("-- select *").lower()


def test_direct_identifier_in_exec_or_analyst_is_caught_but_allowed_in_ops():
    tags = {**GOOD_TAGS, ("share_exec", "share_exec__t", "n"): "direct"}
    assert "DIRECT_IN_EXEC_ANALYST" in kinds(check(POLICY, GOOD_COLS, {}, tags))
    assert "DIRECT_IN_EXEC_ANALYST" not in kinds(check(POLICY, GOOD_COLS, {}, GOOD_TAGS))   # ops has a direct column


def test_missing_pii_tag_is_caught():
    tags = {k: v for k, v in GOOD_TAGS.items() if k[2] != "n"}
    assert "PII_TAG_MISSING" in kinds(check(POLICY, GOOD_COLS, {}, tags))


def test_stale_policy_and_unlisted_models_are_caught():
    stale = POLICY + [{"audience": "exec", "model": "share_exec__t", "column": "gone", "allowed": "Y", "treatment": "x"}]
    assert "POLICY_COLUMN_MISSING" in kinds(check(stale, GOOD_COLS, {}, GOOD_TAGS))
    cols = GOOD_COLS + [("share_media", "share_media__new", "name")]
    assert "MODEL_NOT_IN_POLICY" in kinds(check(POLICY, cols, {}, {**GOOD_TAGS, ("share_media", "share_media__new", "name"): "direct"}))
    ghost = POLICY + [{"audience": "ops", "model": "share_ops__ghost", "column": "x", "allowed": "Y", "treatment": "x"}]
    assert "POLICY_MODEL_MISSING" in kinds(check(ghost, GOOD_COLS, {}, GOOD_TAGS))


def _manifest(shares: dict[str, tuple[str, list[str]]]):
    """shares: name -> (schema, [parent names]); parents: 'link' is a linkage model, 'plain' is an ordinary mart."""
    nodes = {
        "model.p.link": {"name": "link_household_fan_account", "schema": "linkage", "resource_type": "model", "original_file_path": "models/linkage/l.sql", "depends_on": {"nodes": []}},
        "model.p.plain": {"name": "mart_x", "schema": "measurement", "resource_type": "model", "original_file_path": "models/measurement/m.sql", "depends_on": {"nodes": []}},
        "model.p.mid": {"name": "mid", "schema": "linkage", "resource_type": "model", "original_file_path": "models/linkage/mid.sql", "depends_on": {"nodes": ["model.p.link"]}},
    }
    for name, (schema, parents) in shares.items():
        nodes[f"model.p.{name}"] = {"name": name, "schema": schema, "resource_type": "model", "original_file_path": f"models/shares/{schema}/{name}.sql",
                                    "depends_on": {"nodes": [f"model.p.{p}" for p in parents]}}
    return {"nodes": nodes, "sources": {}}


def test_a_share_built_from_the_linkage_schema_is_a_leak_unless_it_is_an_approved_aggregate():
    m = _manifest({"share_exec__participation_global": ("share_exec", ["plain"]),
                   "share_exec__fan_engagement_effect": ("share_exec", ["mid"]),        # approved aggregate, through an intermediate linkage model
                   "share_analyst__households": ("share_analyst", ["mid"])})
    assert [p[0] for p in sps.check_linkage(m)] == ["LINKAGE_LEAK"]
    assert "share_analyst__households" in sps.check_linkage(m)[0][1]


def test_nothing_linked_reaches_marketing_or_media_even_as_an_approved_name():
    m = _manifest({"share_marketing__contact_list": ("share_marketing", ["link"]), "share_media__roster": ("share_media", ["plain"])})
    out = sps.check_linkage(m)
    assert [p[0] for p in out] == ["LINKAGE_IN_MARKETING"] and "contact_list" in out[0][1]


def test_club_and_privacy_columns_must_be_dimensions_flags_or_catalogued_metrics():
    pol = [
        {"audience": "club", "model": "m", "column": "participants_allocated", "allowed": "Y", "treatment": "AGGREGATE_SUPPRESSED"},
        {"audience": "club", "model": "m", "column": "made_up_metric", "allowed": "Y", "treatment": "AGGREGATE_SUPPRESSED"},
        {"audience": "club", "model": "m", "column": "free_value", "allowed": "Y", "treatment": "VALUE"},
        {"audience": "privacy", "model": "p", "column": "free_value", "allowed": "Y", "treatment": "VALUE"},
        {"audience": "club", "model": "m", "column": "club_market_id", "allowed": "Y", "treatment": "DIMENSION"},
    ]
    found = sps.check_club_and_metrics(pol, {"participants_allocated"}, None)
    assert ("METRIC_NOT_IN_CATALOG", "share_club.m.made_up_metric") in found
    assert ("CLUB_COLUMN_UNTREATED", "share_club.m.free_value") in found
    assert not any("share_privacy" in d for _, d in found)               # VALUE is allowed in the privacy share only
    assert len(found) == 2


def test_a_club_share_may_read_only_approved_aggregate_marts():
    manifest = {"nodes": {
        "model.p.share_club__x": {"resource_type": "model", "schema": "share_club", "name": "share_club__x", "depends_on": {"nodes": ["model.p.mart_market_coverage", "model.p.fct_participant_year", "seed.p.privacy_params"]}},
        "model.p.mart_market_coverage": {"resource_type": "model", "schema": "quality", "name": "mart_market_coverage", "depends_on": {"nodes": []}},
        "model.p.fct_participant_year": {"resource_type": "model", "schema": "facts", "name": "fct_participant_year", "depends_on": {"nodes": []}},
        "seed.p.privacy_params": {"resource_type": "seed", "schema": "reference", "name": "privacy_params", "depends_on": {"nodes": []}},
    }, "sources": {}}
    assert sps.check_club_and_metrics([], set(), manifest) == [("CLUB_LINEAGE", "share_club__x <- fct_participant_year")]


def test_an_identifying_tag_is_refused_in_club_and_privacy_shares():
    cols = [("share_club", "t", "c")]
    pol = [{"audience": "club", "model": "t", "column": "c", "allowed": "Y", "treatment": "DIMENSION"}]
    for tag in ("direct", "quasi"):
        assert ("QUASI_IN_CLUB_PRIVACY", "share_club.t.c") in check(pol, cols, {}, {("share_club", "t", "c"): tag})
    assert not check(pol, cols, {}, {("share_club", "t", "c"): "none"})
