"""The one-page summary of the Data product tab: public/product-summary.html (and, printed, docs/product/one-pager.pdf).

Goals, products, users, plan, privacy, proof and learning on one page. Every number is read from the product-tab exports (roadmap gates, product specs, goal scorecard, health, age funnel, age rules)
at build time and rounded for display; nothing is typed into the template and nothing is computed in the browser. The copy is `summary:` in site_src/copy/charts.yml (status draft until Anna approves it).
`PROVENANCE` records, for each number shown, the export and field it came from; tests/test_one_pager.py checks the page against it. The build fails if a {placeholder} has no value.
"""
from __future__ import annotations

import re
import sys
from html import escape as e
from pathlib import Path

import yaml

from scripts import site_product as sp

ROOT = Path(__file__).resolve().parent.parent
COPY_PATH = ROOT / "site_src" / "copy" / "charts.yml"
SLUG = "product-summary"
PLACEHOLDER = re.compile(r"\{([a-z_0-9]+)\}")
HORIZONS = ["DELIVERED", "NOW", "NEXT", "LATER"]
TIER_AGES = {"U13": 5, "13_15": 14, "16_17": 17, "ADULT": 40}
TYPE_WORD = {"source-based": "Source", "master": "Master", "insights": "Insight"}


def load_copy() -> dict:
    return yaml.safe_load(COPY_PATH.read_text(encoding="utf-8"))["summary"]


def rows_of(data: dict, name: str) -> list[dict]:
    return data[name]["rows"]


def kpi(data: dict, kpi_id: str, segment=None) -> dict:
    hits = [r for r in rows_of(data, "goal_scorecard") if r["kpi_id"] == kpi_id and r["segment"] == segment]
    if len(hits) != 1:
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: the goal scorecard has {len(hits)} rows for {kpi_id}, expected 1")
    return hits[0]


def values(data: dict, n_personas: int) -> tuple[dict, list[dict]]:
    """The display strings for every placeholder, and where each one came from: [{key, file, field, raw, shown}]."""
    prov: list[dict] = []
    out: dict[str, str] = {}

    def put(key: str, shown: str, file: str, field: str, raw) -> None:
        out[key] = shown
        prov.append({"key": key, "file": file, "field": field, "raw": raw, "shown": shown})

    def need(v, what: str):
        if v is None:
            raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: no value for {what}")
        return v

    health = rows_of(data, "product_health")
    pipe = [r for r in health if r["area"] == "pipeline"]
    tests = [r["value_num"] for r in pipe if r["value_num"] is not None]
    if len(tests) < len(pipe):       # a partial dbt run (for example `make product` alone) leaves some products without a recorded run: say so, and use only what was recorded
        print(f"WARNING: one-pager: tests passing read from {len(tests)} of {len(pipe)} products (no run recorded for the rest); run `make all-phases` before publishing", file=sys.stderr)
    need(tests or None, "tests passing")
    put("pct_tests", f"{int(min(tests))}", "product_health", "value_num (pipeline, lowest of the products)", min(tests))
    breaks = [r["value_num"] for r in health if r["area"] == "boundaries"]
    put("n_boundary", f"{int(max(breaks))}", "product_health", "value_num (boundaries, highest of the products)", max(breaks))
    dark = next(r for r in health if r["area"] == "trust" and r["measure"] == "Known leagues that sent no file")
    m = re.fullmatch(r"(\d+) of (\d+)", dark["value_text"])
    if not m:
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: cannot read '{dark['value_text']}' as 'N of M'")
    put("dark_leagues", m.group(1), "product_health", "value_text", dark["value_text"])
    put("known_leagues", m.group(2), "product_health", "value_text", dark["value_text"])

    g = kpi(data, "global_participants")
    put("global_participants", f"{round(need(g['value'], 'participants') / 100) * 100:,}", "goal_scorecard", "value (global_participants)", g["value"])
    c = kpi(data, "countries_with_participants")
    put("n_countries", f"{int(need(c['value'], 'countries')):d}", "goal_scorecard", "value (countries_with_participants)", c["value"])
    gs = kpi(data, "girls_share_of_youth")
    put("girls_share", f"{round(need(gs['value'], 'girls share') * 100):d}", "goal_scorecard", "value (girls_share_of_youth)", gs["value"])
    rt = kpi(data, "retention_one_year")
    put("retention", f"{round(need(rt['value'], 'retention') * 100):d}", "goal_scorecard", "value (retention_one_year)", rt["value"])
    fc = kpi(data, "fans_created_by_flag")
    for key, field in (("fans_created", "value"), ("fans_lo", "value_low"), ("fans_hi", "value_high")):
        put(key, f"{round(need(fc[field], 'fans created') / 100) * 100:,}", "goal_scorecard", f"{field} (fans_created_by_flag)", fc[field])

    step = [r for r in rows_of(data, "conv_tier") if r["age_tier"] == "U13" and r["kind"] == "ACTIVATION"]
    if len(step) != 1:
        raise SystemExit("SITE BUILD REFUSED:\n  one-pager: no activation step for the under-13 tier in the age funnel")
    put("pct_u13_club_consent", f"{round(need(step[0]['share_of_registered'], 'under-13 consent') * 100):d}", "conv_tier", "share_of_registered (under 13, activation step)", step[0]["share_of_registered"])

    road = rows_of(data, "roadmap")
    gated = [r for r in road if r["n_gates"] is not None]
    put("n_met", f"{int(gated[0]['n_met'])}", "roadmap", "n_met", gated[0]["n_met"])
    put("n_gates", f"{int(gated[0]['n_gates'])}", "roadmap", "n_gates", gated[0]["n_gates"])
    mvp = next(r for r in road if r["product_id"] == "DP4" and r["horizon"] == "NOW" and r["gate_id"])
    put("current", f"{round(need(mvp['current_value'], 'MVP gate value'))}", "roadmap", "current_value (the MVP gate)", mvp["current_value"])
    put("target", f"{round(need(mvp['target'], 'MVP gate target'))}", "roadmap", "target (the MVP gate)", mvp["target"])
    put("n_personas", f"{n_personas}", "docs/product/discovery.md", "rows of the persona table", n_personas)
    return out, prov


