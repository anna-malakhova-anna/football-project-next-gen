"""The one-page summary of the Data product tab: public/product-summary.html (and, printed, docs/product/one-pager.pdf).

Goals, products, users, plan, privacy, proof and learning on one page. Every number is read from the product-tab exports (roadmap gates, product specs, goal scorecard, health, age funnel, age rules)
at build time and rounded for display; nothing is typed into the template and nothing is computed in the browser. The copy is `summary:` in site_src/copy/charts.yml (status draft until Anna approves it).
`PROVENANCE` records, for each number shown, the export and field it came from; tests/test_one_pager.py checks the page against it. The build fails if a {placeholder} has no value.
"""
from __future__ import annotations

import csv
import re
import sys
from html import escape as e
from pathlib import Path

import yaml

from scripts import site_product as sp
from scripts import site_tables

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
    gate_n = next(r for r in road if r["gate_id"] == "N")
    put("countries_b", f"{round(need(gate_n['current_value'], 'countries at grade B')):d}", "roadmap", "current_value (gate N)", gate_n["current_value"])
    up = kpi(data, "fan_engagement_uplift")
    put("uplift", f"{round(need(up['value'], 'engagement uplift') * 100):d}", "goal_scorecard", "value (fan_engagement_uplift)", up["value"])
    lk = kpi(data, "linked_household_rate")
    put("linked", f"{round(need(lk['value'], 'linked households') * 100):d}", "goal_scorecard", "value (linked_household_rate)", lk["value"])
    hist = list(csv.DictReader((ROOT / "products" / "boundary_debt_history.csv").open(encoding="utf-8")))
    put("debt_start", hist[0]["debt_rows"], "products/boundary_debt_history.csv", "debt_rows (first row)", hist[0]["debt_rows"])
    gaps = rows_of(data, "roadmap_gap_links")
    put("n_gaps", f"{len(gaps)}", "roadmap_gap_links", "row count", len(gaps))
    put("n_changed", f"{sum(1 for g in gaps if g['status'] == 'CHANGED')}", "roadmap_gap_links", "rows with status CHANGED", sum(1 for g in gaps if g["status"] == "CHANGED"))
    put("n_age_rules", f"{len(rows_of(data, 'age_rules'))}", "age_rules", "row count", len(rows_of(data, "age_rules")))
    for code in ("U13", "13_15", "16_17", "ADULT"):
        reg = next(r for r in rows_of(data, "conv_tier") if r["age_tier"] == code and r["step_no"] == 1)
        con = next(r for r in rows_of(data, "conv_tier") if r["age_tier"] == code and r["kind"] == "ACTIVATION")
        small = reg["tier_funnel_households"] is None or con["tier_funnel_households"] is None      # a hidden count stays hidden
        put(f"reg_{code}", "fewer than 10" if small else f"{round(reg['tier_funnel_households'], -1):,}", "conv_tier", f"tier_funnel_households (registered, {code})", reg["tier_funnel_households"])
        put(f"con_{code}", "fewer than 10" if small else f"{round(con['tier_funnel_households'], -1):,}", "conv_tier", f"tier_funnel_households (club contact, {code})", con["tier_funnel_households"])
        put(f"pct_{code}", "" if small else f"{round(con['share_of_registered'] * 100):d}", "conv_tier", f"share_of_registered (club contact, {code})", con["share_of_registered"])
    return out, prov


def pick(rows: list[dict], filt: str) -> dict:
    """The one row of an export that matches 'key=value;key=value'."""
    conds = [c.split("=", 1) for c in filt.split(";")]
    hits = [r for r in rows if all(str(r.get(k)) == v for k, v in conds)]
    if len(hits) != 1:
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: the filter '{filt}' matches {len(hits)} rows, expected 1")
    return hits[0]


def gap_evidence(g: dict, data: dict, vals: dict) -> tuple[str, dict]:
    """The evidence of one gap, read from the export the seed names. Returns the text and its provenance entry."""
    if g["source_export"] not in data:
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: gap {g['gap_id']} names an export that is not built: {g['source_export']}")
    row = pick(rows_of(data, g["source_export"]), g["source_filter"])
    v = row.get(g["source_field"])
    if v in (None, ""):
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: gap {g['gap_id']}: {g['source_export']}.{g['source_field']} is empty")
    text = fill(g["evidence_template"].replace("{v}", str(v).replace("{", "(").replace("}", ")")), vals)
    return text, {"key": f"gap_{g['gap_id']}", "file": g["source_export"], "field": g["source_field"], "raw": v, "shown": text}


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


