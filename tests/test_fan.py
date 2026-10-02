import collections
import json
import math

import pyarrow.parquet as pq
import pytest

from generator import main, population
from generator.population import build_population
from generator.sources import fan

load_config = population.load_config_full       # the real, full-size configuration (see conftest.py)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    base = tmp_path_factory.mktemp("gen_fan")
    cfg = load_config()
    res = main.run(cfg, raw_dir=str(base / "raw"), truth_dir=str(base / "truth"))
    out = next(o for o in res["outputs"] if o.source_system == "FAN_ENGAGEMENT")
    return cfg, base, out


def _counts(out):
    return collections.Counter(m["defect_id"] for m in out.manifest)


def _events(base):
    rows = []
    for f in sorted((base / "raw" / "fan").glob("events_*.jsonl")):
        for line in f.read_text().splitlines():
            rows.append((f.name, json.loads(line)))
    return rows


def test_files_one_per_delivery_month_and_an_accounts_snapshot(run):
    cfg, base, out = run
    files = sorted(p.name for p in (base / "raw" / "fan").iterdir())
    years = cfg["seasons"]["years"]
    assert "fan_accounts.csv" in files
    months = [f for f in files if f.startswith("events_")]
    assert months[0] == f"events_{years[0]}_01.jsonl" and months[-1] == f"events_{years[-1]}_12.jsonl" and len(months) == 12 * len(years)
    first = json.loads((base / "raw" / "fan" / months[0]).read_text().splitlines()[0])
    assert set(first) == {"event_id", "account_id", "event_type", "event_ts", "value"}
    assert out.n_records == len(_events(base))


def test_household_counts_follow_the_config(run):
    cfg, base, _ = run
    t = pq.read_table(base / "truth" / "fan_truth.parquet").to_pylist()
    part = [r for r in t if r["is_participant_household"]]
    non = [r for r in t if not r["is_participant_household"]]
    fc = cfg["sources"]["fan"]
    assert len(non) == round(fc["non_participant_household_multiple"] * len(part))
    assert sum(1 for r in part if r["account_id"]) == round(fc["participant_account_share"] * len(part))
    assert all(r["account_id"] for r in non)


def test_defects_are_injected_at_exact_counts(run):
    cfg, base, out = run
    rates, c = cfg["defects"]["fan"], _counts(out)
    accounts = pq.read_table(base / "truth" / "fan_account_truth.parquet").to_pylist()
    n_part_acc = sum(a["is_participant_household"] for a in accounts)
    assert c["email_differs_from_registration"] == round(rates["email_differs_from_registration"] * n_part_acc)
    n_delivered = out.n_records - c["duplicate_event"]
    assert c["duplicate_event"] == round(rates["duplicate_event"] * n_delivered)
    assert c["clock_skew"] == round(rates["clock_skew"] * n_delivered)
    assert c["late_arriving_event"] == pytest.approx(rates["late_arriving_event"] * n_delivered, rel=0.01)
    assert c["email_case_whitespace"] == round(rates["email_case_whitespace"] * len(accounts))


def test_duplicates_share_an_event_id_and_late_events_keep_their_true_month(run):
    _, base, out = run
    rows = _events(base)
    ids = collections.Counter(e["event_id"] for _, e in rows)
    assert sum(n - 1 for n in ids.values()) == _counts(out)["duplicate_event"]
    late = {m["source_record_id"] for m in out.manifest if m["defect_id"] == "late_arriving_event"}
    skewed = {m["source_record_id"] for m in out.manifest if m["defect_id"] == "clock_skew"}
    in_later_file = 0
    for fname, e in rows:
        if e["event_id"] in late and e["event_id"] not in skewed:
            file_month = fname[len("events_"):-len(".jsonl")].replace("_", "-")
            assert e["event_ts"][:7] < file_month               # delivered after the month it happened in
            in_later_file += 1
    assert in_later_file > 0


def test_selection_participant_households_have_higher_latent_fandom(run):
    _, base, _ = run
    t = pq.read_table(base / "truth" / "fan_truth.parquet").to_pylist()
    mean = lambda rows: sum(r["latent_fandom"] for r in rows) / len(rows)  # noqa: E731
    part = [r for r in t if r["is_participant_household"]]
    non = [r for r in t if not r["is_participant_household"]]
    assert mean(part) - mean(non) > 0.3
    assert all(0 < r["enrollment_propensity"] < 1 for r in t)


def test_the_true_uplift_is_in_the_data_after_enrollment(run):
    cfg, base, _ = run
    t = {r["account_id"]: r for r in pq.read_table(base / "truth" / "fan_truth.parquet").to_pylist() if r["account_id"]}
    y0 = cfg["seasons"]["years"][0]
    # treated accounts enrolling after the first year: events per month before vs after enrollment, relative to non-participants in the same calendar months
    per = collections.defaultdict(lambda: collections.Counter())
    for _, e in _events(base):
        y, m = int(e["event_ts"][:4]), int(e["event_ts"][5:7])
        per[e["account_id"]][(y - y0) * 12 + m - 1] += 1
    n_months = len(cfg["seasons"]["years"]) * 12
    ctl = [0.0] * n_months
    n_ctl = sum(1 for r in t.values() if not r["is_participant_household"])
    for acc, r in t.items():
        if not r["is_participant_household"]:
            for k, v in per[acc].items():
                ctl[k] += v
    ctl = [v / n_ctl for v in ctl]
    ratio_after, ratio_before = [], []
    for acc, r in t.items():
        if r["is_participant_household"] and r["first_registration_year"] > y0:
            e0 = (r["first_registration_year"] - y0) * 12 + r["enroll_month"] - 1
            end = (r["last_active_year"] - y0) * 12 + 11
            before = sum(per[acc][k] for k in range(0, e0))
            after = sum(per[acc][k] for k in range(e0, end + 1))
            ratio_before.append((before, sum(ctl[k] for k in range(0, e0))))
            ratio_after.append((after, sum(ctl[k] for k in range(e0, end + 1))))
    rel = lambda pairs: sum(a for a, _ in pairs) / sum(b for _, b in pairs)  # noqa: E731
    assert rel(ratio_after) / rel(ratio_before) == pytest.approx(1 + cfg["sources"]["fan"]["true_uplift"], abs=0.08)


def test_generation_is_deterministic():
    cfg = load_config()
    people, parts = build_population(cfg)
    a = fan.generate(people, parts, cfg)
    people, parts = build_population(cfg)
    b = fan.generate(people, parts, cfg)
    assert a.files["fan/fan_accounts.csv"] == b.files["fan/fan_accounts.csv"]
    k = "fan/events_2023_10.jsonl"
    assert a.files[k] == b.files[k] and a.manifest == b.manifest
