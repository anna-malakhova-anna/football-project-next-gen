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
