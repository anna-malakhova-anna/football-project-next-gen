import json
from pathlib import Path

import duckdb
import pytest
import yaml

from scripts import validate_contracts as vc

ROOT = Path(__file__).resolve().parent.parent


def contract(**over):
    base = {
        "source_system": "T", "version": "1.0.0", "effective_date": "2026-01-01", "owner_role": "r", "partner_type": "p",
        "delivery": {"format": "CSV", "mechanism": "m", "cadence": "c"}, "grain": "g",
        "raw": {"table": "raw.t", "row_filter": None}, "primary_key": ["id"],
        "person_identifier": {"quality": "none", "field": None, "note": ""}, "minors_present": True,
        "consent_fields": [{"column": "photo", "permits": "photos", "allowed_values": ["Y", "N", ""]}],
        "schema": [
            {"column": "id", "raw": "id", "type": "string", "required": True, "pii": "quasi"},
            {"column": "email", "raw": "email", "type": "string", "required": True, "pii": "direct"},
            {"column": "team", "raw": "team", "type": "string", "required": True, "pii": "none"},
            {"column": "photo", "raw": "photo", "type": "boolean", "required": True, "pii": "none"},
        ],
        "quality": [],
    }
    base.update(over)
    return base


def db(rows, columns=("id", "email", "team", "photo")):
    con = duckdb.connect()
    con.execute("create schema raw")
    con.execute(f"create table raw.t ({', '.join(c + ' varchar' for c in columns)}, _source_file varchar)")
    for r in rows:
        con.execute(f"insert into raw.t values ({', '.join('?' for _ in range(len(columns) + 1))})", [*r, "f.csv"])
    return con


def by_rule(results, rule, column=None):
    return [r for r in results if r["rule"] == rule and (column is None or r["column_name"] == column)]


GOOD = [("1", "a@x.com", "t1", "Y"), ("2", "b@x.com", "t2", "N"), ("3", "c@x.com", "t3", "")]


def test_a_clean_table_passes_everything():
    res = vc.evaluate(db(GOOD), contract())
    assert {r["status"] for r in res} == {"PASS"}


def test_threshold_breach_is_a_warn_by_default_and_an_error_when_marked():
    rows = GOOD + [("4", "", "t4", "Y")]                               # 1 of 4 emails blank = 0.25
    warn = vc.evaluate(db(rows), contract(quality=[{"rule": "max_null_rate", "column": "email", "threshold": 0.1}]))
    r = by_rule(warn, "max_null_rate")[0]
    assert (r["status"], r["severity"], round(r["observed"], 2)) == ("WARN", "WARN", 0.25)
    err = vc.evaluate(db(rows), contract(quality=[{"rule": "max_null_rate", "column": "email", "threshold": 0.1, "severity": "ERROR"}]))
    assert by_rule(err, "max_null_rate")[0]["status"] == "ERROR"
    ok = vc.evaluate(db(rows), contract(quality=[{"rule": "max_null_rate", "column": "email", "threshold": 0.25}]))
    assert by_rule(ok, "max_null_rate")[0]["status"] == "PASS"          # exactly at the threshold is allowed


def test_a_missing_consent_column_is_an_error():
    res = vc.evaluate(db([("1", "a@x.com", "t")], columns=("id", "email", "team")), contract())
    r = by_rule(res, "column_present", "photo")[0]
    assert r["status"] == "ERROR"


def test_a_missing_pii_column_is_an_error_but_a_missing_plain_column_is_a_warn():
    no_email = vc.evaluate(db([("1", "t", "Y")], columns=("id", "team", "photo")), contract())
    assert by_rule(no_email, "column_present", "email")[0]["status"] == "ERROR"
    no_team = vc.evaluate(db([("1", "a@x.com", "Y")], columns=("id", "email", "photo")), contract())
    assert by_rule(no_team, "column_present", "team")[0]["status"] == "WARN"


def test_an_unexpected_consent_value_is_an_error_blank_is_not():
    bad = vc.evaluate(db(GOOD + [("4", "d@x.com", "t", "Maybe")]), contract())
    assert by_rule(bad, "consent_values")[0]["status"] == "ERROR"
    assert by_rule(vc.evaluate(db(GOOD), contract()), "consent_values")[0]["status"] == "PASS"      # '' is allowed: not captured


