import collections

import pytest

from generator.population import build_population, load_config


@pytest.fixture(scope="module")
def pop():
    cfg = load_config()
    people, parts = build_population(cfg)
    return cfg, people, parts


def test_segment_counts(pop):
    cfg, people, _ = pop
    n = cfg["population"]["total_people"]
    seg = cfg["population"]["segments"]
    c = collections.Counter(p["segment"] for p in people)
    assert len(people) == n
    assert c["US_YOUTH"] == round(n * seg["us_youth"])
    assert c["CA_YOUTH"] == round(n * seg["ca_youth"])
    assert c["INTL"] == round(n * seg["intl"])
    assert c["ADULT_US_CA"] == n - c["US_YOUTH"] - c["CA_YOUTH"] - c["INTL"]


def test_ids_unique_and_segments_not_leaked(pop):
    _, people, _ = pop
    ids = [p["true_person_id"] for p in people]
    assert len(set(ids)) == len(ids)
    assert [p["segment"] for p in people[:200]].count("US_YOUTH") < 200  # shuffled


def test_deterministic():
    cfg = load_config()
    a, pa = build_population(cfg)
    b, pb = build_population(cfg)
    assert a == b and pa == pb


def test_youth_ages_at_first_season(pop):
    cfg, people, _ = pop
    lo, hi = cfg["population"]["youth_age_range"]
    for p in people:
        age = p["first_season"] - p["dob"].year
        if p["is_minor"]:
            assert lo <= age <= hi
        else:
            assert 18 <= age <= 55


def test_households_share_guardian_and_sibling_share(pop):
    cfg, people, _ = pop
    hh = collections.defaultdict(list)
    for p in people:
        if p["household_id"]:
            hh[p["household_id"]].append(p)
    for kids in hh.values():
        assert len({k["guardian_email"] for k in kids}) == 1
        assert len({k["home_country"] for k in kids}) == 1
    youth = [p for p in people if p["is_minor"]]
    with_sib = sum(len(hh[p["household_id"]]) > 1 for p in youth)
    assert with_sib / len(youth) == pytest.approx(
        cfg["population"]["household"]["youth_with_sibling_share"], abs=0.04)
    # a guardian email never spans two households
    owner = {}
    for hid, kids in hh.items():
        e = kids[0]["guardian_email"]
        assert owner.setdefault(e, hid) == hid


def test_adults_have_own_contact_minors_have_guardian(pop):
    _, people, _ = pop
    for p in people:
        if p["is_minor"]:
            assert p["guardian_email"] and p["own_email"] is None
        else:
            assert p["own_email"] and p["guardian_email"] is None


def test_francophone_share_of_ca_youth(pop):
    cfg, people, _ = pop
    ca = [p for p in people if p["segment"] == "CA_YOUTH"]
    fr = sum(p["language"] == "fr" for p in ca) / len(ca)
    assert fr == pytest.approx(cfg["population"]["ca_francophone_share"], abs=0.06)
    assert {p["home_region"] for p in ca if p["language"] == "fr"} <= {"QC", "NB", "ON"}


def test_cross_border_movers(pop):
    cfg, people, parts = pop
    usca = [p for p in people if p["home_country"] in ("US", "CA")]
    movers = [p for p in usca if p["is_cross_border"]]
    assert len(movers) == pytest.approx(
        len(usca) * cfg["population"]["cross_border_share_of_us_ca"], abs=2)
    by_person = collections.defaultdict(set)
    for r in parts:
        by_person[r["true_person_id"]].add(r["source_system"])
    for m in movers:
        assert by_person[m["true_person_id"]] == {"US_LEAGUE", "CA_CLUB"}


def test_multi_league_share_is_about_5_percent(pop):
    cfg, people, parts = pop
    us_youth = {p["true_person_id"] for p in people if p["segment"] == "US_YOUTH"}
    slots = collections.defaultdict(lambda: collections.Counter())
    for r in parts:
        if r["true_person_id"] in us_youth and r["league_slot"] == 1:
            slots[r["true_person_id"]][(r["season_year"], r["season_term"])] += 1
    two = {r["true_person_id"] for r in parts if r["league_slot"] == 2}
    assert two <= us_youth
    assert len(two) / len(us_youth) == pytest.approx(
        cfg["participation"]["us_two_leagues_same_season_share"], abs=0.005)
    # every slot-2 row has a matching slot-1 row in the same season and term
    s1 = {(r["true_person_id"], r["season_year"], r["season_term"]) for r in parts if r["league_slot"] == 1}
    for r in parts:
        if r["league_slot"] == 2:
            assert (r["true_person_id"], r["season_year"], r["season_term"]) in s1


def test_participation_rules(pop):
    cfg, people, parts = pop
    ymax = cfg["population"]["youth_age_range"][1]
    by = {p["true_person_id"]: p for p in people}
    seasons = collections.defaultdict(set)
    for r in parts:
        p = by[r["true_person_id"]]
        assert r["season_year"] >= p["first_season"]
        if p["is_minor"]:
            assert r["season_year"] - p["dob"].year <= ymax
        assert (r["season_term"] == "ANNUAL") == (r["country_code"] != "US")
        seasons[r["true_person_id"]].add(r["season_year"])
    assert set(seasons) == set(by)  # everyone participates at least once
    for pid, ys in seasons.items():  # contiguous seasons: churn is permanent
        assert sorted(ys) == list(range(min(ys), max(ys) + 1))


def test_churn_higher_for_14_plus_than_8_to_11(pop):
    _, people, parts = pop
    by = {p["true_person_id"]: p for p in people}
    active = collections.defaultdict(set)
    for r in parts:
        active[r["true_person_id"]].add(r["season_year"])
    def rate(lo, hi):
        n = d = 0
        for pid, ys in active.items():
            p = by[pid]
            if p["is_cross_border"] or not p["is_minor"]:
                continue
            for y in (2023, 2024):
                if y in ys and lo <= y - p["dob"].year <= hi and y + 1 - p["dob"].year <= 17:
                    n += (y + 1) not in ys
                    d += 1
        return n / d
    assert rate(14, 16) > rate(8, 11) + 0.1


def test_girls_new_player_share_grows(pop):
    _, people, _ = pop
    share = {}
    for y in (2023, 2024, 2025):
        new = [p for p in people if p["is_minor"] and p["first_season"] == y]
        share[y] = sum(p["sex"] == "F" for p in new) / len(new)
    assert share[2023] < share[2024] < share[2025]


def test_consent_and_nickname_fields(pop):
    cfg, people, _ = pop
    us = [p for p in people if p["segment"] == "US_YOUTH"]
    nick = sum(p["nickname"] is not None for p in us) / len(us)
    assert nick == pytest.approx(cfg["population"]["nickname_share"], abs=0.03)
    assert all(isinstance(p["marketing_opt_in"], bool) and isinstance(p["photo_consent"], bool)
               for p in people)
