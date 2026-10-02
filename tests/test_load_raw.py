import csv
import json
import re

import duckdb
import pytest
from openpyxl import load_workbook

from generator import export_config_seed as ecs
from generator import main
from generator.population import load_config
from loader import load_raw


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    base = tmp_path_factory.mktemp("load")
    cfg = load_config()
    main.run(cfg, raw_dir=str(base / "raw"), truth_dir=str(base / "truth"))
    counts = load_raw.load(raw_dir=str(base / "raw"), db_path=str(base / "flag.duckdb"), cfg=cfg)
    return base, counts


def _q(base, sql):
    con = duckdb.connect(str(base / "flag.duckdb"), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_row_counts_match_files(loaded):
    base, counts = loaded
    raw = base / "raw"
    us = sum(sum(1 for _ in csv.reader(open(f, encoding="utf-8"))) - 1 for f in (raw / "us_league").glob("*.csv"))
    ca = sum(len(json.loads(f.read_text(encoding="utf-8"))["records"]) for f in (raw / "ca_club").glob("*.json"))
    intl = sum(ws.max_row for f in (raw / "intl").glob("*.xlsx") for ws in load_workbook(f))
    school = sum(sum(1 for _ in csv.reader(open(f, encoding="utf-8"))) - 1 for f in (raw / "school").glob("*.csv"))
    fan_acc = sum(1 for _ in csv.reader(open(raw / "fan" / "fan_accounts.csv", encoding="utf-8"))) - 1
    fan_ev = sum(sum(1 for _ in open(f, encoding="utf-8")) for f in (raw / "fan").glob("events_*.jsonl"))
    fan_consent = sum(1 for _ in open(raw / "fan" / "fan_consent_events.jsonl", encoding="utf-8"))
    fan_txn = sum(sum(1 for _ in open(f, encoding="utf-8")) for f in (raw / "fan").glob("fan_transactions_*.jsonl"))
    assert counts == {"us_league_registrations": us, "ca_club_records": ca, "intl_federation_returns": intl, "school_headcounts": school,
                      "fan_accounts": fan_acc, "fan_events": fan_ev, "fan_consent_events": fan_consent, "fan_transactions": fan_txn}


def test_only_the_three_raw_tables_and_no_ground_truth(loaded):
    base, _ = loaded
    tables = {r[0] for r in _q(base, "select table_name from information_schema.tables where table_schema='raw'")}
    assert tables == set(load_raw.RAW_TABLES)
    cols = {r[0].lower() for r in _q(base, "select column_name from information_schema.columns where table_schema='raw'")}
    assert not {c for c in cols if "true_person" in c or "truth" in c}
    # no ground-truth id (P-000123 / H-00012) appears in any raw cell
    pat = r"\bP-\d{6}\b|\bH-\d{5}\b"
    for t in load_raw.RAW_TABLES:
        n = _q(base, f"select count(*) from raw.{t} t where regexp_matches(cast(t as varchar), '{pat}')")[0][0]
        assert n == 0, t


def test_everything_lands_as_varchar_except_metadata(loaded):
    base, _ = loaded
    types = {(t, c): d for t, c, d in _q(base, "select table_name, column_name, data_type from information_schema.columns where table_schema='raw'")}
    for (t, c), d in types.items():
        if c.startswith("_"):
            assert d in {"VARCHAR", "INTEGER", "TIMESTAMP"}
        elif t in ("ca_club_records", "fan_events", "fan_consent_events", "fan_transactions"):
            assert d == "JSON"
        else:
            assert d == "VARCHAR", (t, c)


def test_us_values_are_mirrored_exactly(loaded):
    base, _ = loaded
    f = base / "raw" / "us_league" / "registrations_spring_2024.csv"
    with open(f, newline="", encoding="utf-8") as fh:
        want = list(csv.DictReader(fh))
    got = _q(base, "select * exclude (_loaded_at) from raw.us_league_registrations where _source_file='us_league/registrations_spring_2024.csv' order by _row_number")
    cols = [d[0] for d in duckdb.connect(str(base / "flag.duckdb"), read_only=True).execute(
        "select * exclude (_loaded_at) from raw.us_league_registrations limit 0").description]
    assert len(got) == len(want)
    for g, w in zip(got, want):
        rec = dict(zip(cols, g))
        assert all(rec[k] == v for k, v in w.items())  # incl. '' staying '' and '07302'-style zips
    assert [g[cols.index("_row_number")] for g in got] == list(range(1, len(want) + 1))
    assert _q(base, "select count(*) from raw.us_league_registrations where player_gender = ''")[0][0] > 0
    assert _q(base, "select count(*) from raw.us_league_registrations where player_gender is null")[0][0] == 0


def test_ca_json_kept_whole(loaded):
    base, _ = loaded
    page = json.loads((base / "raw" / "ca_club" / "page_0001.json").read_text(encoding="utf-8"))
    got = _q(base, "select record_json::varchar, _page from raw.ca_club_records where _source_file='ca_club/page_0001.json'")
    assert [json.loads(g[0]) for g in got] == page["records"]
    assert {g[1] for g in got} == {1}
    assert _q(base, "select count(*) from raw.ca_club_records where (record_json->'consents') is null")[0][0] > 0


def test_intl_rows_incl_junk_and_serials_kept_raw(loaded):
    base, _ = loaded
    cfg = load_config()
    years, sc = len(cfg["seasons"]["years"]), cfg["sources"]["intl"]
    # title row, blank row, header row and summary row are all present as-is
    assert _q(base, "select c1 from raw.intl_federation_returns where _sheet_name='Germany' and _excel_row=1 and _source_file like '%2024%'")[0][0].startswith("Federation Return")
    germany_years = sum(1 for y in cfg["seasons"]["years"] if y >= int(cfg["markets"]["intl_launch_years"]["DE"]))      # a sheet exists only from the market's launch year
    assert _q(base, "select count(*) from raw.intl_federation_returns where _sheet_name='Germany' and _excel_row=2 and c1 is null and c9 is null")[0][0] == germany_years
    assert _q(base, "select count(*) from raw.intl_federation_returns where c1 = 'Player ID'")[0][0] == ecs._structural_count(cfg, "junk_header_row")   # one header row per country sheet
    assert _q(base, "select count(*) from raw.intl_federation_returns where c1 like 'Total: %'")[0][0] == ecs._structural_count(cfg, "junk_summary_row")
    serials = _q(base, "select c3 from raw.intl_federation_returns where _sheet_name='United Kingdom' and regexp_matches(c3, '^[0-9]+$')")
    assert serials and all(re.fullmatch(r"\d{5}", s[0]) for s in serials)


def test_load_is_idempotent(loaded):
    base, counts = loaded
    again = load_raw.load(raw_dir=str(base / "raw"), db_path=str(base / "flag.duckdb"), cfg=load_config())
    assert again == counts