def test_an_undeclared_raw_column_is_an_error():
    res = vc.evaluate(db([("1", "a@x.com", "t", "Y", "secret")], columns=("id", "email", "team", "photo", "ssn")), contract())
    r = by_rule(res, "undeclared_column", "ssn")[0]
    assert r["status"] == "ERROR" and "PII class is unknown" in r["detail"]
    assert not any(x["column_name"] == "_source_file" for x in by_rule(res, "undeclared_column"))        # lineage columns are exempt


def test_nonmatching_invalid_and_duplicate_rates():
    rows = [("1", "a", "t", "Y"), ("1", "b", "t", "Y"), ("3", "c", "bad", "N"), ("4", "d", "t", "N")]
    quality = [{"rule": "max_duplicate_rate", "key": ["id"], "threshold": 0.0},
               {"rule": "max_invalid_rate", "column": "team", "allowed_values": ["t"], "threshold": 0.0},
               {"rule": "max_nonmatching_rate", "column": "id", "pattern": "^[0-3]$", "threshold": 0.0}]
    res = vc.evaluate(db(rows), contract(quality=quality))
    assert round(by_rule(res, "max_duplicate_rate")[0]["observed"], 2) == 0.25
    assert round(by_rule(res, "max_invalid_rate")[0]["observed"], 2) == 0.25
    assert round(by_rule(res, "max_nonmatching_rate")[0]["observed"], 2) == 0.25
    assert all(by_rule(res, r)[0]["status"] == "WARN" for r in ("max_duplicate_rate", "max_invalid_rate", "max_nonmatching_rate"))


def test_a_cross_column_expression_rate_catches_rows_that_break_the_arithmetic():
    rows = [("1", "10", "4", "6"), ("2", "10", "4", "5"), ("3", "20", "10", "10"), ("4", None, "1", "1")]       # id, email=total, team=girls, photo=boys
    q_ = [{"rule": "max_expression_rate", "name": "total_equals_girls_plus_boys", "threshold": 0.1,
           "expression": "try_cast(email as integer) <> try_cast(team as integer) + try_cast(photo as integer)"}]
    res = vc.evaluate(db(rows), contract(quality=q_, consent_fields=contract()["consent_fields"]))
    r = by_rule(res, "max_expression_rate")[0]
    assert r["column_name"] == "total_equals_girls_plus_boys" and r["observed"] == 0.25 and r["status"] == "WARN"   # a NULL total is not a violation


def test_blank_values_belong_to_the_null_rule_not_the_invalid_rule():
    rows = [("1", "a", "t", "Y"), ("2", "b", "", "Y")]
    res = vc.evaluate(db(rows), contract(quality=[{"rule": "max_invalid_rate", "column": "team", "allowed_values": ["t"], "threshold": 0.0}]))
    assert by_rule(res, "max_invalid_rate")[0]["observed"] == 0.0


def test_the_row_filter_excludes_junk_rows():
    rows = [("Player ID", "x", "x", "x"), ("1", "a@x.com", "t", "Y"), ("Total: 1", None, None, None)]
    c = contract(raw={"table": "raw.t", "row_filter": "email is not null and id <> 'Player ID'"},
                 quality=[{"rule": "max_null_rate", "column": "team", "threshold": 0.0}])
    assert by_rule(vc.evaluate(db(rows), c), "max_null_rate")[0]["observed"] == 0.0


def test_a_missing_raw_table_is_an_error():
    con = duckdb.connect()
    con.execute("create schema raw")
    res = vc.evaluate(con, contract())
    assert res[0]["rule"] == "raw_table_present" and res[0]["status"] == "ERROR"


def _json_db(records):
    con = duckdb.connect()
    con.execute("create schema raw")
    con.execute("create table raw.t (record_json json, _page int, _source_file varchar)")
    for r in records:
        con.execute("insert into raw.t values (?, 1, 'p.json')", [json.dumps(r)])
    return con


def _json_contract():
    return contract(
        schema=[{"column": "id", "raw": "$.id", "type": "string", "required": True, "pii": "quasi"},
                {"column": "consents.photo", "raw": "$.consents.photo", "type": "boolean", "required": True, "pii": "none"}],
        consent_fields=[{"column": "$.consents.photo", "permits": "photos", "allowed_values": ["true", "false"]}],
        quality=[{"rule": "max_null_rate", "column": "consents.photo", "threshold": 0.1}], primary_key=["$.id"])


