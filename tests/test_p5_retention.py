"""The age-out and revocation retention job, run on a small seeded store with every case in it. SYNTHETIC data."""
import datetime as dt

import duckdb
import pytest

from retention import job

PARAMS = {"as_of": "2027-12-31", "age_out_age": 18, "grace_months": 12, "max_record_months": 36, "revocation_delay_days": 0}


def _rec(con, person, hh, birth_year, registered, n=1, email=None, market="MKT-01", band="U17"):
    con.execute("insert into pii_store.child_record values ('matrix_export', ?, ?, ?, 'Ann', 'Test', ?, 'F', '12345', ?, ?, ?, 2025, ?)",
                [f"{person}-{n}", person, hh, birth_year, email or f"{hh.lower()}@example.com", market, band, registered])


@pytest.fixture()
def store():
    con = duckdb.connect()
    job.init_schema(con)
    cases = {
        "A": ("H-A", 2008), "B": ("H-B", 2009), "C": ("H-C", 2008), "D": ("H-D", None), "E": ("H-E", 2015), "F": ("H-F", 2015),
        "G1": ("H-G", 2008), "G2": ("H-G", 2016), "H": ("H-H", 2005), "I": ("H-I", 2014),
    }
    for person, (hh, by) in cases.items():
        _rec(con, person, hh, by, dt.datetime(2025, 6, 1))
    _rec(con, "C", "H-C", 2012, dt.datetime(2025, 7, 1), n=2)                  # a typo that makes the child look younger must not extend retention
    _rec(con, "D", "H-D", None, dt.datetime(2024, 1, 1), n=2)                  # older than the 36-month cap
    _rec(con, "I", "H-I", 1850, dt.datetime(2025, 7, 1), n=2)                  # an implausible birth year is ignored
    for hh in {c[0] for c in cases.values()}:
        con.execute("insert into pii_store.household_contact values (?, ?)", [hh, f"{hh.lower()}@example.com"])
        con.execute("insert into pii_store.consent_event values (?, ?, 'MARKETING_OPT_IN', 'GRANTED', 'NFL_CLUB_MARKETING', ?, ?)", [f"ev-{hh}", hh, dt.datetime(2025, 6, 1), dt.datetime(2025, 6, 1)])
        con.execute("insert into pii_store.household_activation values (?, true, 'ELIGIBLE')", [hh])
    con.execute("insert into pii_store.revocation values ('H-E', sha256('h-e@example.com'), ?)", [dt.datetime(2026, 5, 1)])      # revoked before the job date
    con.execute("insert into pii_store.revocation values ('H-F', sha256('h-f@example.com'), ?)", [dt.datetime(2028, 1, 2)])      # revoked after the job date
    yield con
    con.close()


def _persons(con):
    return {r[0] for r in con.execute("select distinct p5_person_id from pii_store.child_record").fetchall()}


def _households(con, table):
    return {r[0] for r in con.execute(f"select distinct household_id from pii_store.{table}").fetchall()}


def test_nothing_over_the_threshold_survives(store):
    res = job.run(store, dict(PARAMS))
    assert not any(res["violations"].values()), res["violations"]
    survivors = _persons(store)
    assert {"A", "C", "E", "G1", "H"}.isdisjoint(survivors)                    # aged out (A on the exact boundary, C by its oldest record, G1, H) or revoked (E)
    assert {"B", "D", "F", "G2", "I"} <= survivors                              # not yet due (B born 2009, F revokes after the job date) or kept by a newer record (D)
    left = {r[0] for r in store.execute("select source_record_id from pii_store.child_record where p5_person_id = 'D'").fetchall()}
    assert left == {"D-1"}                                                      # only the record older than the cap went


def test_revocation_removes_activation_at_once_and_keeps_only_a_hash(store):
    store.execute("update pii_store.household_activation set eligible_for_club_activation = true where household_id = 'H-E'")
    res = job.run(store, dict(PARAMS))
    assert res["newly_removed_from_activation"] == 1                           # H-E was still eligible when the job ran
    assert "H-E" not in _households(store, "household_contact") and "H-E" not in _households(store, "consent_event")
    assert store.execute("select count(*) from pii_store.suppression_list").fetchone()[0] == 1
    hashes = {r[0] for r in store.execute("select parent_email_hash from pii_store.suppression_list").fetchall()}
    assert all(len(h) == 64 and "@" not in h for h in hashes)
    assert store.execute("select eligible_for_club_activation from pii_store.household_activation where household_id = 'H-F'").fetchone()[0] is True   # revoked after the job date


def test_parent_side_goes_only_when_no_child_is_left(store):
    job.run(store, dict(PARAMS))
    assert "H-G" in _households(store, "household_contact")                    # one sibling aged out, the other remains: the household stays
    assert {"H-A", "H-C", "H-H", "H-E"}.isdisjoint(_households(store, "household_contact"))   # every child gone: contact, consent and activation go too
    assert {"H-A", "H-C", "H-H", "H-E"}.isdisjoint(_households(store, "consent_event") | _households(store, "household_activation"))


def test_log_and_aggregates_hold_counts_only(store):
    job.run(store, dict(PARAMS))
    text = " ".join(str(v) for t in ("retention_log", "retained_aggregate") for row in store.execute(f"select * from pii_store.{t}").fetchall() for v in row)
    assert "@" not in text and "Test" not in text and "Ann" not in text and "H-" not in text and "P5" not in text
    agg = dict(store.execute("select reason, sum(children) from pii_store.retained_aggregate group by 1").fetchall())
    assert agg["AGE_OUT"] == 4 and agg["REVOKED"] == 1                         # A, C, G1, H aged out; E revoked


def test_second_run_deletes_nothing_more(store):
    job.run(store, dict(PARAMS))
    again = job.run(store, dict(PARAMS))
    assert again["records_deleted"] == 0 and again["households_purged"] == 0 and not any(again["violations"].values())


def test_the_verification_catches_a_survivor(store):
    job.run(store, dict(PARAMS))
    _rec(store, "Z", "H-Z", 2000, dt.datetime(2025, 1, 1))                      # an aged-out child planted after the run
    assert job.verify(store, PARAMS)["v1 aged-out child survives"] == 1
    store.execute("insert into pii_store.household_contact values ('H-ORPHAN', 'x@example.com')")
    assert job.verify(store, PARAMS)["v5 orphan parent data survives"] == 1
