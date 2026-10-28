"""The one-page summary of the Data product tab: public/product-summary.html (and, printed, docs/product/one-pager.pdf).

Goals, products, users, plan, privacy, proof and learning on one page. Every number is read from the product-tab exports (roadmap gates, product specs, goal scorecard, health, age funnel, age rules)
at build time and rounded for display; nothing is typed into the template and nothing is computed in the browser. The copy is `summary:` in site_src/copy/charts.yml (status draft until Anna approves it).
`PROVENANCE` records, for each number shown, the export and field it came from; tests/test_one_pager.py checks the page against it. The build fails if a {placeholder} has no value.
"""
from __future__ import annotations

import re
import sys
from html import escape as e

import yaml

from scripts import site_product as sp
from scripts import site_tables
from scripts.common import ROOT

COPY_PATH = ROOT / "site_src" / "copy" / "charts.yml"
SLUG = "product-summary"
PLACEHOLDER = re.compile(r"\{([A-Za-z_0-9]+)\}")
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
    put("girls_lo", f"{need(gs['value_low'], 'girls share low') * 100:.1f}", "goal_scorecard", "value_low (girls_share_of_youth)", gs["value_low"])
    put("girls_hi", f"{need(gs['value_high'], 'girls share high') * 100:.1f}", "goal_scorecard", "value_high (girls_share_of_youth)", gs["value_high"])
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
    gate_z = next(r for r in road if r["gate_id"] == "Z_ACTIVATION")
    mz = re.search(r"now ([0-9.]+)%", need(gate_z["value_text"], "consent gate value"))
    if not mz:
        raise SystemExit(f"SITE BUILD REFUSED:\n  one-pager: cannot read the consent gate value from '{gate_z['value_text']}'")
    put("z_known", mz.group(1), "roadmap", "value_text (gate Z_ACTIVATION)", gate_z["value_text"])
    gate_y = next(r for r in road if r["gate_id"] == "Y")
    put("identity_limit", f"{round(need(gate_y['target'], 'identity gate limit')):d}", "roadmap", "target (gate Y)", gate_y["target"])
    for sp_row in rows_of(data, "product_specs"):
        major_minor = ".".join(sp_row["version"].split(".")[:2])
        put(f"ver_{sp_row['id']}", f"v{major_minor}", "product_specs", f"version ({sp_row['id']})", sp_row["version"])
    gate_n = next(r for r in road if r["gate_id"] == "N")
    put("countries_b", f"{round(need(gate_n['current_value'], 'countries at grade B')):d}", "roadmap", "current_value (gate N)", gate_n["current_value"])
    up = kpi(data, "fan_engagement_uplift")
    put("uplift", f"{round(need(up['value'], 'engagement uplift') * 100):d}", "goal_scorecard", "value (fan_engagement_uplift)", up["value"])
    lk = kpi(data, "linked_household_rate")
    put("linked", f"{round(need(lk['value'], 'linked households') * 100):d}", "goal_scorecard", "value (linked_household_rate)", lk["value"])
    gaps = rows_of(data, "roadmap_gap_links")
    put("n_gaps", f"{len(gaps)}", "roadmap_gap_links", "row count", len(gaps))
    put("n_changed", f"{sum(1 for g in gaps if g['status'] == 'CHANGED')}", "roadmap_gap_links", "rows with status CHANGED", sum(1 for g in gaps if g["status"] == "CHANGED"))
    put("n_products", f"{len(sp.products())}", "product_specs", "the portfolio the tab draws (DP1 to DP5; DP6 is the Global outlook's own product)", len(sp.products()))
    bands = {b["grade"]: b["min_score"] for b in rows_of(data, "dq_grade_bands")}
    for grade in ("A", "B", "C"):
        put(f"band_{grade.lower()}", f"{int(need(bands.get(grade), 'grade band ' + grade))}", "dq_grade_bands", f"min_score ({grade})", bands[grade])
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


def quality_chip(text: str, c: dict | None = None, vals: dict | None = None) -> str:
    """A short plain label from the live quality text of a product spec; unknown shapes fail the build instead of showing nothing.
    With the copy and values, the identity range and the spread of market grades use the copy's wording ("Identity error under 1%", "Grades vary by market")."""
    if (m := re.match(r"grade ([A-F])\b", text)):
        return f"Grade {m.group(1)}"
    if re.match(r"identity range ([0-9.]+)%", text):
        return fill(c["quality_labels"]["identity"], vals) if c else "Identity range"
    if re.match(r"A \d+, B \d+", text):
        return c["quality_labels"]["varies"] if c else "Grades vary"
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
    see = f"<a class='ps-see' href='product.html{e(sec['see'])}'>{e(c['see_full'])} &rarr;</a>"
    return (f"<section class='ps-sec' id='s-{key}'><header class='ps-sh'><div class='ps-sht'><p class='ps-kicker'>{n} · {e(sec['kicker'])}</p><h2>{e(fill(sec['h2'], vals))}</h2></div>{see}</header>{line}{component}</section>")