def test_json_sources_missing_object_is_a_null_warn_but_a_never_present_consent_path_is_an_error():
    some = [{"id": "1", "consents": {"photo": True}}, {"id": "2"}]               # one record lacks the consents object
    res = vc.evaluate(_json_db(some), _json_contract())
    assert by_rule(res, "column_present", "consents.photo")[0]["status"] == "PASS"
    assert by_rule(res, "max_null_rate", "consents.photo")[0]["status"] == "WARN"
    none = [{"id": "1"}, {"id": "2"}]                                             # the consent path never appears
    res = vc.evaluate(_json_db(none), _json_contract())
    assert by_rule(res, "column_present", "consents.photo")[0]["status"] == "ERROR"


def test_json_undeclared_key_is_an_error():
    res = vc.evaluate(_json_db([{"id": "1", "consents": {"photo": True}, "ssn": "x"}]), _json_contract())
    assert by_rule(res, "undeclared_column", "$.ssn")[0]["status"] == "ERROR"


def test_every_real_contract_is_well_formed_and_matches_its_file_name():
    paths = [p for p in sorted((ROOT / "contracts").glob("*.yml")) if not p.name.startswith("_")]
    assert {p.stem for p in paths} >= {"US_LEAGUE", "CA_CLUB", "INTL_FED"}
    for p in paths:
        c = vc.load_contract(p)
        assert str(c["version"]).count(".") == 2 and str(c["effective_date"]) and isinstance(c["consent_fields"], list)
        assert c["consent_fields"] or c.get("consent_exempt_reason"), f"{p.name}: declare the consent fields, or say why there are none (consent_exempt_reason)"
        assert all(col["pii"] in vc.PII for col in c["schema"])


def test_an_expression_rule_without_a_name_or_expression_is_rejected(tmp_path):
    bad = contract(quality=[{"rule": "max_expression_rate", "threshold": 0.1}])
    (tmp_path / "T.yml").write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="max_expression_rate needs"):
        vc.load_contract(tmp_path / "T.yml")


def test_malformed_contracts_are_rejected(tmp_path):
    (tmp_path / "T.yml").write_text(yaml.safe_dump({k: v for k, v in contract().items() if k != "consent_fields"}))
    with pytest.raises(ValueError, match="missing contract fields"):
        vc.load_contract(tmp_path / "T.yml")
    (tmp_path / "X.yml").write_text(yaml.safe_dump(contract()))
    with pytest.raises(ValueError, match="does not match the file name"):
        vc.load_contract(tmp_path / "X.yml")
    bad = contract()
    bad["schema"][0]["pii"] = "maybe"
    (tmp_path / "T.yml").write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="pii"):
        vc.load_contract(tmp_path / "T.yml")


def test_results_are_written_with_a_run_time(tmp_path):
    path = tmp_path / "w.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create schema raw; create table raw.t (id varchar, email varchar, team varchar, photo varchar, _source_file varchar)")
    con.execute("insert into raw.t values ('1', 'a@x.com', 't', 'Y', 'f')")
    con.close()
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts" / "T.yml").write_text(yaml.safe_dump(contract()))
    vc.validate(tmp_path / "contracts", path, write=True)
    con = duckdb.connect(str(path), read_only=True)
    rows = con.execute("select source_system, status, run_at is not null from quality.dq_contract_results").fetchall()
    assert rows and all(r[0] == "T" and r[2] for r in rows)


def test_a_contract_split_into_components_must_declare_its_component(tmp_path):
    ok = contract(); ok["source_system"] = "T"; ok["component"] = "events"
    (tmp_path / "T__events.yml").write_text(yaml.safe_dump(ok))
    assert vc.load_contract(tmp_path / "T__events.yml")["component"] == "events"
    bad = dict(ok); bad.pop("component")
    (tmp_path / "T__accounts.yml").write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="must declare `component: accounts`"):
        vc.load_contract(tmp_path / "T__accounts.yml")
    wrong = dict(ok); wrong["source_system"] = "OTHER"
    (tmp_path / "T__other.yml").write_text(yaml.safe_dump(wrong))
    with pytest.raises(ValueError, match="does not match the file name"):
        vc.load_contract(tmp_path / "T__other.yml")