def section(n: int, c: dict, key: str, vals: dict, component: str) -> str:
    sec = c["sections"][key]
    line = f"<p class='ps-line'>{e(fill(sec['line'], vals))}</p>" if sec["line"] else ""
    sowhat = f"<p class='ps-sowhat'><b>So what.</b> {e(fill(sec['sowhat'], vals))}</p>" if sec.get("sowhat") else ""
    return (f"<section class='ps-sec' id='s-{key}'><p class='ps-kicker'>{n} · {e(sec['kicker'])}</p><h2>{e(fill(sec['h2'], vals))}</h2>{line}{component}{sowhat}</section>")


def labels_component(c: dict, data: dict) -> str:
    """Product labels: five collapsed rows (one open at a time, a native exclusive accordion) on screen; a compact five-row table in print."""
    ps = sp.products()
    specs = {r["id"]: r for r in rows_of(data, "product_specs")}
    rows, table = "", ""
    for i, (pid, p) in enumerate(ps.items(), 1):
        sp_row = specs[pid]
        goals = " ".join(f"<span class='ps-tag'>{e(g)}</span>" for g in p["goals"])
        head = (f"<span class='ps-lname'>{e(pid)} {e(c['product_names'][pid])}</span><span class='ps-chip2'>{e(sp.TYPE_WORD[p['type']])}</span><span class='ps-chip2 ps-st-{e(p['status'])}'>{e(sp.STATUS_WORD[p['status']])}</span>"
                f"<span class='ps-lver'>v{e(p['version'])}</span><span class='ps-chip2 ps-q'>{e(quality_chip(sp_row['quality_text']))}</span>{goals}")
        body = (sp.label_html(pid, p, sp_row, True, plain=True) + f"<p class='ps-limit'>{e(c['label_limits'][pid])}</p>"
                f"<p class='note'><a href='product.html#view=D5-{i}'>Full label on the tab &rarr;</a></p>")
        rows += f"<details name='dp-label' class='ps-label'><summary>{head}</summary>{body}</details>"
        rule = p["privacy"]["prohibited_uses"][0]["use"]
        table += (f"<tr><th scope='row'>{e(pid)} {e(c['product_names'][pid])}</th><td>{e(sp.TYPE_WORD[p['type']])}</td><td>{e(sp.STATUS_WORD[p['status']])}</td><td>v{e(p['version'])}</td>"
                  f"<td>{e(quality_chip(sp_row['quality_text']))}</td><td>{e(p['owner_role'])}</td><td>Never: {e(rule)}</td></tr>")
    ptable = site_tables.enhance(f"<table class='vtable ps-print-only'><thead><tr><th>Product</th><th>Type</th><th>Status</th><th>Version</th><th>Quality</th><th>Owner</th><th>{e(c['print_rule_label'])}</th></tr></thead><tbody>{table}</tbody></table>")
    return f"<div class='ps-labels ps-screen-only'>{rows}</div>{ptable}"


def tiers_component(c: dict, data: dict, vals: dict) -> str:
    rules = rows_of(data, "age_rules")
    segs = ""
    for i, (code, label) in enumerate(c["tiers"].items(), 1):
        small = vals[f"pct_{code}"] == ""
        bar = ("<p class='ps-cnote'>fewer than 10 families</p>" if small else
               f"<div class='ps-cbar' role='img' aria-label='{e(vals[f'pct_{code}'])}% agreed to club contact'><i style='width:{e(vals[f'pct_{code}'])}%'></i></div>"
               f"<p class='ps-cnote'><b>{e(vals[f'pct_{code}'])}%</b> {e(c['consent_bar_label'])}: {e(vals[f'con_{code}'])} of {e(vals[f'reg_{code}'])} families</p>")
        segs += (f"<div class='ps-tcol'><div class='ps-tier ps-t{i}'><b>{e(label)}</b><span>{e(c['consents'][who_consents(rules, code)])}</span></div>"
                 f"<p class='ps-allowed'>{e(c['tier_allowed'][code])}</p>{bar}</div>")
    nots = "".join(f"<span class='ps-chip'><s>{e(t)}</s></span>" for t in c["not_doing"])
    return f"<div class='ps-tiers'>{segs}</div><div class='ps-chips'>{nots}</div>"


