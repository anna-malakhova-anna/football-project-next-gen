import collections
import json

import pyarrow.parquet as pq
import pytest

from generator import main, population
from generator.population import build_population
from generator.sources import fan


def load_config():
    """The real configuration (see conftest.py), at a mid size: enough households to see the fan mechanics, small enough for a test."""
    cfg = population.load_config_full()
    cfg["population"]["total_people"] = 6000
    return cfg


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    base = tmp_path_factory.mktemp("gen_fan")
    cfg = load_config()
    res = main.run(cfg, raw_dir=str(base / "raw"), truth_dir=str(base / "truth"))
    out = next(o for o in res["outputs"] if o.source_system == "FAN_ENGAGEMENT")
    return cfg, base, out


def _counts(out):
    return collections.Counter(m["defect_id"] for m in out.manifest)


def _jsonl(base, pattern):
    rows = []
    for f in sorted((base / "raw" / "fan").glob(pattern)):
        for line in f.read_text().splitlines():
            rows.append((f.name, json.loads(line)))
    return rows


def _truth(base, name):
    return pq.read_table(base / "truth" / f"{name}.parquet").to_pylist()


def test_files_layout_and_columns(run):
    cfg, base, out = run
    files = sorted(p.name for p in (base / "raw" / "fan").iterdir())
    years = cfg["seasons"]["years"]
    assert "fan_accounts.csv" in files and "fan_consent_events.jsonl" in files
    events = [f for f in files if f.startswith("events_")]
    assert events[0] == f"events_{years[0]}_01.jsonl" and events[-1] == f"events_{years[-1]}_12.jsonl" and len(events) == 12 * len(years)
    assert any(f.startswith("fan_transactions_") for f in files)
    header = (base / "raw" / "fan" / "fan_accounts.csv").read_text().splitlines()[0]
    assert header == "account_id,email,phone,postal_prefix,country,created_at,acquisition_source,birth_year"
    assert set(_jsonl(base, "events_2023_10.jsonl")[0][1]) == {"event_id", "account_id", "event_type", "event_ts", "value"}
    assert set(_jsonl(base, "fan_consent_events.jsonl")[0][1]) == {"account_id", "channel", "status", "event_ts", "capture_point"}
    assert set(_jsonl(base, "fan_transactions_2023_10.jsonl")[0][1]) == {"txn_id", "account_id", "txn_ts", "category", "amount", "is_refund", "original_txn_id"}
    n = len(_jsonl(base, "events_*.jsonl")) + len(_jsonl(base, "fan_consent_events.jsonl")) + len(_jsonl(base, "fan_transactions_*.jsonl"))
    assert out.n_records == n


def test_event_types_and_values(run):
    _, base, _ = run
    types = {e["event_type"] for _, e in _jsonl(base, "events_*.jsonl")}
    assert types == {"app_open", "content_view", "game_stream", "newsletter_click", "fantasy_activity", "flag_content_view"}
    assert all(e["value"] is None for _, e in _jsonl(base, "events_*.jsonl"))     # purchases are transactions now, not events


def test_defects_are_injected_at_exact_counts(run):
    cfg, base, out = run
    rates, c = cfg["defects"]["fan"], _counts(out)
    accounts = _truth(base, "fan_account_truth")
    n_part = sum(a["is_participant_household"] and not a["is_duplicate_account"] for a in accounts)
    assert c["email_differs_from_registration"] == round(rates["email_differs_from_registration"] * n_part)
    base_accounts = sum(not a["is_duplicate_account"] for a in accounts)
    assert c["duplicate_account"] == round(rates["duplicate_account"] * base_accounts)
    assert sum(a["is_duplicate_account"] for a in accounts) == c["duplicate_account"]
    n_delivered = len(_jsonl(base, "events_*.jsonl")) - c["duplicate_event"]
    assert c["duplicate_event"] == round(rates["duplicate_event"] * n_delivered)
    assert c["clock_skew"] == round(rates["clock_skew"] * n_delivered)
    assert c["late_arriving_event"] == pytest.approx(rates["late_arriving_event"] * n_delivered, rel=0.02)
    txns = _jsonl(base, "fan_transactions_*.jsonl")
    originals = sum(1 for _, t in txns if not t["is_refund"])
    assert c["refund_without_original"] == round(rates["refund_without_original"] * originals)
    assert c["email_case_whitespace"] == round(rates["email_case_whitespace"] * len(accounts))
    assert c["consent_out_of_order"] > 0


def test_refunds_match_an_original_except_the_orphans(run):
    _, base, out = run
    txns = [t for _, t in _jsonl(base, "fan_transactions_*.jsonl")]
    ids = {t["txn_id"]: t for t in txns if not t["is_refund"]}
    assert len(ids) == len([t for t in txns if not t["is_refund"]])
    orphans = [t for t in txns if t["is_refund"] and t["original_txn_id"] not in ids]
    assert len(orphans) == _counts(out)["refund_without_original"]
    for t in txns:
        if t["is_refund"] and t["original_txn_id"] in ids:
            assert ids[t["original_txn_id"]]["amount"] == t["amount"] and ids[t["original_txn_id"]]["account_id"] == t["account_id"]
        assert t["amount"] > 0 and t["category"] in {"ticket", "merch", "subscription", "other"}


