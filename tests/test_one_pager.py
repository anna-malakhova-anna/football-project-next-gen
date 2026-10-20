"""The one-page summary of the Data product tab: every number on it comes from a product-tab export (the build records where), and its copy is a draft until Anna approves it."""
import html as htmllib
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public" / "data"
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def load():
    if not (DATA / "roadmap.json").exists():
        pytest.skip("no built site")
    from scripts import site_summary
    names = ("roadmap", "product_specs", "goal_scorecard", "product_health", "age_rules", "conv_tier")
    return site_summary, {n: json.loads((DATA / f"{n}.json").read_text(encoding="utf-8")) for n in names}


def visible(html: str) -> str:
    html = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.S)
    html = re.sub(r"(title|aria-label)='[^']*'", "", html)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", html)))


def test_every_number_on_the_page_comes_from_a_product_tab_export():
    ss, data = load()
    page, prov, _c = ss.render(data, "2.0")
    for p in prov:
        if p["file"].endswith(".md"):
            continue
        text = (DATA / f"{p['file']}.json").read_text(encoding="utf-8")
        assert json.dumps(p["raw"]) in text or str(p["raw"]) in text, f"{p['key']}: {p['raw']!r} is not in data/{p['file']}.json"
    allowed = {n for p in prov for n in NUMBER.findall(p["shown"])}
    allowed |= {str(r[k]) for r in data["age_rules"]["rows"] for k in ("age_min", "age_max")} | {"18", "2.0"}
    for r in data["roadmap"]["rows"]:        # the roadmap component prints the gate lines and decisions of the tab as they are
        for k in ("value_text", "status_text", "decision_text", "gate_id"):
            allowed |= set(NUMBER.findall(r[k] or ""))
    for r in data["product_specs"]["rows"]:
        if (m := re.match(r"identity range ([0-9.]+)%", r["quality_text"])):
            allowed.add(f"{float(m.group(1)):.1f}")
    text = re.sub(r"\b(?:DP|G)\d\b|\bv\d+\.\d+\b", " ", visible(page))
    stray = [n for n in NUMBER.findall(text) if n.rstrip(",") not in allowed]
    assert not stray, f"numbers with no source: {stray}"


def test_placeholders_must_have_a_value():
    ss, _ = load()
    with pytest.raises(SystemExit):
        ss.fill("{no_such_number}", {})


def test_no_raw_decimals_on_the_page_or_in_the_product_tables():
    ss, data = load()
    page, _p, _c = ss.render(data, "2.0")
    assert not re.search(r"\b0\.\d{3,}", visible(page))
    from scripts import build_site
    for name in ("conv_tier", "goal_scorecard"):
        d = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
        assert not re.search(r"<td>0\.\d{3,}</td>", build_site.table_html(d, 200))


def test_summary_copy_is_draft_until_approved_and_every_string_is_listed():
    ss, _ = load()
    c = ss.load_copy()
    assert c["status"] in ("draft", "final")
    keys = {k for k, _t in ss.copy_strings(c)}
    assert "summary.pitch" in keys and any(k.startswith("summary.personas[") for k in keys)
    assert yaml.safe_load((ROOT / "site_src/copy/charts.yml").read_text(encoding="utf-8"))["summary"]["title"]


def cards(html: str) -> dict:
    """version -> (gate text) of every roadmap card in a page's roadmap component."""
    out = {}
    for m in re.finditer(r"<(?:button|div) [^>]*class='vrcard'[^>]*>(.*?)</(?:button|div)>", html, flags=re.S):
        body = m.group(1)
        ver = re.search(r"<span class='vrchip'>(v[\d.]+)", body).group(1)
        title = re.search(r"<span class='vrtitle'>(.*?)</span>", body).group(1)
        gate = re.search(r"<p class='vgtext'>(.*?)</p>", body, flags=re.S)
        out[ver, title] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", gate.group(1))).strip() if gate else ""
    return out


def test_every_gate_and_version_on_the_one_pager_equals_the_product_tab():
    ss, data = load()
    tab = (ROOT / "public" / "product.html")
    if not tab.exists():
        pytest.skip("no built site")
    page, _p, _c = ss.render(data, "2.0")
    tab_cards = cards(tab.read_text(encoding="utf-8"))
    gate_by_version = {}
    for (ver, _t), g in tab_cards.items():
        gate_by_version.setdefault(ver, set()).add(g)
    mine = cards(page)
    assert mine, "no roadmap cards on the one-pager"
    # a version is shared by several products, so compare the set of gate lines per version on the tab with each card here
    for (ver, _title), g in mine.items():
        assert g in gate_by_version[ver] or g == "", f"{ver}: gate line {g!r} is not on the Data product tab"
    gated_tab = {g for gs in gate_by_version.values() for g in gs if g}
    gated_mine = {g for g in mine.values() if g}
    assert gated_mine == gated_tab, "every gate of the tab is on the one-pager, with the same value"
