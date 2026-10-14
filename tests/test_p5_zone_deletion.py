"""Retention versus deletion in the identity and linkage zones (spec section 10)."""
from __future__ import annotations

import duckdb
import pytest

from generator.population import load_config
from retention import zones

P = {"as_of": "2027-12-31", "age_out_age": 18, "grace_months": 12, "max_record_months": 36, "revocation_delay_days": 0}


@pytest.fixture()
def con():
    c = duckdb.connect(":memory:")
    for s in ("identity", "intermediate", "marts", "linkage"):
        c.execute(f"create schema {s}")
    c.execute("create table marts.bridge_registration_participant (registration_key varchar, participant_id varchar, match_record_id varchar)")
    c.execute("""create table identity.idr_input_records (match_record_id varchar, first_name varchar, last_name varchar, first_name_key varchar, last_name_key varchar, dob date,
                 contact_email varchar, contact_phone varchar, postal_code varchar, birth_year integer, is_minor boolean)""")
    c.execute("""create table intermediate.int_registrations_unioned (registration_key varchar, first_name varchar, last_name varchar, first_name_key varchar, last_name_key varchar, dob date,
                 contact_email varchar, contact_phone varchar, postal_code varchar)""")
    c.execute("create table marts.dim_participant (participant_id varchar, first_name varchar, last_name varchar, dob date, contact_email varchar, contact_phone varchar, birth_year integer)")
    c.execute("create table marts.participant_identifiers (participant_id varchar, identifier_value varchar)")
    c.execute("create table linkage.int_household (participant_id varchar, household_id varchar)")

    def person(pid, birth_year, minor):
        c.execute("insert into marts.bridge_registration_participant values (?, ?, ?)", [f"r-{pid}", pid, f"r-{pid}"])
        c.execute("insert into identity.idr_input_records values (?, 'A', 'B', 'a', 'b', date '2010-05-05', 'x@y.z', '5551234', '12345', ?, ?)", [f"r-{pid}", birth_year, minor])
        c.execute("insert into intermediate.int_registrations_unioned values (?, 'A', 'B', 'a', 'b', date '2010-05-05', 'x@y.z', '5551234', '12345')", [f"r-{pid}"])
        c.execute("insert into marts.dim_participant values (?, 'A', 'B', date '2010-05-05', 'x@y.z', '5551234', ?)", [pid, birth_year])
        c.execute("insert into marts.participant_identifiers values (?, 'x@y.z')", [pid])
        c.execute("insert into linkage.int_household values (?, 'H')", [pid])
    person("on_the_line", 2008, True)      # Dec 31 2026 + 12 months = Dec 31 2027: due exactly at as_of
    person("one_day_early", 2009, True)    # not yet
    person("adult", 1990, False)           # never a child: never deleted by this policy
    person("old_child", 2001, True)
    yield c
    c.close()


def test_only_children_past_age_out_plus_grace_are_due(con):
    assert zones.plan(con, P) == 2
    due = {r[0] for r in con.execute("select participant_id from _zone_due").fetchall()}
    assert due == {"on_the_line", "old_child"}


def test_no_direct_identifier_survives_and_the_pseudonymous_facts_stay(con):
    zones.apply(con, P)
    assert all(v == 0 for v in zones.survivors(con).values())
    row = con.execute("select first_name, dob, contact_email, birth_year from marts.dim_participant where participant_id = 'on_the_line'").fetchone()
    assert row == (None, None, None, 2008)
    assert con.execute("select postal_code from identity.idr_input_records where match_record_id = 'r-on_the_line'").fetchone()[0] == "123"
    assert con.execute("select count(*) from marts.participant_identifiers where participant_id = 'on_the_line'").fetchone()[0] == 0


def test_a_child_not_yet_due_and_an_adult_are_left_alone(con):
    zones.apply(con, P)
    for pid in ("one_day_early", "adult"):
        assert con.execute("select contact_email from marts.dim_participant where participant_id = ?", [pid]).fetchone()[0] == "x@y.z"
        assert con.execute("select count(*) from linkage.int_household where participant_id = ?", [pid]).fetchone()[0] == 1


def test_a_second_run_changes_nothing_more(con):
    zones.apply(con, P)
    again = zones.apply(con, P)
    assert all(v == 0 for k, v in again.items() if k.startswith(("marts.participant_identifiers", "linkage")))
    assert all(v == 0 for v in zones.survivors(con).values())


@pytest.mark.skipif(not zones.DB.exists(), reason="warehouse not built")
def test_retention_marts_rebuild_from_pseudonymous_facts_after_deletion():
    """The spec's test: delete in a copy, rebuild the Phase 4 retention marts, assert them unchanged within the configured tolerance."""
    tol = float(load_config()["phase5"]["retention"]["survival_tolerance"])
    res = zones.experiment(identity_rebuild=False)
    assert res["zone_counts"]["participants"] > 0
    assert all(v == 0 for v in res["survivors"].values())
    base, after = res["metrics"]["BASELINE"], res["metrics"]["FACTS_ONLY"]
    for m, b in base.items():
        assert abs(after[m] - b) <= tol * abs(b), m