def labels_component(c: dict, data: dict, vals: dict) -> str:
    """Product labels: five collapsed rows (one open at a time, a native exclusive accordion) on screen; a compact five-row table in print."""
    ps = sp.products()
    specs = {r["id"]: r for r in rows_of(data, "product_specs")}
    st = c["card_stats"]
    rows, table = "", ""
    for i, (pid, p) in enumerate(ps.items(), 1):
        sp_row = specs[pid]
        kind = sp.LANE_KIND[pid][0]
        goals = " ".join(f"<span class='ps-tag'>{e(g)}</span>" for g in p["goals"])
        cell = lambda k, v: f"<span class='ps-cell'><i>{e(st[k])}</i><b>{v}</b></span>"   # noqa: E731
        head = (f"<span class='ps-num' aria-hidden='true'>{i:02d}</span><span class='ps-lname'>{e(pid)} {e(c['product_names'][pid])}<small class='ps-pos'>{e(c['positions'][kind])}</small></span>"
                f"<span class='ps-cells'>{cell('version', 'v' + e(p['version']))}{cell('status', e(c['status_words'][p['status']]))}{cell('grade', e(quality_chip(sp_row['quality_text'], c, vals)))}{cell('goals', goals)}</span>")
        body = (sp.label_html(pid, p, sp_row, True, plain=True) + f"<p class='ps-limit'>{e(c['label_limits'][pid])}</p>"
                f"<p class='note'><a href='product.html#view=D5-{i}'>Full label on the tab &rarr;</a></p>")
        rows += f"<details name='dp-label' class='ps-label ps-k-{kind}'><summary>{head}</summary>{body}</details>"
        rule = p["privacy"]["prohibited_uses"][0]["use"]
        table += (f"<tr><th scope='row'>{e(pid)} {e(c['product_names'][pid])}</th><td>{e(sp.TYPE_WORD[p['type']])}</td><td>{e(c['status_words'][p['status']])}</td><td>v{e(p['version'])}</td>"
                  f"<td>{e(quality_chip(sp_row['quality_text'], c, vals))}</td><td>{e(p['owner_role'])}</td><td>Never: {e(rule)}</td></tr>")
    ptable = site_tables.enhance(f"<table class='vtable ps-print-only'><thead><tr><th>Product</th><th>Type</th><th>Status</th><th>Version</th><th>Quality</th><th>Owner</th><th>{e(c['print_rule_label'])}</th></tr></thead><tbody>{table}</tbody></table>")
    legend = f"<p class='ps-legend'>{e(fill(c['grade_legend'], vals))}</p>"
    return f"<div class='ps-labels ps-screen-only'>{rows}</div>{ptable}{legend}"


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


WATCH_ORDER = ["quality", "trust", "contract_status", "pipeline", "freshness", "privacy", "boundaries"]


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
        goals += (f"<div class='ps-leader'><span class='ps-tag'>{e(gid)}</span><div class='n'>{e(fill(g['value'], vals))}</div><div class='lab'>{e(g['label'])}</div>"
                  f"<p>{e(fill(g['support'], vals))}</p><p><span class='ps-gate ps-gate-{'met' if gate['gate_status'] == 'MET' else 'no'}'>{e(chip)}</span></p>"
                  f"<p class='ps-gso'><b>So what.</b> {e(fill(g['sowhat'], vals))}</p></div>")
    hrows = ""
    h = c["health_heads"]
    health = rows_of(data, "product_health")
    specs = {r["id"]: r for r in rows_of(data, "product_specs")}
    for pid in sp.products():
        mine = [r for r in health if r["product_id"] == pid]
        tests = next(r for r in mine if r["area"] == "pipeline")
        privacy = next(r for r in mine if r["area"] == "privacy" and r["measure"] == "Share-policy check violations")
        mark = lambda r: ("&#10003;" if r["status"] == "OK" else ("&ndash;" if r["value_num"] is None else "&#10007;"))  # noqa: E731
        word, why = health_status(mine)
        hrows += (f"<tr><th scope='row'>{e(pid)} {e(c['product_names'][pid])}</th><td>{e(quality_chip(specs[pid]['quality_text'], c, vals))}</td><td>{mark(tests)}</td><td>{mark(privacy)}</td>"
                  f"<td><b class='ps-hs ps-hs-{word.lower()}'>{word}</b>{(' <span class=ps-why>' + e(why) + '</span>') if why else ''}</td></tr>")
    htable = site_tables.enhance(f"<table class='vtable ps-health-table'><thead><tr><th>{e(h['product'])}</th><th>{e(h['grade'])}</th><th>{e(h['tests'])}</th><th>{e(h['privacy'])}</th><th>{e(h['status'])}</th></tr></thead><tbody>{hrows}</tbody></table>")
    return f"<div class='ps-leaders'>{goals}</div><p class='ps-sub'>{e(fill(c['working_sub'], vals))}</p>{htable}"


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
        body += (f"<tr id='gap-{g['gap_id']}'><th scope='row'><span class='ps-gn' aria-label='Gap {g['gap_id']}'>{g['gap_id']}</span>{e(g['plain_text'])}</th><td>{e(text)}</td><td><span class='ps-tag'>{e(g['product_id'])}</span></td><td>{e(g['change_text'])}</td><td>{tag}</td></tr>")
    table = site_tables.enhance(f"<table class='vtable ps-gaps'><thead><tr><th>{e(h['gap'])}</th><th>{e(h['evidence'])}</th><th>{e(h['product'])}</th><th>{e(h['changed'])}</th><th>{e(h['tag'])}</th></tr></thead><tbody>{body}</tbody></table>")
    return table, prov, marks


