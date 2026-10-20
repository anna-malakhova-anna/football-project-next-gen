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
    put("year", f"{int(need(g['year'], 'scorecard year'))}", "goal_scorecard", "year", g["year"])
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


def hero_block(c: dict) -> str:
    tiles = "".join(f"<div class='ps-goal'><b>{e(g['head'])}</b><span>{e(g['text'])}</span></div>" for g in c["goals"].values())
    return f"<section class='ps-hero'><div><h1>{e(c['title'])}</h1><p>{e(c['pitch'])}</p></div><div class='ps-goals'>{tiles}</div></section>"


def roadmap_block(c: dict, data: dict, vals: dict) -> str:
    """The roadmap component of the Data product tab (site_product.roadmap_board_html), static: same rows, same gate markup, no viewer."""
    ps = sp.products()
    spec = {r["id"]: r for r in rows_of(data, "product_specs")}
    notes = {}
    for pid, p in ps.items():
        extra = " · MVP" if p["status"] == "mvp" else ""
        notes[pid] = f"{', '.join(p['goals'])}{extra} · {quality_chip(spec[pid]['quality_text'])}"
    static = {"names": c["product_names"], "notes": notes, "subs": c["lane_subs"], "titles": c["roadmap_titles"], "pivot": c["pivot"]}
    board = sp.roadmap_board_html(rows_of(data, "roadmap"), ps, {}, {}, static=static)
    return f"<section><div class='ps-st'><h2>{e(c['roadmap_heading'])}</h2><span>{e(fill(c['roadmap_line'], vals))}</span></div>{board}</section>"


def privacy_block(c: dict, data: dict, vals: dict) -> str:
    rules = rows_of(data, "age_rules")
    segs = ""
    for i, (code, label) in enumerate(c["tiers"].items(), 1):
        who = who_consents(rules, code)
        segs += f"<div class='ps-tier ps-t{i}'><b>{e(label)}</b><span>{e(c['consents'][who])}</span></div>"
    nots = "".join(f"<span class='ps-chip'><s>{e(t)}</s></span>" for t in c["not_doing"])
    return (f"<div class='ps-panel'><div class='ps-st'><h2>{e(c['privacy_heading'])}</h2><span>{e(c['tier_note'])}</span></div><div class='ps-tiers'>{segs}</div>"
            f"<div class='ps-chips'>{nots}</div><p class='ps-note'>{e(fill(c['privacy_line'], vals))}</p></div>")


def working_block(c: dict, vals: dict) -> str:
    kpis = "".join(f"<div class='ps-kpi'><div class='g'>{e(k['tag'])}</div><div class='n'>{e(fill(k['value'], vals))}</div><div class='l'>{e(fill(k['label'], vals))}</div></div>" for k in c["kpis_goals"])
    health = "".join(f"<span><b>{e(fill(h['value'], vals))}</b> {e(h['label'])}</span>" for h in c["health"])
    return (f"<div class='ps-panel'><div class='ps-st'><h2>{e(c['working_heading'])}</h2><span>{e(fill(c['working_sub'], vals))}</span></div>"
            f"<div class='ps-kpis'>{kpis}</div><div class='ps-health'>{health}</div></div>")


def learned_block(c: dict) -> str:
    users = "".join(f"<span class='ps-user{' ps-sup' if p.get('supplier') else ''}'>{e(p['role'])}{' · ' + e(c['supplier_tag']) if p.get('supplier') else ''}</span>" for p in c["personas"])
    return (f"<div class='ps-panel ps-learn'><div class='ps-st'><h2>{e(c['learned_heading'])}</h2></div><p><b>{e(c['debt_label'])}</b> {e(c['debt'])}</p>"
            f"<p><b>{e(c['next_label'])}</b> {e(c['next'])}</p><div class='ps-users'>{users}</div></div>")