def fill(text: str, vals: dict) -> str:
    missing = [k for k in PLACEHOLDER.findall(text) if k not in vals]
    if missing:
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: no value for {{{missing[0]}}} in '{text[:60]}'")
    return PLACEHOLDER.sub(lambda m: vals[m.group(1)], text)


def quality_chip(text: str) -> str:
    """A short plain label from the live quality text of a product spec; unknown shapes fail the build instead of showing nothing."""
    if (m := re.match(r"grade ([A-F])\b", text)):
        return f"Grade {m.group(1)}"
    if (m := re.match(r"identity range ([0-9.]+)%", text)):
        return f"{float(m.group(1)):.1f}% range"
    if re.match(r"A \d+, B \d+", text):
        return "A to D"
    raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: cannot make a short quality label from '{text}'")


def who_consents(rules: list[dict], tier: str) -> str:
    rs = [r for r in rules if (r["age_max"] < 18 if tier != "ADULT" else r["age_max"] >= 100) and (tier == "ADULT" or (r["age_min"] <= TIER_AGES[tier] <= r["age_max"]))]
    who = sorted({r["who_consents"] for r in rs})
    if who not in (["GUARDIAN"], ["SELF"]):
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: the age rules disagree on who consents for tier {tier}: {who}")
    return who[0]


def goals_block(c: dict) -> str:
    items = "".join(f"<li><span class='ps-tag'>{e(k)}</span> {e(t)}</li>" for k, t in c["goals"].items())
    return f"<section class='ps-box ps-a'><h2>{e(c['why_heading'])}</h2><ul class='ps-goals'>{items}</ul></section>"


def products_block(c: dict, data: dict) -> str:
    chips = ""
    for p in rows_of(data, "product_specs"):
        if p["id"] not in c["product_names"]:
            raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: no short name for {p['id']} in the summary copy")
        goals = " ".join(f"<span class='ps-tag ps-tag-goal'>{e(x.strip())}</span>" for x in p["goals"].split(","))
        status = f"<span class='ps-chip ps-st-{e(p['status'])}'>{e(sp.STATUS_WORD[p['status']])}</span>"
        chips += (f"<li><span class='ps-pid'>{e(p['id'])}</span> <b>{e(c['product_names'][p['id']])}</b>"
                  f"<span class='ps-chips'><span class='ps-chip'>{e(TYPE_WORD[p['type']])}</span>{status}<span class='ps-chip ps-q'>{e(quality_chip(p['quality_text']))}</span>{goals}</span></li>")
    return f"<section class='ps-box ps-b'><h2>{e(c['what_heading'])}</h2><ol class='ps-products'>{chips}</ol><p class='ps-line'>{e(c['what_line'])}</p></section>"


