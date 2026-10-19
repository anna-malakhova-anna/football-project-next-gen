from scripts import check_product_boundaries as cb


def test_boundaries_hold_and_debt_only_shrinks():
    problems, violations, info = cb.analyse()
    debt = cb.read_debt()
    assert not problems, problems
    assert set(violations) == set(debt), "products/boundary_debt.csv must list exactly the current violations"
    assert all(reason.strip() for reason in debt.values())


def test_every_model_has_one_owner():
    _, _, info = cb.analyse()
    assert all(o is not None for o in info["owner"].values())


def test_cycle_finder_finds_a_cycle_and_accepts_a_dag():
    assert cb.find_cycle({("DP1", "DP2"), ("DP2", "DP3")}) is None
    c = cb.find_cycle({("DP1", "DP2"), ("DP2", "DP3"), ("DP3", "DP1")})
    assert c is not None and c[0] == c[-1] and set(c) == {"DP1", "DP2", "DP3"}