WATCH_ORDER = ["quality", "trust", "contract_status", "pipeline", "freshness", "cost", "privacy", "boundaries"]


def health_status(rows: list[dict]) -> tuple[str, str]:
    """OK / Watch / Alert for one product from its existing health rows, and the one-line reason for anything but OK."""
    if any(r["status"] == "ALERT" for r in rows):
        word, hits = "Alert", [r for r in rows if r["status"] == "ALERT"]
    elif any(r["status"] == "WATCH" for r in rows):
        word, hits = "Watch", [r for r in rows if r["status"] == "WATCH"]
        hits.sort(key=lambda r: WATCH_ORDER.index(r["area"]) if r["area"] in WATCH_ORDER else 99)   # the most product-specific reason first
    else:
        return "OK", ""
    r = hits[0]
    reason = r["measure"] if not re.search(r"[A-Z]{3,}", r["measure"]) else sp.AREA_LABEL.get(r["area"], r["area"])
    return word, f"{reason}: {r['value_text']}"


def working_component(c: dict, data: dict, vals: dict) -> str:
    road = {r["gate_id"]: r for r in rows_of(data, "roadmap") if r["gate_id"]}
    goals = ""
    for gid, g in c["goal_rows"].items():
        gate = road[g["gate"]]
        chip = f"{gate['status_text']}: {gate['value_text']}"
        goals += (f"<div class='ps-grow'><div class='ps-gnum'><span class='ps-tag'>{e(gid)}</span><div class='n'>{e(fill(g['value'], vals))}</div></div>"
                  f"<div class='ps-gtext'><p>{e(fill(g['support'], vals))}</p><p><span class='ps-gate ps-gate-{'met' if gate['gate_status'] == 'MET' else 'no'}'>{e(chip)}</span></p>"
                  f"<p class='ps-gso'><b>So what.</b> {e(fill(g['sowhat'], vals))}</p></div></div>")
    hrows = ""
    h = c["health_heads"]
    health = rows_of(data, "product_health")
    specs = {r["id"]: r for r in rows_of(data, "product_specs")}
    for pid in sp.products():
        mine = [r for r in health if r["product_id"] == pid]
        tests = next(r for r in mine if r["area"] == "pipeline")
        breaks = next(r for r in mine if r["area"] == "boundaries")
        privacy = next(r for r in mine if r["area"] == "privacy" and r["measure"] == "Share-policy check violations")
        mark = lambda r: ("&#10003;" if r["status"] == "OK" else ("&ndash;" if r["value_num"] is None else "&#10007;"))  # noqa: E731
        word, why = health_status(mine)
        hrows += (f"<tr><th scope='row'>{e(pid)} {e(c['product_names'][pid])}</th><td>{e(quality_chip(specs[pid]['quality_text']))}</td><td>{mark(tests)}</td><td>{e(breaks['value_text'])}</td><td>{mark(privacy)}</td>"
                  f"<td><b class='ps-hs ps-hs-{word.lower()}'>{word}</b>{(' <span class=ps-why>' + e(why) + '</span>') if why else ''}</td></tr>")
    htable = site_tables.enhance(f"<table class='vtable ps-health-table'><thead><tr><th>{e(h['product'])}</th><th>{e(h['grade'])}</th><th>{e(h['tests'])}</th><th>{e(h['breaks'])}</th><th>{e(h['privacy'])}</th><th>{e(h['status'])}</th></tr></thead><tbody>{hrows}</tbody></table>")
    return f"<div class='ps-grows'>{goals}</div><p class='ps-sub'>{e(fill(c['working_sub'], vals))}</p>{htable}"