def personas_block(c: dict) -> str:
    items = ""
    for p in c["personas"]:
        tag = f" <span class='ps-chip ps-supplier'>{e(c['supplier_tag'])}</span>" if p.get("supplier") else ""
        items += f"<li><b>{e(p['role'])}:</b> {e(p['need'])}{tag}</li>"
    return f"<section class='ps-box ps-c'><h2>{e(c['who_heading'])}</h2><ul class='ps-personas'>{items}</ul></section>"


def stages_block(c: dict, vals: dict) -> str:
    items = "".join(f"<li><b>{e(s['label'])}</b><span>{e(fill(s['proof'], vals))}</span></li>" for s in c["stages"])
    return f"<section class='ps-box ps-d'><h2>{e(c['how_heading'])}</h2><ol class='ps-stages'>{items}</ol></section>"


def privacy_block(c: dict, data: dict, vals: dict) -> str:
    rules = rows_of(data, "age_rules")
    segs = ""
    for code, label in c["tiers"].items():
        who = who_consents(rules, code)
        segs += f"<li class='ps-tier ps-tier-{code}'><b>{e(label)}</b><span>{e(c['consents'][who])}</span></li>"
    nots = "".join(f"<li><s>{e(t)}</s></li>" for t in c["not_doing"])
    return (f"<section class='ps-box ps-e'><h2>{e(c['privacy_heading'])}</h2><ol class='ps-tiers'>{segs}</ol><p class='ps-line'>{e(c['tier_note'])}</p>"
            f"<ul class='ps-nots'>{nots}</ul><p class='ps-line'>{e(fill(c['privacy_line'], vals))}</p></section>")


def roadmap_block(c: dict, data: dict, vals: dict) -> str:
    road = rows_of(data, "roadmap")
    head = "".join(f"<span class='ps-lh'>{e(c['lanes'][h])}</span>" for h in HORIZONS)
    lanes = ""
    for p in rows_of(data, "product_specs"):
        cells = ""
        for h in HORIZONS:
            inner = ""
            for r in (x for x in road if x["product_id"] == p["id"] and x["horizon"] == h):
                label = f"{r['version']} {r['title']}"
                inner += f"<span class='ps-dot ps-h-{h.lower()}' role='img' aria-label='{e(label, quote=True)}' title='{e(label, quote=True)}'></span>"
                if r["gate_id"]:
                    met = r["gate_status"] == "MET"
                    text = f"&#10003; {e(c['gate_met'])}" if met else e(c["gate_not_yet"])
                    inner += (f"<span class='ps-gate'><i class='ps-fill' style='width:{float(r['bar_fill_pct']):.0f}%'></i><b class='ps-mark' style='left:{float(r['target_marker_pct']):.0f}%'></b></span>"
                              f"<span class='ps-gs ps-gs-{'met' if met else 'no'}'>{text}</span>")
            cells += f"<span class='ps-cell'>{inner}</span>"
        lanes += f"<div class='ps-lane'><span class='ps-pid'>{e(p['id'])}</span>{cells}</div>"
    return (f"<section class='ps-box ps-f'><h2>{e(c['roadmap_heading'])}</h2><p class='ps-line'>{e(fill(c['roadmap_line'], vals))}</p>"
            f"<div class='ps-lanes'><div class='ps-lane ps-lane-head'><span class='ps-pid'></span>{head}</div>{lanes}</div></section>")


def working_block(c: dict, vals: dict) -> str:
    def tile(parts: list[dict], tag: str | None) -> str:
        body = "".join(f"<span class='ps-kv'><b>{e(fill(p['value'], vals))}</b> <span>{e(fill(p['label'], vals))}</span></span>" for p in parts)
        t = f"<span class='ps-tag'>{e(tag)}</span>" if tag else ""
        return f"<li>{t}{body}</li>"
    goals = "".join(tile(k["parts"], k["tag"]) for k in c["kpis_goals"])
    health = "".join(tile([k], None) for k in c["kpis_health"])
    return f"<section class='ps-box ps-g'><h2>{e(c['working_heading'])}</h2><ul class='ps-kpis'>{goals}</ul><ul class='ps-kpis ps-kpis-health'>{health}</ul></section>"


def learned_block(c: dict) -> str:
    rows = "".join(f"<li><b>{e(c[k + '_label'])}</b> {e(c[k])}</li>" for k in ("pivot", "debt", "next"))
    return f"<section class='ps-box ps-h'><h2>{e(c['learned_heading'])}</h2><ul class='ps-learned'>{rows}</ul></section>"