def learned_component(c: dict, vals: dict) -> str:
    h = c["findings_heads"]
    rows = "".join(f"<tr><th scope='row'>{e(f['finding'])}</th><td>{e(fill(f['evidence'], vals))}</td><td>{e(f['sowhat'])}</td></tr>" for f in c["findings"])
    table = site_tables.enhance(f"<table class='vtable ps-learned'><thead><tr><th>{e(h['finding'])}</th><th>{e(h['evidence'])}</th><th>{e(h['sowhat'])}</th></tr></thead><tbody>{rows}</tbody></table>")
    nxt = c["next_strip"]
    return f"{table}<div class='ps-next'><b>{e(nxt['label'])}</b><span>{e(nxt['text'])}</span></div>"


CSS = """
body.summary{--s-ink-hero:#0b1726;--s-hero-ink:#ffffff;--s-hero-muted:#b4c0d0;--s-accent:#19b37a;--s-accent-ink:#0b7a52;--s-accent-2:#7aa7ff;--s-bg:#f4f5f7;--s-card:#ffffff;--s-line:#e1e4e8;
  --s-text:#1b2733;--s-muted:#4f5b68;--s-zebra:#f0f2f5;--s-arrow:#0b1726;--s-ok-bg:#d8f3e7;--s-ok:#0b5f41;--s-watch-bg:#fde9c8;--s-watch:#7a4a00;--s-alert-bg:#fbdada;--s-alert:#9b1c1c;--s-shadow:0 6px 16px rgba(11,23,38,.14)}
@media (prefers-color-scheme:dark){html:not([data-theme="light"]) body.summary{--s-ink-hero:#070e18;--s-hero-ink:#eef2f7;--s-hero-muted:#a9b6c7;--s-accent:#3fd39a;--s-accent-ink:#5fe0b0;--s-accent-2:#9dbdff;--s-bg:#0f141b;--s-card:#161d26;--s-line:#26303b;
  --s-text:#e6ebf1;--s-muted:#a9b4c0;--s-zebra:#1a222c;--s-arrow:#cfd8e3;--s-ok-bg:#0f3a2a;--s-ok:#7ee3b8;--s-watch-bg:#3a2a0c;--s-watch:#f0c070;--s-alert-bg:#3d1717;--s-alert:#ff9a9a;--s-shadow:0 6px 16px rgba(0,0,0,.5)}}
html[data-theme="dark"] body.summary{--s-ink-hero:#070e18;--s-hero-ink:#eef2f7;--s-hero-muted:#a9b6c7;--s-accent:#3fd39a;--s-accent-ink:#5fe0b0;--s-accent-2:#9dbdff;--s-bg:#0f141b;--s-card:#161d26;--s-line:#26303b;
  --s-text:#e6ebf1;--s-muted:#a9b4c0;--s-zebra:#1a222c;--s-arrow:#cfd8e3;--s-ok-bg:#0f3a2a;--s-ok:#7ee3b8;--s-watch-bg:#3a2a0c;--s-watch:#f0c070;--s-alert-bg:#3d1717;--s-alert:#ff9a9a;--s-shadow:0 6px 16px rgba(0,0,0,.5)}
body.summary{--bg:var(--s-bg);--surface:var(--s-card);--border:var(--s-line);--text:var(--s-text);--text-muted:var(--s-muted);--accent:var(--s-accent-ink);--font-body:Inter,system-ui,sans-serif;--font-display:"Barlow Condensed","Arial Narrow",sans-serif;
  margin:0;background:var(--s-bg);color:var(--s-text);font:400 15px/1.5 Inter,system-ui,sans-serif}
body.summary *{box-sizing:border-box}
body.summary .ps-inner,body.summary .ps-story{max-width:1200px;margin:0 auto;padding-left:24px;padding-right:24px}
/* hero */
body.summary .ps-hero{background-color:var(--s-ink-hero);background-image:repeating-linear-gradient(90deg,rgba(255,255,255,.04) 0 1px,transparent 1px 56px),linear-gradient(115deg,transparent 50%,rgba(25,179,122,.16) 100%);color:var(--s-hero-ink);padding:40px 0 0}
body.summary .ps-eyebrow{margin:0 0 8px;font:600 12px/1 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--s-accent)}
body.summary .ps-hero h1{font:700 64px/1 "Barlow Condensed",sans-serif;letter-spacing:.01em;text-transform:uppercase;margin:0;color:var(--s-hero-ink)}
body.summary .ps-badge{display:inline-block;margin:14px 0 0;font:600 11px/1 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;border:1px solid var(--s-hero-muted);color:var(--s-hero-ink);border-radius:999px;padding:5px 12px}
body.summary .ps-pitch{margin:14px 0 0;color:var(--s-hero-muted);font-size:17px;max-width:760px}
body.summary .ps-record{display:grid;grid-template-columns:repeat(4,1fr);margin-top:28px;border-top:1px solid rgba(255,255,255,.14)}
body.summary .ps-rec{padding:18px 0 20px 20px;border-left:1px solid rgba(255,255,255,.14)}
body.summary .ps-rec:first-child{border-left:0;padding-left:0}
body.summary .ps-rec .n{font:700 64px/1 "Barlow Condensed",sans-serif;font-variant-numeric:tabular-nums;color:var(--s-hero-ink)}
body.summary .ps-rec .l{margin-top:4px;font:600 12px/1.2 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--s-hero-muted)}
/* sticky tab bar */
body.summary .ps-tabs{position:sticky;top:0;z-index:20;background:var(--s-ink-hero);border-top:1px solid rgba(255,255,255,.1);box-shadow:0 2px 0 rgba(0,0,0,.2)}
body.summary .ps-tabs .ps-inner{display:flex;gap:4px;overflow-x:auto;white-space:nowrap;scrollbar-width:thin}
body.summary .ps-tabs a{display:block;padding:15px 14px 12px;font:600 12px/1 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--s-hero-muted);text-decoration:none;border-bottom:3px solid transparent}
body.summary .ps-tabs a:hover{color:var(--s-hero-ink)}
body.summary .ps-tabs a.on{color:var(--s-hero-ink);border-bottom-color:var(--s-accent)}
/* sections */
body.summary .ps-story{padding-top:56px;padding-bottom:40px}
body.summary .ps-sec{margin:0 0 64px;padding:0;border:0;scroll-margin-top:60px;break-inside:avoid}
body.summary .ps-sh{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;border-left:4px solid var(--s-accent);padding-left:14px;margin-bottom:14px}
body.summary .ps-kicker{margin:0 0 4px;font:600 12px/1.2 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--s-muted)}
body.summary .ps-sec h2{font:700 36px/1.05 "Barlow Condensed",sans-serif;letter-spacing:.01em;text-transform:uppercase;margin:0;color:var(--s-text)}
body.summary .ps-see{flex:none;margin-top:4px;font:600 12px/1 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--s-accent-ink);text-decoration:none;white-space:nowrap}
body.summary .ps-see:hover{text-decoration:underline}
body.summary .ps-line{margin:0 0 16px;color:var(--s-muted)}
body.summary .ps-sec .vproduct{margin:0}
/* standings tables */
body.summary .vtable,body.summary .vmatrix{width:100%;border-collapse:collapse;font-size:14px;background:var(--s-card);border:1px solid var(--s-line)}
body.summary .vtable thead th,body.summary .vmatrix thead th{background:var(--s-ink-hero);color:var(--s-hero-ink);font:600 11px/1.2 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;padding:0 12px;height:40px;border:0;text-align:left;vertical-align:middle}
body.summary .vtable td,body.summary .vtable tbody th,body.summary .vmatrix td,body.summary .vmatrix tbody th{height:40px;padding:6px 12px;border:0;border-bottom:1px solid var(--s-line);vertical-align:middle;font-weight:400}
body.summary .vtable tbody th[scope=row],body.summary .vmatrix tbody th{font-weight:700;color:var(--s-text)}
body.summary .vtable tbody tr:nth-child(even){background:var(--s-zebra)}
body.summary #s-priorities td:nth-child(n+2):nth-child(-n+6),body.summary #s-priorities thead th:nth-child(n+2):nth-child(-n+6){text-align:right;font-variant-numeric:tabular-nums}
body.summary .ps-health-table td:nth-child(n+2):nth-child(-n+4),body.summary .ps-health-table thead th:nth-child(n+2):nth-child(-n+4){text-align:center}
body.summary .vmatrix td{text-align:center;font-weight:600}
body.summary .vm-pill{display:inline-block;padding:2px 12px;border-radius:999px;font:700 11px/1.5 Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase}
body.summary .vmatrix thead th:not(:first-child){text-align:center}
/* roster cards (product labels) */
body.summary .ps-labels{display:grid;gap:10px}
body.summary .ps-label{--k:#b8a06a;background:var(--s-card);border:1px solid var(--s-line);border-left:6px solid var(--k);border-radius:4px}
body.summary .ps-k-source{--k:#b8a06a}body.summary .ps-k-master{--k:#3D7CC9}body.summary .ps-k-insights{--k:#2F6B4F}body.summary .ps-k-restricted{--k:#7D4E8E}
body.summary .ps-label summary{color:var(--s-text);display:grid;grid-template-columns:64px minmax(190px,1fr) 3fr;align-items:center;gap:12px;padding:12px 16px;cursor:pointer;list-style:none}
body.summary .ps-label summary::-webkit-details-marker{display:none}
body.summary .ps-num{font:700 52px/1 "Barlow Condensed",sans-serif;color:transparent;-webkit-text-stroke:1.5px var(--s-muted)}
body.summary .ps-lname{font:700 22px/1.1 "Barlow Condensed",sans-serif;letter-spacing:.01em;text-transform:uppercase}
body.summary .ps-pos{display:block;margin-top:3px;font:600 11px/1 Inter,sans-serif;letter-spacing:.08em;color:var(--s-muted)}
body.summary .ps-cells{display:flex;flex-wrap:wrap;gap:8px}
body.summary .ps-cell{background:var(--s-bg);border-radius:4px;padding:5px 12px;min-width:92px}
body.summary .ps-cell i{display:block;font:600 10px/1.2 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--s-muted);font-style:normal}
body.summary .ps-cell b{font:600 14px/1.3 Inter,sans-serif;font-variant-numeric:tabular-nums}
body.summary .ps-tag{display:inline-block;font-weight:700;font-size:11px;padding:0 5px;border:1px solid var(--s-accent-ink);color:var(--s-accent-ink);border-radius:2px;white-space:nowrap}
body.summary .ps-label[open]>summary{border-bottom:1px solid var(--s-line)}
body.summary .ps-label .vlabel{padding:12px 20px 4px;font-size:14px;background:var(--s-bg)}
body.summary .ps-label .vlabel p{margin:4px 0}
body.summary .ps-label .vlabel ul{margin:2px 0 6px;padding-left:18px}
body.summary .ps-label .vrules{display:grid;grid-template-columns:1fr 1fr;gap:16px}
body.summary .ps-label .vnever li::marker{content:"\\2298  ";color:#C0392B}
body.summary .ps-limit{margin:0;padding:0 20px 4px;background:var(--s-bg);color:var(--s-muted);font-size:13px}
body.summary .ps-label .note{margin:0;padding:4px 20px 12px;background:var(--s-bg)}
body.summary .ps-legend{margin:14px 0 0;font-size:13px;color:var(--s-muted)}
body.summary .ps-print-only{display:none}
/* persona cards */
body.summary .vpersonas{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
body.summary .vpersona{display:grid;grid-template-columns:44px 1fr;column-gap:12px;align-content:start;background:var(--s-card);border:1px solid var(--s-line);border-top:4px solid var(--s-accent);border-radius:4px;padding:16px;font-size:14px}
body.summary .vpersona>p{grid-column:1 / -1;margin:6px 0 0}
body.summary .vpersona .vmono{grid-row:1 / span 2;display:flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:50%;background:var(--s-ink-hero);color:var(--s-hero-ink);font:700 18px/1 "Barlow Condensed",sans-serif;letter-spacing:.04em}
body.summary .vpersona h4{margin:0;align-self:end;font:700 22px/1.05 "Barlow Condensed",sans-serif;letter-spacing:.01em;text-transform:uppercase;color:var(--s-text)}
body.summary .vpersona .note{grid-column:2;margin:2px 0 0;font:600 11px/1.2 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--s-muted)}
/* diagram */
body.summary .vdep{width:100%;height:auto;max-height:none}
body.summary .vdep rect{fill:var(--s-card);stroke:rgba(27,39,51,.28);stroke-width:1;rx:4}
body.summary .vdep .db-util{fill:#f3ecd3;filter:drop-shadow(0 -5px 0 #b8a06a)}body.summary .vdep .db-en{fill:#dbe7f8;filter:drop-shadow(0 -5px 0 #3D7CC9)}body.summary .vdep .db-dr{fill:#d3ebd9;filter:drop-shadow(0 -5px 0 #2F6B4F)}
body.summary .vdep .db-src{fill:var(--s-bg);stroke:var(--s-muted);stroke-dasharray:4 3}
body.summary .vdep .dt{font:700 14px "Barlow Condensed",sans-serif;letter-spacing:.02em;text-transform:uppercase;fill:#1B2733}
body.summary .vdep .ds{font:400 11px Inter,sans-serif;fill:#3a4654}
body.summary .vdep g:has(.db-src) .dt{fill:var(--s-text)}body.summary .vdep g:has(.db-src) .ds{fill:var(--s-muted)}
body.summary .vdep .da{stroke:var(--s-arrow);stroke-width:1.6}body.summary .vdep .dah{fill:var(--s-arrow)}
/* roadmap as a schedule grid */
body.summary .vroad{font-size:.8125rem}
body.summary .vroad .vr-colhead{background:var(--s-ink-hero);color:var(--s-hero-ink);font:700 15px/1 "Barlow Condensed",sans-serif;letter-spacing:.06em;text-transform:uppercase;padding:9px 10px;border-radius:4px 4px 0 0}
body.summary .vroad .vrcard{border-radius:4px;box-shadow:0 1px 0 rgba(11,23,38,.18);background:var(--s-card);border-color:var(--s-line)}
body.summary .vroad .vr-cell{background:var(--s-bg);border-color:var(--s-line)}
body.summary .vroad .vr-label{color:#1B2733}
body.summary .vroad .vrpivot{background:var(--s-card);color:var(--s-text)}
body.summary .vroad .vrtitle,body.summary .vroad .vgval{color:var(--s-text)}
body.summary .vrgap{display:inline-block;margin-top:2px;font-size:.6875rem;color:var(--s-accent-ink);font-weight:700;text-decoration:none}
body.summary .vroad .vrcard:target{outline:2px solid var(--s-accent)}
/* privacy */
body.summary .ps-tiers{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:4px 0 16px}
body.summary .ps-tier{border-radius:4px;padding:10px 12px;color:#fff}
body.summary .ps-tier b{display:block;font:700 20px/1.1 "Barlow Condensed",sans-serif;letter-spacing:.01em;text-transform:uppercase}
body.summary .ps-tier span{font-size:12px}
body.summary .ps-t1{background:#1f4e79}body.summary .ps-t2{background:#2d6a9a}body.summary .ps-t3{background:#2e6c97}body.summary .ps-t4{background:#59626d}
body.summary .ps-allowed{font-size:13px;margin:8px 0}
body.summary .ps-cbar{height:8px;border-radius:2px;background:var(--s-line);overflow:hidden}
body.summary .ps-cbar i{display:block;height:100%;background:var(--s-accent)}
body.summary .ps-cnote{font-size:12px;margin:5px 0 0;color:var(--s-muted)}
body.summary .ps-chips{display:flex;flex-wrap:wrap;gap:6px}
body.summary .ps-chip{display:inline-flex;gap:4px;border:1px solid var(--s-line);border-radius:999px;padding:3px 11px;font-size:12px;color:var(--s-muted);background:var(--s-card)}
body.summary .ps-chip::before{content:"\\2298";color:#C0392B;font-weight:700}
/* stat leaders */
body.summary .ps-leaders{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
body.summary .ps-leader{background:var(--s-card);border:1px solid var(--s-line);border-top:4px solid var(--s-accent);border-radius:4px;padding:18px 18px 16px}
body.summary .ps-leader .n{font:700 72px/1 "Barlow Condensed",sans-serif;font-variant-numeric:tabular-nums;color:var(--s-accent-ink);margin-top:6px}
body.summary .ps-leader .lab{font:600 12px/1.2 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--s-muted);margin-bottom:8px}
body.summary .ps-leader p{margin:0 0 6px;font-size:14px}
body.summary .ps-gso b{color:var(--s-accent-ink)}
body.summary .ps-gate{display:inline-block;font-size:12px;border-radius:999px;padding:1px 10px;border:1px solid var(--s-line)}
body.summary .ps-gate-met{border-color:#2F6B4F;color:var(--s-ok)}body.summary .ps-gate-no{border-color:#B04A1C;color:var(--s-watch)}
body.summary .ps-sub{font-size:12px;color:var(--s-muted);margin:14px 0 8px}
body.summary .ps-hs{display:inline-block;padding:1px 10px;border-radius:999px;font:700 11px/1.5 Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase}
body.summary .ps-hs-ok{background:var(--s-ok-bg);color:var(--s-ok)}body.summary .ps-hs-watch{background:var(--s-watch-bg);color:var(--s-watch)}body.summary .ps-hs-alert{background:var(--s-alert-bg);color:var(--s-alert)}
body.summary .ps-why{display:block;font-size:12px;color:var(--s-muted);margin-top:2px}
body.summary .ps-next{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline;margin-top:14px;padding:14px 18px;background:var(--s-ink-hero);color:var(--s-hero-ink);border-left:4px solid var(--s-accent);border-radius:0 4px 4px 0}
body.summary .ps-next b{font:700 12px/1 Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--s-accent)}
body.summary .ps-next span{flex:1;min-width:260px;font-size:15px}
body.summary .ps-gn{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;margin-right:8px;border-radius:50%;background:var(--s-ink-hero);color:var(--s-hero-ink);font:700 12px/1 Inter,sans-serif;vertical-align:middle}
body.summary .ps-tagchip{display:inline-block;font:700 11px/1.5 Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;border-radius:999px;padding:1px 10px;white-space:nowrap;text-decoration:none}
body.summary .ps-tag-changed{background:var(--s-accent);color:#04251a}
body.summary .ps-tag-watch{background:var(--s-watch-bg);color:var(--s-watch)}
/* motion */
@media (prefers-reduced-motion:no-preference){body.summary .ps-label,body.summary .vpersona,body.summary .ps-leader,body.summary .vroad .vrcard{transition:transform .15s,box-shadow .15s}
  body.summary .ps-label:hover,body.summary .vpersona:hover,body.summary .ps-leader:hover,body.summary .vroad .vrcard:hover{transform:translateY(-2px);box-shadow:var(--s-shadow)}}
/* footer */
body.summary .ps-foot{background:var(--s-ink-hero);color:var(--s-hero-muted);padding:28px 0;font-size:13px}
body.summary .ps-foot .ps-inner{display:flex;flex-wrap:wrap;gap:6px 24px;align-items:center}
body.summary .ps-foot a{color:var(--s-accent-2);text-decoration:none;font-weight:600}
@media screen and (max-width:900px){
  body.summary .ps-hero h1{font-size:40px}
  body.summary .ps-record{grid-template-columns:repeat(2,1fr)}
  body.summary .ps-rec:nth-child(3){border-left:0;padding-left:0}
  body.summary .ps-rec .n{font-size:44px}
  body.summary .ps-sh{flex-direction:column}
  body.summary .ps-sec h2{font-size:28px}
  body.summary .vpersonas,body.summary .ps-tiers,body.summary .ps-leaders,body.summary .ps-label .vrules{grid-template-columns:1fr}
  body.summary .ps-label summary{grid-template-columns:48px 1fr}
  body.summary #s-matrix .vproduct{overflow-x:auto}
  body.summary #s-matrix .vmatrix{min-width:560px}
  body.summary .ps-cells{grid-column:1 / -1}
  body.summary .ps-inner,body.summary .ps-story{padding-left:16px;padding-right:16px}
}
@page{size:letter portrait;margin:.5in}
/* phones (ADR-037): taps at least 44px tall, reading text at least 12px */
@media (max-width:719px){body.summary .ps-see{display:inline-flex;align-items:center;min-height:44px}body.summary .vrgap,body.summary .ps-tagchip{display:inline-flex;align-items:center;min-height:44px}
  body.summary .ps-sec .vtable thead th,body.summary .ps-sec .vmatrix thead th,body.summary .vm-pill,body.summary .vpersona .note,body.summary .ps-tag,body.summary .ps-hs,body.summary .ps-pos,body.summary .ps-tagchip{font-size:12px}body.summary .ps-foot a{display:inline-block;padding:10px 0}}
@media print{
  body.summary{--pz1:.63;--pz2:.54;--pz3:.46;--ph:250px;--pf:80px;-webkit-print-color-adjust:exact;print-color-adjust:exact;--s-bg:#fff;--s-card:#fff;--s-text:#1B2733;--s-muted:#4A5866;--s-line:#D5DBE1;--s-zebra:#f0f2f5;--s-ink-hero:#0b1726;--s-hero-ink:#fff;--s-hero-muted:#b4c0d0;--s-accent:#19b37a;--s-accent-ink:#0b7a52;--s-arrow:#0b1726;color-scheme:light}
  body.summary .ps-tabs,body.summary .ps-see,body.summary .ps-screen-only{display:none}
  body.summary table.ps-print-only{display:table}
  body.summary .vm-link{display:none}
  body.summary .ps-hero{zoom:var(--pz1);width:calc(720px / var(--pz1));height:var(--ph);overflow:hidden;padding:20px 0 0}
  body.summary .ps-hero .ps-inner,body.summary .ps-story{max-width:none;padding-left:0;padding-right:0}
  body.summary .ps-hero h1{font-size:44px}
  body.summary .ps-pitch{margin-top:6px;font-size:14px}
  body.summary .ps-badge{margin-top:8px}
  body.summary .ps-record{margin-top:10px}
  body.summary .ps-rec{padding:8px 0 0 16px}.ps-rec .n{font-size:36px}
  body.summary .ps-hero .ps-inner{padding-left:20px;padding-right:20px}
  body.summary .ps-story{padding-top:0;padding-bottom:0}
  body.summary .ps-p1{zoom:var(--pz1);width:calc(720px / var(--pz1));height:calc(960px / var(--pz1) - var(--ph));overflow:hidden;break-after:page;padding-top:16px}
  body.summary .ps-p2{zoom:var(--pz2);width:calc(720px / var(--pz2));height:calc(960px / var(--pz2));overflow:hidden;break-after:page}
  body.summary .ps-p3{zoom:var(--pz3);width:calc(720px / var(--pz3));height:calc(960px / var(--pz3) - var(--pf));overflow:hidden}
  body.summary .ps-foot{zoom:var(--pz3);width:calc(720px / var(--pz3));height:var(--pf);overflow:hidden;padding:14px 0}
  body.summary .ps-foot .ps-inner{padding-left:20px;padding-right:20px;max-width:none}
  body.summary .ps-sec{margin-bottom:28px}
  body.summary .ps-sec h2{font-size:28px}
  body.summary .ps-line{margin-bottom:8px}
  body.summary .vr-head,body.summary .vr-lane{grid-template-columns:170px repeat(4,minmax(0,1fr))}
  body.summary .vr-head{display:grid}
  body.summary .vr-cell:empty,body.summary .vr-cell:not(:has(*)){display:flex}
  body.summary .vr-cell::before{content:none}
  body.summary .ps-tiers{grid-template-columns:repeat(4,1fr)}
  body.summary .ps-leaders{grid-template-columns:repeat(3,1fr)}
  body.summary .ps-leader .n{font-size:56px}
  body.summary .vdep{max-height:300px}
  body.summary .vtable td,body.summary .vtable tbody th,body.summary .vmatrix td,body.summary .vmatrix tbody th{height:30px;padding:3px 10px}
  body.summary .ps-next,body.summary .ps-hero,body.summary .ps-tier,body.summary .vroad,body.summary .vroad .vr-colhead,body.summary .vtable thead th,body.summary .vmatrix thead th,body.summary .ps-foot,body.summary .vpersona .vmono{-webkit-print-color-adjust:exact;print-color-adjust:exact}
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
             ("labels", labels_component(c, data, vals)),
             ("priorities", site_tables.enhance(sp.prioritization_html(rows_of(data, "product_prioritization"), static={"products": names}))),
             ("roadmap", sp.roadmap_board_html(rows_of(data, "roadmap"), ps, d10, {}, static=True, gap_marks=marks)),
             ("privacy", tiers_component(c, data, vals)),
             ("working", working_component(c, data, vals)),
             ("gaps", gaps_html),
             ("learned", learned_component(c, vals))]
    secs = [section(i, c, k, vals, comp) for i, (k, comp) in enumerate(comps, 1)]
    rl = c["record_labels"]
    rec = [("products", vals["n_products"]), ("gates", f"{vals['n_met']}/{vals['n_gates']}"), ("fans", f"~{vals['fans_created']}"), ("breaks", vals["n_boundary"])]
    record = "".join(f"<div class='ps-rec'><div class='n'>{e(v)}</div><div class='l'>{e(rl[k])}</div></div>" for k, v in rec)
    hero = (f"<header class='ps-hero'><div class='ps-inner'><p class='ps-eyebrow'>{e(fill(c['eyebrow'], vals))}</p><h1>{e(c['title'])}</h1><span class='ps-badge'>{e(c['synthetic_badge'])}</span>"
            f"<p class='ps-pitch'>{e(c['pitch'])}</p><div class='ps-record'>{record}</div></div></header>")
    tabs = "<nav class='ps-tabs' aria-label='Sections'><div class='ps-inner'>" + "".join(f"<a href='#{e(t['id'])}'{' class=on' if i == 0 else ''}>{e(t['label'])}</a>" for i, t in enumerate(c["tabs"])) + "</div></nav>"
    foot = (f"<footer class='ps-foot'><div class='ps-inner'><span>{e(c['disclaimer'])}</span><span>{e(c['footer'])}</span><span>{e(fill(c['methodology'], {'version': str(version)}))}</span>"
            f"<a href='product.html'>{e(c['footer_link'])} &rarr;</a></div></footer>")
    grid = f"<div class='ps-p1'>{''.join(secs[:3])}</div><div class='ps-p2'>{''.join(secs[3:6])}</div><div class='ps-p3'>{''.join(secs[6:])}</div>"
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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;700&family=Barlow+Condensed:wght@600;700&family=Inter:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="css/tokens.css">
<link rel="stylesheet" href="css/site.css">
<link rel="stylesheet" href="assets/viewer.css">
<script>try{{var t=localStorage.getItem("cff-theme");if(t==="light"||t==="dark"){{document.documentElement.dataset.theme=t}}}}catch(e){{}}</script>
<style>{CSS}</style>
</head>
<body class="ps summary">
{hero}
{tabs}
<main class="ps-story" id="main">
{grid}
</main>
{foot}
<script>/* progressive enhancement: where the browser lacks exclusive <details name>, opening one closes the others. It only toggles open; it computes nothing. */
document.querySelectorAll('details[name=dp-label]').forEach(function(d){{d.addEventListener('toggle',function(){{if(d.open&&!('name' in HTMLDetailsElement.prototype)){{document.querySelectorAll('details[name=dp-label]').forEach(function(o){{if(o!==d)o.open=false}})}}}})}});
</script>
<script>/* active tab follows the scroll; no data logic */
(function(){{var links=[].slice.call(document.querySelectorAll('.ps-tabs a'));var map={{}};links.forEach(function(a){{map[a.getAttribute('href').slice(1)]=a}});if(!('IntersectionObserver' in window))return;var obs=new IntersectionObserver(function(es){{es.forEach(function(en){{if(en.isIntersecting){{links.forEach(function(l){{l.classList.remove('on')}});var a=map[en.target.id];if(a)a.classList.add('on')}}}})}},{{rootMargin:'-25% 0px -65% 0px'}});Object.keys(map).forEach(function(id){{var el=document.getElementById(id);if(el)obs.observe(el)}});}})();
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