def gaps_component(c: dict, data: dict, vals: dict) -> tuple[str, list[dict], dict]:
    gaps = rows_of(data, "roadmap_gap_links")
    known = {f"{r['product_id']} {r['version']}" for r in rows_of(data, "roadmap")}
    h = c["gaps_heads"]
    body, prov, marks = "", [], {}
    for g in gaps:
        text, pr = gap_evidence(g, data, vals)
        prov.append(pr)
        rid = g["roadmap_row_id"]
        if rid:
            if rid not in known:
                raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: gap {g['gap_id']} points at a roadmap card that does not exist: {rid}")
            marks.setdefault(rid, []).append(g["gap_id"])
            tag = f"<a class='ps-tagchip ps-tag-changed' href='#card-{rid.replace(' ', '-')}'>{e(c['gap_tags'][g['status']])}</a>"
        else:
            tag = f"<span class='ps-tagchip ps-tag-watch'>{e(c['gap_tags'][g['status']])}</span>"
        body += (f"<tr id='gap-{g['gap_id']}'><th scope='row'>{e(g['plain_text'])}</th><td>{e(text)}</td><td><span class='ps-tag'>{e(g['product_id'])}</span></td><td>{e(g['change_text'])}</td><td>{tag}</td></tr>")
    table = site_tables.enhance(f"<table class='vtable ps-gaps'><thead><tr><th>{e(h['gap'])}</th><th>{e(h['evidence'])}</th><th>{e(h['product'])}</th><th>{e(h['changed'])}</th><th>{e(h['tag'])}</th></tr></thead><tbody>{body}</tbody></table>")
    return table, prov, marks


def learned_component(c: dict, vals: dict) -> str:
    rows = "".join(f"<tr><th scope='row'>{e(r['label'])}</th><td>{e(fill(r['what'], vals))}</td><td>{e(fill(r['sowhat'], vals))}</td></tr>" for r in c["learned_rows"].values())
    return site_tables.enhance(f"<table class='vtable ps-learned'><thead><tr><th></th><th>What</th><th>So what</th></tr></thead><tbody>{rows}</tbody></table>")


