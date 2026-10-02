import re
from pathlib import Path

import duckdb
import pytest

from scripts import render_report as rr


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("create schema share_exec; create schema measurement")
    kpis = [("unique_participants", "Unique participants", 3962.0, 3351.0, 611.0, 0.18233, 3953.0, 3965.0),
            ("new_participants", "New participants", 1699.0, 1664.0, 35.0, 0.02103, None, None),
            ("retention_rate", "Year-over-year retention rate", 0.6753, 0.6393, 0.036, None, None, None),
            ("reactivated_participants", "Reactivated participants", 0.0, 0.0, 0.0, None, None, None),
            ("youth_girls_participants", "Youth girls participants", 1637.0, 1287.0, 350.0, 0.27195, None, None),
            ("girls_share_of_youth", "Girls' share of youth participation", 0.4578, 0.428, 0.0298, None, None, None),
            ("international_participants", "International participants", 1495.0, 1205.0, 290.0, 0.24, 1491.0, 1495.0),
            ("countries_with_participants", "Countries with at least one participant", 8.0, 8.0, 0.0, 0.0, None, None),
            ("multi_org_participants", "Multi-organization participants", 288.0, 224.0, 64.0, 0.28571, None, None),
            ("registrations_per_participant", "Registrations per participant", 1.416, 1.4106, 0.0054, 0.0038, None, None),
            ("returning_participants", "Returning participants", 2263.0, 1687.0, 576.0, 0.34, None, None),
            ("identity_range_pct", "Identity range", 0.00303, 0.00328, -0.00025, None, None, None),
            ("pct_participants_high_confidence", "High confidence", 0.9929, 0.9931, -0.0002, None, None, None),
            ("open_review_items", "Open review items", 61.0, 59.0, 2.0, 0.034, None, None),
            ("pct_registrations_failing_dq", "Failing DQ", 0.0224, 0.0246, -0.0023, None, None, None),
            ("sources_onboarded", "Sources onboarded", 3.0, 3.0, 0.0, 0.0, None, None),
            ("sources_known", "Sources known", 5.0, 5.0, 0.0, 0.0, None, None)]
    c.execute("create table measurement.mart_kpi_scorecard(participation_year int, kpi_id varchar, kpi_name varchar, value double, "
              "prior_year_value double, yoy_change double, yoy_change_pct double, low double, high double, methodology_version varchar)")
    for k in kpis:
        c.execute("insert into measurement.mart_kpi_scorecard values (2025, ?, ?, ?, ?, ?, ?, ?, ?, '1.0')", list(k))
    c.execute("insert into measurement.mart_kpi_scorecard values (2024, 'youth_girls_participants', 'Youth girls', 1287.0, null, null, null, null, null, '1.0')")
    c.execute("create table share_exec.share_exec__participation_by_country(participation_year int, country_code varchar, "
              "participants_attributed bigint, participants_present bigint, suppressed varchar)")
    c.execute("insert into share_exec.share_exec__participation_by_country values (2025, null, 3962, null, 'NONE'), (2025, 'US', 3900, 3910, 'NONE'), "
              "(2025, 'XX', null, null, 'PRIMARY'), (2025, 'YY', null, null, 'SECONDARY')")
    c.execute("create table share_exec.share_exec__participation_segments(participation_year int, country_code varchar, age_band varchar, "
              "participants bigint, girls_share_of_youth double, suppressed varchar)")
    c.execute("insert into share_exec.share_exec__participation_segments values (2025, null, null, 3962, 0.4578, 'NONE'), "
              "(2024, null, null, 3351, null, 'PRIMARY'), (2025, 'US', null, 3900, 0.46, 'NONE')")
    return c


def test_the_data_trust_panel_sits_directly_under_the_headline_numbers(con):
    text = rr.render(con, 2025)
    assert text.index("## Headline numbers") < text.index("### Data trust") < text.index("## Participants by country")
    assert "Open review items" in text.split("### Data trust")[1].split("##")[0]


def test_suppressed_cells_are_labelled_and_never_shown_as_numbers(con):
    text = rr.render(con, 2025)
    assert text.count("suppressed") >= 3
    assert "| XX | suppressed | suppressed |" in text and "| YY | suppressed | suppressed |" in text
    assert "| 2024 | 3,351 | suppressed |" in text                  # published count, suppressed share
    assert "n/a" in text                                          # presence has no total


def test_bounds_and_changes_come_straight_from_the_scorecard(con):
    text = rr.render(con, 2025)
    assert "| Unique participants | 3,962 | 3,351 | +611 (+18.2%) | 3,953 to 3,965 |" in text
    assert "67.5%" in text and "+3.6 pts" in text
    assert "-0.0 pts" not in text and "+-" not in text


def test_methodology_version_footer_links_to_the_memo(con):
    text = rr.render(con, 2025)
    assert "Methodology version 1.0" in text and "counting-a-participant.md" in text
    assert "Synthetic data" in text and "registration is not proof that someone played" in text


def test_the_script_reads_only_the_exec_share_and_the_scorecard():
    src = (Path(rr.__file__)).read_text()
    sql = re.findall(r'"[^"]*\bfrom\s+([a-z_]+\.[a-z_]+)', src) + re.findall(r"\bfrom\s+([a-z_]+\.[a-z_]+)", src)
    assert set(sql) <= set(rr.SOURCES), set(sql) - set(rr.SOURCES)
    for banned in ("fct_participant", "dim_participant", "mart_participation", "ground_truth", "share_ops", "share_analyst"):
        assert banned not in " ".join(sql), banned


def test_refuses_a_year_with_no_scorecard(con):
    with pytest.raises(SystemExit):
        rr.render(con, 1999)