def test_consent_is_events_with_no_event_meaning_not_captured(run):
    cfg, base, _ = run
    ev = [e for _, e in _jsonl(base, "fan_consent_events.jsonl")]
    assert {e["status"] for e in ev} == {"opt_in", "opt_out"}
    assert {e["channel"] for e in ev} == {"email", "sms", "push"}
    assert {e["capture_point"] for e in ev} == {"signup", "checkout", "flag_registration", "preference_center"}
    truth = _truth(base, "fan_consent_truth")
    assert {t["final_status"] for t in truth} == {"opt_in", "opt_out", "none"}          # accounts and channels with no event are NONE, never FALSE
    assert len(truth) == 3 * len(_truth(base, "fan_account_truth"))


def test_staggered_rollout_nobody_registers_before_their_markets_launch(run):
    cfg, base, _ = run
    people = _truth(base, "person_registry")
    assert all(p["first_season"] >= p["market_launch_year"] for p in people)
    markets = {m["market_id"]: m for m in fan.markets_mod.build_markets(cfg)["markets"]}
    never = {k for k, m in markets.items() if m["launch_year"] is None}
    assert never and not any(p["home_market_id"] in never for p in people)           # some markets never launch, so nobody there is registered
    assert len({m["launch_year"] for m in markets.values() if m["launch_year"]}) >= 4


def test_acquisition_incremental_accounts_exist_only_for_households_without_an_account_and_follow_the_lift(run):
    cfg, base, _ = run
    hh = [h for h in _truth(base, "fan_truth") if h["is_participant_household"]]
    no_account_before = [h for h in hh if not h["had_account_before"]]
    assert all(h["acq_type"] == "NONE" for h in hh if h["had_account_before"])
    incremental = sum(h["acq_type"] == "INCREMENTAL" for h in no_account_before)
    lift = cfg["sources"]["fan"]["acquisition"]["true_acquisition_lift"]
    assert incremental / len(no_account_before) == pytest.approx(lift, abs=0.04)
    # the market-level truth: programme-caused accounts appear only in market-years where the programme has launched
    mt = _truth(base, "fan_market_truth")
    assert all(r["new_accounts_incremental"] == 0 for r in mt if not r["is_treated"])
    assert sum(r["new_accounts_incremental"] for r in mt) > 0


def test_selection_account_holders_who_enroll_a_child_are_fandom_heavy(run):
    _, base, _ = run
    hh = [h for h in _truth(base, "fan_truth") if h["is_participant_household"]]
    mean = lambda rows: sum(r["latent_fandom"] for r in rows) / len(rows)  # noqa: E731
    assert mean([h for h in hh if h["had_account_before"]]) - mean([h for h in hh if h["acq_type"] == "NONE" and not h["had_account_before"]]) > 0.4
    assert all(0 < h["enrollment_propensity"] < 1 for h in hh)


def test_the_true_uplift_and_reactivation_are_in_the_oracle(run):
    cfg, base, _ = run
    oracle = _truth(base, "fan_effect_truth")
    hh = {h["account_id"]: h for h in _truth(base, "fan_truth") if h["is_participant_household"] and h["account_id"]}
    obs = cf = 0.0
    for r in oracle:
        h = hh[r["account_id"]]
        month_year = cfg["seasons"]["years"][0] + r["month_idx"] // 12
        if month_year > h["first_registration_year"] or (month_year == h["first_registration_year"] and r["month_idx"] % 12 + 1 >= h["enroll_month"]):
            obs += r["expected_events_observed"]
            cf += r["expected_events_no_programme"]
    assert 0.08 < obs / cf - 1 < 0.40            # the uplift while active, decay after churn, and reactivations the programme caused
    assert any(h["reactivation_caused"] for h in hh.values())


def test_status_truth_covers_every_participant_household_and_unknown_is_not_no_account(run):
    _, base, _ = run
    hh = [h for h in _truth(base, "fan_truth") if h["is_participant_household"]]
    assert {h["truth_status"] for h in hh} <= {"EXISTING_ACTIVE", "LAPSED_REACTIVATED", "LAPSED_DORMANT", "NET_NEW", "NO_ACCOUNT", "BORDERLINE"}
    assert all((h["truth_status"] == "NO_ACCOUNT") == (h["account_id"] == "") for h in hh)


def test_duplicate_accounts_share_a_household_and_a_canonical_account(run):
    _, base, _ = run
    ac = {a["account_id"]: a for a in _truth(base, "fan_account_truth")}
    dups = [a for a in ac.values() if a["is_duplicate_account"]]
    assert dups
    for d in dups:
        orig = ac[d["canonical_account_id"]]
        assert orig["household_key"] == d["household_key"] and not orig["is_duplicate_account"]


def test_generation_is_deterministic():
    cfg = load_config()
    cfg["population"]["total_people"] = 1500
    people, parts = build_population(cfg)
    a = fan.generate(people, parts, cfg)
    people, parts = build_population(cfg)
    b = fan.generate(people, parts, cfg)
    assert a.files["fan/fan_accounts.csv"] == b.files["fan/fan_accounts.csv"]
    assert a.files["fan/fan_consent_events.jsonl"] == b.files["fan/fan_consent_events.jsonl"]
    k = "fan/events_2023_10.jsonl"
    assert a.files[k] == b.files[k] and a.manifest == b.manifest
    t = [k for k in a.files if k.startswith("fan/fan_transactions_")][5]
    assert a.files[t] == b.files[t]