CSS = """
body.ps{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-body);font-size:14px;line-height:1.3}
.ps *{box-sizing:border-box}
.ps-sheet{max-width:1440px;margin:0 auto;padding:8px 16px 6px;display:grid;gap:8px}
.ps-head h1{font-family:var(--font-display);font-size:28px;line-height:1.05;margin:0;color:var(--text)}
.ps-head p{margin:2px 0 0;color:var(--text-muted);font-size:15px}
.ps-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;align-items:stretch}
.ps-box{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:8px 10px;min-width:0}
.ps-box h2{font-family:var(--font-display);font-size:18px;line-height:1.1;margin:0 0 5px;color:var(--accent);text-transform:none;letter-spacing:.01em}
.ps ul,.ps ol{list-style:none;margin:0;padding:0}
.ps-a{grid-column:1}.ps-b{grid-column:2}.ps-c{grid-column:3}
.ps-left{grid-column:1 / span 2;display:grid;gap:8px;grid-template-rows:auto auto}
.ps-e{grid-column:3}
.ps-g{grid-column:1}.ps-h{grid-column:2 / span 2}
.ps-tag{display:inline-block;font-weight:700;font-size:11px;padding:0 5px;border:1px solid var(--accent);color:var(--accent);border-radius:var(--r-chip);margin-right:3px;white-space:nowrap}
.ps-goals li,.ps-personas li{font-size:15px;padding:5px 0;border-top:1px solid var(--border)}
.ps-goals li:first-child,.ps-personas li:first-child{border-top:0}
.ps-products li{padding:2px 0;border-top:1px solid var(--border)}
.ps-products li:first-child{border-top:0}
.ps-pid{font-weight:700;font-size:11px;color:var(--text-muted);display:inline-block;min-width:30px}
.ps-chips{display:flex;flex-wrap:wrap;gap:3px;margin-top:2px;padding-left:30px}
.ps-chip{display:inline-block;font-size:12px;padding:0 6px;border-radius:999px;border:1px solid var(--border);color:var(--text)}
.ps-st-mvp{border-color:var(--accent);background:var(--accent);color:#fff;font-weight:700}
.ps-st-proposed{border-style:dashed}
.ps-q{border-color:var(--series-sand)}
.ps-supplier{border-style:dashed;color:var(--text-muted);font-style:italic}
.ps-tag-goal{font-weight:500}
.ps-line{margin:6px 0 0;color:var(--text-muted);font-size:13px}
.ps-stages{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}
.ps-stages li{display:grid;gap:1px;align-content:start;border-left:3px solid var(--accent);padding-left:6px}
.ps-stages{counter-reset:st}.ps-stages li{counter-increment:st}.ps-stages li::before{content:counter(st);font-weight:700;font-size:11px;color:var(--text-muted)}
.ps-stages span:last-child{font-size:13px;color:var(--text-muted)}
.ps-tiers{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:2px}
.ps-tier{display:grid;gap:1px;padding:4px 5px;border-top:6px solid var(--series-sky);background:var(--bg);font-size:12px;min-width:0}
.ps-tier span{color:var(--text-muted)}
.ps-tier-13_15{border-top-color:var(--series-turf)}.ps-tier-16_17{border-top-color:var(--series-sand)}.ps-tier-ADULT{border-top-color:var(--series-plum)}
.ps-nots{display:flex;flex-wrap:wrap;gap:3px;margin-top:5px}
.ps-nots li{font-size:12px;border:1px solid var(--series-pylon);border-radius:999px;padding:0 6px;color:var(--text-muted)}
.ps-lanes{display:grid;gap:2px;margin-top:5px}
.ps-lane{display:grid;grid-template-columns:34px repeat(4,minmax(0,1fr));gap:4px;align-items:center;min-height:19px}
.ps-lh{font-size:11px;font-weight:700;color:var(--text-muted)}
.ps-cell{display:flex;align-items:center;gap:3px;flex-wrap:wrap;min-width:0}
.ps-dot{width:13px;height:13px;border-radius:50%;border:2px solid var(--accent);display:inline-block}
.ps-h-delivered{background:var(--accent)}
.ps-h-now{background:var(--line-to-gain);border-color:var(--text)}
.ps-h-next{background:transparent}
.ps-h-later{background:transparent;border-style:dashed;border-color:var(--text-muted)}
.ps-gate{position:relative;display:inline-block;width:56px;height:7px;background:var(--border);border-radius:3px}
.ps-fill{position:absolute;left:0;top:0;bottom:0;background:var(--series-sky);border-radius:3px}
.ps-mark{position:absolute;top:-2px;bottom:-2px;width:2px;background:var(--text)}
.ps-gs{font-size:11px;color:var(--text-muted)}.ps-gs-met{color:var(--accent);font-weight:700}
.ps-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
.ps-kpis+.ps-kpis{margin-top:6px;padding-top:6px;border-top:1px solid var(--border)}
.ps-kpis li{display:grid;gap:1px;align-content:start;justify-items:start}
.ps-kv b{font-family:var(--font-display);font-size:22px;line-height:1;color:var(--text)}
.ps-kv span{font-size:12px;color:var(--text-muted)}
.ps-kv{display:block}.ps-kv b{display:block}
.ps-learned li{padding:7px 0;border-top:1px solid var(--border);font-size:15px}
.ps-learned li:first-child{border-top:0}
.ps-learned b{color:var(--accent);margin-right:4px}
.ps-foot{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:11px;color:var(--text-muted)}
.ps-foot a{color:var(--link)}
@media screen and (max-width:900px){
  .ps-grid{grid-template-columns:minmax(0,1fr)}
  .ps-a,.ps-b,.ps-c,.ps-left,.ps-e,.ps-g,.ps-h{grid-column:1}
  .ps-left{display:contents}
  .ps-stages{grid-template-columns:minmax(0,1fr)}
  .ps-kpis{grid-template-columns:minmax(0,1fr)}
  .ps-a{order:1}.ps-b{order:2}.ps-c{order:3}.ps-d{order:4}.ps-e{order:5}.ps-f{order:6}.ps-g{order:7}.ps-h{order:8}
}
@page{size:letter landscape;margin:.3in}
@media print{
  :root:root{--bg:#fff;--surface:#fff;--text:#1B2733;--text-muted:#4A5866;--border:#D5DBE1;--accent:#2F6B4F;--link:#1F5E8F;color-scheme:light}
  html{zoom:.68}
  body.ps{font-size:13px}
  .ps-sheet{padding:0}
  .ps-box{break-inside:avoid}
}
"""


