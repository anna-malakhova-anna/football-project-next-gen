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
