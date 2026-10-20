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
    names = ("roadmap", "product_specs", "goal_scorecard", "product_health", "age_rules", "conv_tier", "product_prioritization")
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
    for r in data["roadmap"]["rows"]:        # the roadmap component prints the cards, gate lines and decisions of the tab as they are
        for k in ("value_text", "status_text", "decision_text", "gate_id", "title", "phase_ref", "version"):
            allowed |= set(NUMBER.findall(r[k] or ""))
    for r in data["product_prioritization"]["rows"]:       # the priorities table prints the confirmed scores and their total
        allowed |= {str(r[k]) for k in ("value_to_goals", "feasibility_today", "data_readiness", "privacy_risk")} | {str(r["value_to_goals"] + r["feasibility_today"] + r["data_readiness"] - r["privacy_risk"])}
    allowed |= {"1", "5"}                    # "Scores 1 to 5", the scale named in the tab's own note
    allowed |= set(NUMBER.findall((ROOT / "docs/product/discovery.md").read_text(encoding="utf-8")))   # the persona cards print discovery.md
    for r in data["product_specs"]["rows"]:
        if (m := re.match(r"identity range ([0-9.]+)%", r["quality_text"])):
            allowed.add(f"{float(m.group(1)):.1f}")
    text = re.sub(r"\b(?:DP|G)\d\b|\bv\d+\.\d+\b", " ", visible(re.sub(r"<svg.*?</svg>", " ", page, flags=re.S)))
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
    assert "summary.pitch" in keys and any(k.startswith("summary.sections.") for k in keys)
    assert yaml.safe_load((ROOT / "site_src/copy/charts.yml").read_text(encoding="utf-8"))["summary"]["title"]


def slides(html: str) -> dict:
    """The viewer slides of product.html: id -> html."""
    out = {}
    for m in re.finditer(r'<script type="application/json" class="vspec" data-kind="html" data-id="([^"]+)"[^>]*>(.*?)</script>', html, flags=re.S):
        out[m.group(1)] = json.loads(m.group(2).replace("<\\/", "</"))["html"]
    return out


def squash(html: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def section(page: str, key: str) -> str:
    return re.search(rf"<section class='ps-sec' id='s-{key}'>(.*?)</section>", page, flags=re.S).group(1)


def tab_and_page():
    ss, data = load()
    tab = ROOT / "public" / "product.html"
    if not tab.exists():
        pytest.skip("no built site")
    page, _p, _c = ss.render(data, "2.0")
    return tab.read_text(encoding="utf-8"), page


def test_the_diagram_is_the_tabs_diagram():
    tab, page = tab_and_page()
    svg = re.search(r"<svg data-diagram='dependencies'.*?</svg>", slides(tab)["D1-2"], flags=re.S).group(0)
    assert svg in page


def test_the_matrix_has_the_tabs_cells():
    tab, page = tab_and_page()
    cells = lambda h: [squash(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", h)]   # noqa: E731
    assert cells(slides(tab)["D1-1"]) == cells(section(page, "matrix")) and cells(section(page, "matrix"))


def test_the_personas_are_the_tabs_personas():
    tab, page = tab_and_page()
    names = lambda h: re.findall(r"<div class='vpersona'><h4>(.*?)</h4><p class='note'>(.*?)</p><p>(.*?)</p>", h)   # noqa: E731
    assert names(slides(tab)["D3-1"]) == names(section(page, "personas")) and len(names(section(page, "personas"))) == 6


def test_the_priorities_are_the_tabs_priorities():
    tab, page = tab_and_page()
    rows = lambda h: [re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r)[1:] for r in re.findall(r"<tbody>(.*?)</tbody>", h, flags=re.S)[0].split("</tr>") if "<td" in r]   # noqa: E731
    tab_rows = [[squash(c) for c in r] for r in rows(slides(tab)["D4-1"])]
    my_rows = [[squash(c) for c in r] for r in rows(section(page, "priorities"))]
    assert my_rows == tab_rows and len(my_rows) == 5


def cards(html: str) -> dict:
    """(product lane, version, title) -> gate line, for every card of a roadmap board."""
    out = {}
    for lane in re.findall(r"<div class='vr-lane.*?(?=<div class='vr-lane|<div class='vr-notdoing')", html, flags=re.S):
        pid = re.search(r"<b>(DP\d)", lane).group(1)
        for m in re.finditer(r"<(?:button|div) [^>]*class='vrcard'[^>]*>(.*?)</(?:button|div)>", lane, flags=re.S):
            body = m.group(1)
            ver = squash(re.search(r"<span class='vrchip'>(.*?)</span>", body).group(1))
            title = squash(re.search(r"<span class='vrtitle'>(.*?)</span>", body).group(1))
            gate = re.search(r"<p class='vgtext'>(.*?)</p>", body, flags=re.S)
            dec = re.search(r"<p class='vdec'>(.*?)</p>", body, flags=re.S)
            out[pid, ver, title] = (squash(gate.group(1)) if gate else "", squash(dec.group(1)) if dec else "")
    return out


def test_every_roadmap_card_gate_and_version_equals_the_product_tab():
    tab, page = tab_and_page()
    mine, theirs = cards(section(page, "roadmap")), cards(tab)
    assert mine and mine == theirs, "the one-pager roadmap is the tab's roadmap, card for card"