CSS = """
body.ps{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 var(--font-body)}
.ps *{box-sizing:border-box}
.ps-story{max-width:960px;margin:0 auto;padding:20px 16px 28px}
.ps-hero{background:var(--night-field);color:#fff;border-radius:12px;padding:20px 24px;margin-bottom:40px}
.ps-hero h1{font-family:var(--font-display);font-size:32px;line-height:1.1;margin:0;color:#fff}
.ps-hero p{margin:6px 0 0;color:#B9C6DC;font-size:15px}
.ps-sec{margin:0 0 40px;padding-bottom:36px;border-bottom:1px solid var(--border);break-inside:avoid}
.ps-sec:last-of-type{border-bottom:0}
.ps-kicker{margin:0 0 4px;font-size:11.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)}
.ps-sec h2{font-family:var(--font-display);font-size:26px;line-height:1.15;margin:0 0 6px;color:var(--text)}
.ps-line{margin:0 0 14px;color:var(--text-muted)}
.ps-sec .vproduct{margin:0}
.ps-sec .vpersonas{grid-template-columns:repeat(3,minmax(0,1fr))}
.ps-sec .vpersona{font-size:.8125rem}
.ps-sec .vdep{max-height:none}
.ps-tiers{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:4px 0 12px}
.ps-tier{border-radius:6px;padding:9px 10px;color:#fff}
.ps-tier b{display:block;font-size:14px}.ps-tier span{font-size:12px}
.ps-t1{background:#1f4e79}.ps-t2{background:#2d6a9a}.ps-t3{background:#3b76a6}.ps-t4{background:#59626d}
.ps-chips{display:flex;flex-wrap:wrap;gap:6px}
.ps-chip{display:inline-flex;gap:4px;border:1px solid var(--border);border-radius:999px;padding:2px 10px;font-size:12px;color:var(--text-muted)}
.ps-chip::before{content:"\\2298";color:#C0392B;font-weight:700}
.ps-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.ps-kpi .n{font-family:var(--font-display);font-size:34px;font-weight:700;line-height:1.05}
.ps-kpi .l{font-size:12.5px;color:var(--text-muted)}.ps-kpi .g{font-size:11px;font-weight:700;color:var(--text-muted);letter-spacing:.05em}
.ps-health{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:14px;padding-top:10px;border-top:1px solid var(--border);font-size:13px}
.ps-sub{color:var(--text-muted)}
.ps-sowhat{margin:14px 0 0;padding:8px 12px;border-left:4px solid var(--accent);background:var(--surface);border-radius:0 6px 6px 0;font-size:14px}
.ps-sowhat b{color:var(--accent)}
.ps-print-only{display:none}
.ps-labels{display:grid;gap:6px}
.ps-label{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:0}
.ps-label summary{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:9px 12px;cursor:pointer;list-style:none}
.ps-label summary::-webkit-details-marker{display:none}
.ps-label summary::before{content:"\\25B8";color:var(--text-muted)}
.ps-label[open] summary::before{content:"\\25BE"}
.ps-lname{font-weight:700;min-width:150px}
.ps-lver{font-size:12px;color:var(--text-muted)}
.ps-chip2{display:inline-block;font-size:12px;padding:0 8px;border-radius:999px;border:1px solid var(--border)}
.ps-st-mvp{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:700}
.ps-st-proposed{border-style:dashed}
.ps-q{border-color:var(--series-sand)}
.ps-tag{display:inline-block;font-weight:700;font-size:11px;padding:0 5px;border:1px solid var(--accent);color:var(--accent);border-radius:2px;white-space:nowrap}
.ps-label .vlabel{padding:0 14px 6px;font-size:13.5px}
.ps-label .vlabel p{margin:4px 0}
.ps-label .vlabel ul{margin:2px 0 6px;padding-left:18px}
.ps-label .vrules{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.ps-label .vnever li{color:var(--text)}
.ps-label .vnever li::marker{content:"\\2298  ";color:#C0392B}
.ps-limit{margin:0 14px 4px;color:var(--text-muted);font-size:13px}
.ps-label .note{margin:0 14px 10px}
.ps-tcol{min-width:0}
.ps-allowed{font-size:12px;margin:6px 0;color:var(--text)}
.ps-cbar{height:7px;border-radius:4px;background:var(--border);overflow:hidden}
.ps-cbar i{display:block;height:100%;background:#2d6a9a}
.ps-cnote{font-size:12px;margin:4px 0 0;color:var(--text-muted)}
.ps-grows{display:grid;gap:0}
.ps-grow{display:grid;grid-template-columns:170px 1fr;gap:16px;padding:12px 0;border-top:1px solid var(--border)}
.ps-grow:first-child{border-top:0}
.ps-gnum .n{font-family:var(--font-display);font-size:36px;font-weight:700;line-height:1.05}
.ps-gtext p{margin:0 0 4px}
.ps-gso{color:var(--text)}.ps-gso b{color:var(--accent)}
.ps-gate{display:inline-block;font-size:12px;border-radius:999px;padding:1px 10px;border:1px solid var(--border)}
.ps-gate-met{border-color:#2F6B4F;color:#2F6B4F}.ps-gate-no{border-color:#B04A1C;color:#B04A1C}
.ps-sub{font-size:12px;color:var(--text-muted);margin:8px 0}
.ps-hs{font-weight:700}.ps-hs-ok{color:#2F6B4F}.ps-hs-watch{color:#B04A1C}.ps-hs-alert{color:#C0392B}
.ps-why{display:block;font-size:12px;color:var(--text-muted)}
.ps-tagchip{display:inline-block;font-size:12px;border-radius:999px;padding:1px 10px;white-space:nowrap;text-decoration:none}
.ps-tag-changed{background:var(--accent);color:#fff;font-weight:700}
.ps-tag-watch{border:1px dashed var(--text-muted);color:var(--text-muted)}
.vrgap{display:inline-block;margin-top:2px;font-size:.625rem;color:var(--accent);font-weight:700;text-decoration:none}
.ps-sec .vrcard:target{outline:2px solid var(--accent)}
.ps-learn p{margin:0 0 8px}
.ps-learn p b{display:inline-block;min-width:110px;color:var(--text-muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em}
.ps-foot{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--text-muted)}
.ps-foot a{color:var(--link)}
@media screen and (max-width:700px){
  .ps-sec .vpersonas,.ps-tiers,.ps-kpis,.ps-grow,.ps-label .vrules{grid-template-columns:1fr}
  .ps-sec h2{font-size:22px}
}
@page{size:letter portrait;margin:.5in}
@media print{
  :root:root{--bg:#fff;--surface:#fff;--text:#1B2733;--text-muted:#4A5866;--border:#D5DBE1;--link:#1F5E8F;color-scheme:light;--pz1:.6;--pz2:.57;--pz3:.5}
  body.ps{-webkit-print-color-adjust:exact;print-color-adjust:exact;background:#fff}
  .ps-story{max-width:none;padding:0}
  .ps-p1{zoom:var(--pz1);width:calc(720px / var(--pz1));height:calc(960px / var(--pz1));overflow:hidden;break-after:page}
  .ps-p2{zoom:var(--pz2);width:calc(720px / var(--pz2));height:calc(960px / var(--pz2));overflow:hidden;break-after:page}
  .ps-p3{zoom:var(--pz3);width:calc(720px / var(--pz3));height:calc(960px / var(--pz3));overflow:hidden}
  .ps-screen-only{display:none}
  table.ps-print-only{display:table}
  .ps-hero,.ps-tier,.vroad,.vmatrix{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .ps-hero{margin-bottom:22px;padding:14px 20px}
  .ps-sec{margin-bottom:18px;padding-bottom:14px}
  .ps-sec h2{font-size:24px}
  .ps-line{margin-bottom:8px}
  .ps-sowhat{margin-top:8px;padding:5px 10px}
  .ps-story .vr-head{display:grid}
  .ps-story .vr-head,.ps-story .vr-lane{grid-template-columns:170px repeat(4,minmax(0,1fr))}
  .ps-story .vr-cell:empty,.ps-story .vr-cell:not(:has(*)){display:flex}
  .ps-story .vr-cell::before{content:none}
  .ps-story .ps-tiers{grid-template-columns:repeat(4,1fr)}
  .ps-story .ps-kpis{grid-template-columns:repeat(3,1fr)}
  .ps-sec .vdep{max-height:300px}
  .ps-sec .vpersona{padding:7px 9px}
  .ps-sec .vpersona p{margin:3px 0}
  .ps-sec .vtable th,.ps-sec .vtable td,.ps-sec .vmatrix th,.ps-sec .vmatrix td{padding:4px 8px}
}
"""