def render(data: dict, version: str) -> tuple[str, list[dict], dict]:
    """The page, the provenance of every number on it, and the copy block it was built from."""
    c = load_copy()
    n_personas = len(sp.md_table(ROOT / "docs/product/discovery.md")) - 1
    if n_personas != len(c["personas"]):
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: {len(c['personas'])} personas in the copy but {n_personas} in docs/product/discovery.md")
    vals, prov = values(data, n_personas)
    left = f"<div class='ps-left'>{stages_block(c, vals)}{roadmap_block(c, data, vals)}</div>"
    grid = (goals_block(c) + products_block(c, data) + personas_block(c) + left + privacy_block(c, data, vals)
            + working_block(c, vals) + learned_block(c))
    foot = (f"<footer class='ps-foot'><span>{e(c['footer'])}</span><a href='product.html'>{e(c['footer_link'])} &rarr;</a><span>{e(fill(c['methodology'], {'version': str(version)}))}</span></footer>")
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>One-page summary: Flag Football Project</title>
<meta name="description" content="{e(c['pitch'], quote=True)}">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;700&family=Barlow+Condensed:wght@600;700&display=swap">
<link rel="stylesheet" href="css/tokens.css">
<script>try{{var t=localStorage.getItem("cff-theme");if(t==="light"||t==="dark"){{document.documentElement.dataset.theme=t}}}}catch(e){{}}</script>
<style>{CSS}</style>
</head>
<body class="ps">
<main class="ps-sheet" id="main">
<header class="ps-head"><h1>{e(c['title'])}</h1><p>{e(c['pitch'])}</p></header>
<div class="ps-grid">{grid}</div>
{foot}
</main>
</body>
</html>
"""
    return page, prov, c


def copy_strings(c: dict) -> list[tuple[str, str]]:
    """Every copy string in reading order, as (key path, text), for Anna's approval list."""
    out: list[tuple[str, str]] = []

    def walk(prefix: str, v) -> None:
        if isinstance(v, dict):
            for k, x in v.items():
                walk(f"{prefix}.{k}" if prefix else str(k), x)
        elif isinstance(v, list):
            for i, x in enumerate(v, 1):
                walk(f"{prefix}[{i}]", x)
        elif isinstance(v, str):
            out.append((f"summary.{prefix}", v))
    walk("", {k: v for k, v in c.items() if k != "status"})
    return out