CSS = """
body.ps{margin:0;background:var(--bg);color:var(--text);font:13px/1.4 var(--font-body)}
.ps *{box-sizing:border-box}
.ps-page{max-width:1400px;margin:0 auto;padding:16px 16px 14px;display:flex;flex-direction:column;gap:12px}
.ps-hero{background:var(--night-field);color:#fff;border-radius:12px;padding:16px 20px;display:grid;grid-template-columns:1.1fr 2fr;gap:20px;align-items:center}
.ps-hero h1{font-family:var(--font-display);font-size:32px;line-height:1.05;margin:0}
.ps-hero p{margin:6px 0 0;color:#B9C6DC;font-size:13.5px}
.ps-goals{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.ps-goal{background:rgba(255,255,255,.1);border-radius:9px;padding:10px 12px}
.ps-goal b{display:block;font-family:var(--font-display);font-size:20px;letter-spacing:.02em}
.ps-goal span{color:#B9C6DC;font-size:12.5px}
.ps-st{display:flex;align-items:baseline;gap:10px;margin:0 0 6px;flex-wrap:wrap}
.ps-st h2{font-family:var(--font-display);font-size:20px;margin:0;color:var(--text)}
.ps-st span{color:var(--text-muted);font-size:12.5px}
.vroad-static{font-size:.75rem}
.vroad-static .vr-head,.vroad-static .vr-lane{grid-template-columns:170px repeat(4,minmax(0,1fr))}
.vroad-static .vr-colhead{font-size:.8125rem}
.vroad-static .vr-colhead small{display:block;text-transform:none;letter-spacing:0;font-weight:400;font-size:.6875rem}
.vroad-static .vrcard{cursor:default}
.ps-bottom{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:12px}
.ps-panel{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.ps-tiers{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin:4px 0 8px}
.ps-tier{border-radius:6px;padding:7px 8px;color:#fff}
.ps-tier b{display:block;font-size:13px}.ps-tier span{font-size:11px}
.ps-t1{background:#1f4e79}.ps-t2{background:#2d6a9a}.ps-t3{background:#3b76a6}.ps-t4{background:#59626d}
.ps-chips{display:flex;flex-wrap:wrap;gap:5px}
.ps-chip{display:inline-flex;gap:4px;border:1px solid var(--border);border-radius:999px;padding:2px 8px;font-size:11px;color:var(--text-muted)}
.ps-chip::before{content:"\2298";text-decoration:none;color:#C0392B;font-weight:700}
.ps-note{font-size:11.5px;color:var(--text-muted);margin:7px 0 0}
.ps-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.ps-kpi .n{font-family:var(--font-display);font-size:28px;font-weight:700;line-height:1}
.ps-kpi .l{font-size:11px;color:var(--text-muted)}.ps-kpi .g{font-size:10px;font-weight:700;color:var(--text-muted);letter-spacing:.05em}
.ps-health{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:10px;padding-top:8px;border-top:1px solid var(--border);font-size:11.5px}
.ps-health b{font-size:13px}
.ps-learn p{margin:0 0 8px;font-size:12.5px}
.ps-learn p b{display:inline-block;min-width:44px;color:var(--text-muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em}
.ps-users{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;padding-top:8px;border-top:1px solid var(--border)}
.ps-user{font-size:11px;background:var(--bg);border-radius:999px;padding:3px 9px}
.ps-sup{border:1px dashed var(--text-muted)}
.ps-foot{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:10.5px;color:var(--text-muted)}
.ps-foot a{color:var(--link)}
@media screen and (max-width:900px){
  .ps-hero,.ps-bottom,.ps-goals,.ps-kpis{grid-template-columns:1fr}
}
@page{size:letter landscape;margin:.3in}
@media print{
  :root:root{--bg:#fff;--surface:#fff;--text:#1B2733;--text-muted:#4A5866;--border:#D5DBE1;--link:#1F5E8F;color-scheme:light}
  body.ps{-webkit-print-color-adjust:exact;print-color-adjust:exact;background:#fff}
  .ps-page{width:1400px;max-width:none;padding:0;zoom:.7}
  .ps-hero,.ps-tier,.ps-panel,.vroad-static{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""


def render(data: dict, version: str) -> tuple[str, list[dict], dict]:
    """The page, the provenance of every number on it, and the copy block it was built from."""
    c = load_copy()
    n_personas = len(sp.md_table(ROOT / "docs/product/discovery.md")) - 1
    if n_personas != len(c["personas"]):
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: {len(c['personas'])} personas in the copy but {n_personas} in docs/product/discovery.md")
    vals, prov = values(data, n_personas)
    grid = hero_block(c) + roadmap_block(c, data, vals) + f"<section class='ps-bottom'>{privacy_block(c, data, vals)}{working_block(c, vals)}{learned_block(c)}</section>"
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
<link rel="stylesheet" href="assets/viewer.css">
<script>try{{var t=localStorage.getItem("cff-theme");if(t==="light"||t==="dark"){{document.documentElement.dataset.theme=t}}}}catch(e){{}}</script>
<style>{CSS}</style>
</head>
<body class="ps">
<main class="ps-page" id="main">
{grid}
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