def render(data: dict, version: str) -> tuple[str, list[dict], dict]:
    """The page, the provenance of every number on it, and the copy block it was built from."""
    c = load_copy()
    n_personas = len(sp.md_table(ROOT / "docs/product/discovery.md")) - 1
    vals, prov = values(data, n_personas)
    ps = sp.products()
    names = c["product_names"]
    d10 = yaml.safe_load(COPY_PATH.read_text(encoding="utf-8"))["charts"]["D10"]
    gaps_html, gap_prov, marks = gaps_component(c, data, vals)
    prov += gap_prov
    vals.update({p["key"]: p["shown"] for p in gap_prov})
    comps = [("matrix", sp.matrix_html(ps, static={"goals": c["goal_short"], "products": names})),
             ("deps", sp.dependency_svg()),
             ("personas", sp.personas_html(False, static=True)),
             ("labels", labels_component(c, data)),
             ("priorities", site_tables.enhance(sp.prioritization_html(rows_of(data, "product_prioritization"), static={"products": names}))),
             ("roadmap", sp.roadmap_board_html(rows_of(data, "roadmap"), ps, d10, {}, static=True, gap_marks=marks)),
             ("privacy", tiers_component(c, data, vals)),
             ("working", working_component(c, data, vals)),
             ("gaps", gaps_html),
             ("learned", learned_component(c, vals))]
    secs = [section(i, c, k, vals, comp) for i, (k, comp) in enumerate(comps, 1)]
    hero = f"<header class='ps-hero'><h1>{e(c['title'])}</h1><p>{e(c['pitch'])}</p></header>"
    foot = (f"<footer class='ps-foot'><span>{e(c['footer'])}</span><a href='product.html'>{e(c['footer_link'])} &rarr;</a><span>{e(fill(c['methodology'], {'version': str(version)}))}</span></footer>")
    grid = f"<div class='ps-p1'>{hero}{''.join(secs[:3])}</div><div class='ps-p2'>{''.join(secs[3:6])}</div><div class='ps-p3'>{''.join(secs[6:])}{foot}</div>"
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
<link rel="stylesheet" href="css/site.css">
<link rel="stylesheet" href="assets/viewer.css">
<script>try{{var t=localStorage.getItem("cff-theme");if(t==="light"||t==="dark"){{document.documentElement.dataset.theme=t}}}}catch(e){{}}</script>
<style>{CSS}</style>
</head>
<body class="ps">
<main class="ps-story" id="main">
{grid}
</main>
<script>/* progressive enhancement: where the browser lacks exclusive <details name>, opening one closes the others. It only toggles open; it computes nothing. */
document.querySelectorAll('details[name=dp-label]').forEach(function(d){{d.addEventListener('toggle',function(){{if(d.open&&!('name' in HTMLDetailsElement.prototype)){{document.querySelectorAll('details[name=dp-label]').forEach(function(o){{if(o!==d)o.open=false}})}}}})}});
</script>
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
