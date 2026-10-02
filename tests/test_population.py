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


def test_twins_exist_and_look_like_twins(pop):
    cfg, people, parts = pop
    groups = collections.defaultdict(list)
    for p in people:
        if p["twin_group_id"]:
            groups[p["twin_group_id"]].append(p)
    youth_households = len({p["household_id"] for p in people if p["household_id"]})
    assert len(groups) >= 10
    assert len(groups) / youth_households == pytest.approx(cfg["population"]["twins"]["household_share"], abs=0.004)
    for pair in groups.values():
        a, b = pair
        assert len(pair) == 2 and a["household_id"] == b["household_id"]
        assert a["dob"] == b["dob"] and a["family_name"] == b["family_name"]
        assert a["guardian_email"] == b["guardian_email"] and a["first_season"] == b["first_season"]
        assert a["given_name"].lower() != b["given_name"].lower()
        assert not a["is_cross_border"] and not b["is_cross_border"] and not a["is_multi_league"] and not b["is_multi_league"]
    assert any(a["sex"] == b["sex"] for a, b in groups.values())          # sometimes the same sex
    assert any(a["sex"] != b["sex"] for a, b in groups.values())
    # twins register in the same seasons, terms and country
    plan = collections.defaultdict(list)
    for r in parts:
        plan[r["true_person_id"]].append((r["season_year"], r["season_term"], r["country_code"], r["league_slot"]))
    for a, b in groups.values():
        assert sorted(plan[a["true_person_id"]]) == sorted(plan[b["true_person_id"]])


def test_name_change_cases(pop):
    cfg, people, _ = pop
    changers = [p for p in people if p["name_change_season"]]
    assert len(changers) >= cfg["population"]["name_change"]["min_count"]
    for p in changers:
        assert p["segment"] == "INTL" and p["sex"] == "F" and not p["is_minor"]
        assert p["later_family_name"] != p["family_name"]
        assert p["first_season"] < p["name_change_season"] <= p["last_season"]


def test_some_movers_register_in_both_countries_in_the_year_they_move(pop):
    cfg, people, parts = pop
    movers = [p for p in people if p["is_cross_border"]]
    dual = [p for p in movers if p["dual_country_year"]]
    assert dual and len(dual) / len(movers) == pytest.approx(cfg["population"]["cross_border_dual_year_share"], abs=0.15)
    assert all(p["dual_country_year"] == p["switch_season"] for p in dual)
    countries = collections.defaultdict(set)
    terms = collections.defaultdict(set)
    for r in parts:
        countries[(r["true_person_id"], r["season_year"])].add(r["country_code"])
        terms[(r["true_person_id"], r["season_year"], r["country_code"])].add(r["season_term"])
    two_country_years = {k for k, v in countries.items() if len(v) > 1}
    assert {k[0] for k in two_country_years} == {p["true_person_id"] for p in dual}     # nobody else does it
    assert len(two_country_years) == len(dual)                                           # exactly one such year each
    by_id = {p["true_person_id"]: p for p in people}
    for pid, year in two_country_years:
        p = by_id[pid]
        # the US part of a move year is one term: spring before moving out, fall after moving in
        expected = {"SPRING"} if p["home_country"] == "US" else {"FALL"}
        assert terms[(pid, year, "US")] == expected
        assert terms[(pid, year, "CA")] == {"ANNUAL"}


def test_movers_who_arrive_in_the_us_play_normal_terms_afterwards(pop):
    _, people, parts = pop
    by_id = {p["true_person_id"]: p for p in people}
    later = [r for r in parts if by_id[r["true_person_id"]]["is_cross_border"]
             and by_id[r["true_person_id"]]["alt_country"] == "US"
             and r["season_year"] > by_id[r["true_person_id"]]["switch_season"] and r["country_code"] == "US"]
    assert later and {r["season_term"] for r in later} == {"SPRING", "FALL"}
