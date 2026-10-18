"""The Data product tab (Phase 6, section 7): cards and viewer slides for the portfolio, built from products/*/product.yml, the seeds, the Phase 6 marts and the docs.

Every number on the tab comes from a share, a mart, a seed or a product spec; nothing is computed here beyond formatting. Product cards read product.yml and the live quality grade from the scorecards
at build time (scripts/validate_products.resolve_quality). Copy lives in site_src/copy/charts.yml (entries D1 to D9) under the same draft rules as the other pages.
"""
from __future__ import annotations

import re
from html import escape as e
from pathlib import Path

import yaml

from scripts import validate_products as vp

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/anna-malakhova-anna/football-project-next-gen/blob/main/"
GOALS = {"G1": "Grow NFL presence globally through flag football",
         "G2": "Grow flag football popularity in the US as a safe, accessible way into the sport, alongside tackle football",
         "G3": "Track conversion of flag participants (and their families) to NFL fans, while protecting children: no direct marketing to kids, age-specific consent rules, and guardian consent"}
VALUE_WORD = {"driver": "Driver", "enabler": "Enabler", "utility": "Utility"}
STATUS_WORD = {"mvp": "MVP", "proposed": "Proposed", "active": "Active", "deprecated": "Deprecated", "retired": "Retired"}
TYPE_WORD = {"source-based": "Source-based", "master": "Master", "insights": "Insights"}


def link(path: str, label: str | None = None) -> str:
    """A repo artifact as a link. Only paths that exist in the repo are linked."""
    p = path.split("#")[0]
    if p.startswith("http"):
        return f'<a href="{e(path)}">{e(label or path)}</a>'
    target = (ROOT / p)
    href = REPO + path if target.exists() else None
    return f'<a href="{e(href)}"><code>{e(label or path)}</code></a>' if href else f"<code>{e(label or path)}</code>"


def md_inline(text: str, base: str = "docs/product") -> str:
    """A tiny, safe converter for the table cells in our own docs: escape first, then [text](relative/path), `code` and **bold**."""
    out = e(text)

    def sub(m):
        label, tgt = m.group(1), m.group(2)
        if tgt.startswith("http"):
            return f'<a href="{tgt}">{label}</a>'
        resolved = (Path(base) / tgt).as_posix()
        norm = str((ROOT / resolved).resolve().relative_to(ROOT)) if (ROOT / resolved).resolve().exists() else None
        return f'<a href="{e(REPO + norm)}">{label}</a>' if norm else label
    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", sub, out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<i>\1</i>", out)
    return out


def md_table(path: Path) -> list[list[str]]:
    """The first markdown table of a file as a list of rows (header row first, separator dropped)."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            rows.append(cells)
        elif rows:
            break
    return rows


def products() -> dict[str, dict]:
    return vp.load()


# ---------------------------------------------------------------- D1 goals to products
SHORT_GOALS = {"G1": "Grow NFL presence globally", "G2": "Grow flag in the US", "G3": "Track conversion to fans, protecting children"}


def matrix_html(ps: dict, compact: bool = False) -> str:
    head = "".join(f"<th scope='col'>{e(pid)}" + ("" if compact else f"<br><span class='note'>{e(p['name'])}</span>") + "</th>" for pid, p in ps.items())
    body = ""
    for g, text in GOALS.items():
        cells = "".join(f"<td class='vm-{p['value_proposition']}'>{VALUE_WORD[p['value_proposition']] if g in p['goals'] else '&nbsp;'}</td>" for p in ps.values())
        body += f"<tr><th scope='row'><b>{g}</b> {e(SHORT_GOALS[g] if compact else text)}</th>{cells}</tr>"
    note = "" if compact else "<p class='note'>Driver: moves the goal directly. Enabler: makes other products possible. Utility: keeps things running.</p>"
    return f"<div class='vproduct'><table class='vmatrix'><thead><tr><th>Goal</th>{head}</tr></thead><tbody>{body}</tbody></table>{note}</div>"


def dependency_svg() -> str:
    box = lambda x, y, w, t, sub, cls: (f"<g><rect x='{x}' y='{y}' width='{w}' height='54' rx='4' class='{cls}'/><text x='{x + w / 2}' y='{y + 22}' text-anchor='middle' class='dt'>{e(t)}</text>"  # noqa: E731
                                        f"<text x='{x + w / 2}' y='{y + 40}' text-anchor='middle' class='ds'>{e(sub)}</text></g>")
    arrow = lambda x1, y1, x2, y2: f"<path d='M{x1} {y1} L{x2} {y2}' class='da' marker-end='url(#ar)'/>"  # noqa: E731
    svg = ("<svg data-diagram='dependencies' viewBox='0 0 900 400' role='img' aria-label='Dependencies: Intake feeds the master; the master feeds global, US and conversion insights; conversion also needs the fan feed and consent capture' class='vdep'>"
           "<defs><marker id='ar' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto'><path d='M0 0 L10 5 L0 10 z' class='dah'/></marker></defs>"
           + box(10, 143, 190, "DP1 Intake", "source-based", "db-util") + arrow(200, 170, 260, 170)
           + box(260, 143, 280, "DP2 Participant and household master", "master, restricted", "db-en")
           + arrow(540, 160, 610, 62) + arrow(540, 170, 610, 170) + arrow(540, 180, 610, 270)
           + box(610, 35, 280, "DP3 Global participation", "insights, drives G1", "db-dr") + box(610, 143, 280, "DP4 US growth and club markets", "insights, drives G2 (MVP with DP1)", "db-dr")
           + box(610, 243, 280, "DP5 Flag-to-fan conversion", "insights (restricted), drives G3", "db-dr")
           + box(310, 293, 230, "Fan engagement feed", "an outside source", "db-src") + arrow(540, 320, 610, 296)
           + "<path d='M105 197 C105 372 750 372 750 297' class='da dd' marker-end='url(#ar)' fill='none'/>"
           + "<text x='430' y='392' text-anchor='middle' class='ds'>consent capture at registration (DP1) is a precondition for DP5</text></svg>")
    return f"<div class='vproduct'>{svg}</div>"


# ---------------------------------------------------------------- D2 the method
STAGES = [("Prework", "Who is the customer, what is the value, who consumes it and how, what type of product is it, who owns it, what does it depend on. Nothing is built before this is answered.",
           ["docs/product/discovery.md", "products/DP4/canvas.md", "docs/product/roles.md"]),
          ("Plan and design", "A vision, a minimum viable product and a now, next, later roadmap; how the products feed each other; a versioning rule; an honest check of what the organization can support.",
           ["docs/product/roadmap.md", "docs/product/reference-design.md", "docs/product/maturity.md", "dbt/seeds/product_prioritization.csv"]),
          ("Engineer and operationalize", "Pipelines, metadata and the governance policies: definitions, ethics, lifecycle, quality, security and privacy.",
           ["dbt/models", "docs/playbook/onboard-a-source.md", "docs/product/governance-coverage.md", "docs/product/age-consent-rules.md"]),
          ("Package and deliver", "One label per product: name, version, quality grade, type, owner, consumers, terms and support; a delivery channel, release management and a retirement plan.",
           ["products/DP4/product.yml", "docs/product/terms/DP4.md", "products/CHANGELOG.md", "docs/product/decommission-example.md"]),
          ("Monitor and observe", "Two separate views: inside (is the product healthy) and outside (is anyone using it, and is it moving the goal).",
           ["scripts/build_product_health.py", "dbt/models/phase6/mart_goal_scorecard.sql", "docs/product/feedback-loop.md"])]


def stepper_html() -> str:
    cards = "".join(f"<li class='vstage'><span class='vstage-n'>{i}</span><h4>{e(t)}</h4><p>{e(d)}</p><p class='note'>{' '.join(link(a) for a in arts)}</p></li>" for i, (t, d, arts) in enumerate(STAGES, 1))
    return f"<div class='vproduct'><ol class='vstepper'>{cards}</ol><p class='note'><b>Product, not project.</b> A project ends at delivery. A product has an owner, users, versions, health measures and a retirement plan.</p></div>"


# ---------------------------------------------------------------- D3 discovery
def personas_html(compact: bool) -> str:
    rows = md_table(ROOT / "docs/product/discovery.md")[1:]
    cards = ""
    for persona, goal, job, pain, questions in rows:
        extra = "" if compact else f"<p><b>What we assumed:</b> {md_inline(pain)}</p><p><b>What we would ask:</b> {md_inline(questions)}</p>"
        cards += f"<div class='vpersona'><h4>{md_inline(persona)}</h4><p class='note'>Serves {md_inline(goal)}</p><p>{md_inline(job)}</p>{extra}</div>"
    note = "" if compact else "<p class='note'>There are no real users. These are assumption-based personas with the questions we would validate in real interviews. The league operator is a supplier, not a consumer.</p>"
    return f"<div class='vproduct'><div class='vpersonas{' vcompact' if compact else ''}'>{cards}</div>{note}</div>"


# ---------------------------------------------------------------- D4 prioritization and roadmap
def prioritization_html(rows: list[dict]) -> str:
    body = ""
    for r in rows:
        total = r["value_to_goals"] + r["feasibility_today"] + r["data_readiness"] - r["privacy_risk"]
        body += (f"<tr><th scope='row'>{e(r['product_id'])} {e(r['product_name'])}</th><td>{r['value_to_goals']}</td><td>{r['feasibility_today']}</td><td>{r['data_readiness']}</td><td>{r['privacy_risk']}</td>"
                 f"<td><b>{total}</b></td><td>{e(r['reading'])}</td></tr>")
    return ("<div class='vproduct'><table class='vtable'><thead><tr><th>Product</th><th>Value to the goals</th><th>Feasibility today</th><th>Data readiness</th><th>Privacy risk (higher is riskier)</th><th>Total</th><th>Reading</th></tr></thead>"
            f"<tbody>{body}</tbody></table><p class='note'>Scores 1 to 5 and DRAFT: proposed from the data quality grades, set by the program owner. Total = value + feasibility + readiness - privacy risk.</p></div>")


def roadmap_html(targets: list[dict]) -> str:
    rows = md_table(ROOT / "docs/product/roadmap.md")
    # the Now / Next / Later table is the one whose header starts with Horizon
    lines = (ROOT / "docs/product/roadmap.md").read_text(encoding="utf-8").splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("| Horizon"))
    table = []
    for l in lines[i:]:
        if not l.startswith("|"):
            break
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        table.append(cells)
    cols = {"Now": [], "Next": [], "Later": []}
    for horizon, release, content, _exit in table[1:]:
        key = re.sub(r"\*", "", horizon)
        norm = lambda x: re.sub(r"[^a-z0-9,]", "", re.sub(r"\(the mvp\)|\(mvp\)", "", x.lower().replace("+", ",").replace("*", "")))  # noqa: E731
        crit = [t for t in targets if norm(t["release"]) == norm(release)]
        items = "".join(f"<li>{e(t['metric'])}: {e(t['comparison'])} <b>{t['threshold_value']:g}</b> {e(t['unit'])}"
                        f"{' (guardrail, alert on breach)' if t['kind'] == 'GUARDRAIL' else ''}<span class='note'> from {t['baseline_2025']:g} today ({e(t['status'].lower())})</span></li>" for t in crit)
        cols[key].append(f"<div class='vrelease'><h5>{md_inline(release)}</h5><p>{md_inline(content)}</p><ul>{items}</ul></div>")
    board = "".join(f"<div class='vcol'><h4>{k}</h4>{''.join(v)}</div>" for k, v in cols.items())
    return (f"<div class='vproduct'><div class='vboard'>{board}</div><p class='note'>No dates: now, next, later. The thresholds are draft values from the program owner, with the 2025 baseline beside each; "
            "the exit rows with no threshold have none yet.</p></div>")


# ---------------------------------------------------------------- D5 product labels
def label_html(pid: str, p: dict, spec_row: dict, full: bool) -> str:
    q = spec_row
    ports = "".join(f"<li><code>{e(pt['model'])}</code> <span class='note'>{e(pt['audience'])} audience, {e(pt['grain'])}, {e(pt['refresh'])}</span></li>" for pt in p["output_ports"])
    consumers = "".join(f"<li><b>{e(c['role'])}:</b> {e(c['use_case'])}</li>" for c in p["consumers"])
    head = (f"<div class='vlabel-head'><h4>{e(pid)} {e(p['name'])}</h4><p class='note'>v{e(p['version'])} · {TYPE_WORD[p['type']]} · {STATUS_WORD[p['status']]} · {VALUE_WORD[p['value_proposition']]} for {', '.join(p['goals'])}</p></div>")
    grade = f"<p class='vlabel-grade'><span class='vq'>Live quality</span> {e(q['quality_text'])}</p>"
    base = f"{head}{grade}<p>{e(p['description'])}</p><p><b>Owner:</b> {e(p['owner_role'])}</p><p><b>Privacy class:</b> {e(p['classification'])}</p><p><b>Terms:</b> {link(p['terms_of_use'])}</p>"
    evidence = {"DP4": [("audience.html", "Audience"), ("markets.html", "Club markets")], "DP5": [("acquisition.html", "Acquisition"), ("value.html", "Value"), ("audience.html", "Audience")]}.get(pid)
    ev = "<p><b>Detailed evidence:</b> " + ", ".join(f'<a href="{h}">{l}</a>' for h, l in evidence) + " pages.</p>" if evidence else ""
    if not full:
        return f"<div class='vlabel vlabel-small'>{head}{grade}<p class='note'>{e(p['consumers'][0]['role'])}</p></div>"
    prohibited = "".join(f"<li>{e(u['use'])} <span class='note'>enforced by {', '.join(e(x['name']) for x in u['enforced_by'])}</span></li>" for u in p["privacy"]["prohibited_uses"])
    return (f"<div class='vproduct'><div class='vlabel'>{base}{ev}<h5>Consumers</h5><ul>{consumers}</ul><h5>Output ports</h5><ul>{ports}</ul>"
            f"<h5>Prohibited uses and what enforces them</h5><ul>{prohibited}</ul>"
            f"<p><b>Shelf life:</b> {e(p['shelf_life'])}. <b>Decommission:</b> {link(p['decommission_plan'])}. <b>Support:</b> {e(p['support_contact'])}. <b>Pricing:</b> {e(p['pricing'])}</p>"
            f"<p class='note'>Fictional roles. The quality grade is read from the scorecards at build time, never typed.</p></div></div>")


# ---------------------------------------------------------------- D6 kids' privacy
TIERS = [("U13", "Under 13", "0 to 12"), ("13_15", "13 to 15", "13 to 15"), ("16_17", "16 to 17", "16 and 17"), ("ADULT", "18 and over", "18 and over")]
PURPOSE_PLAIN = {"LEAGUE_OPS": "running the league", "LEAGUE_COMMS": "league messages", "PHOTO_MEDIA": "photos and media", "CLUB_MARKETING": "club marketing", "PARTNER_DISCLOSURE": "passing data to a partner", "PROFILING": "profiling"}


def tiers_html(rules: list[dict]) -> str:
    cards = ""
    for code, label, ages in TIERS:
        rs = [r for r in rules if (r["age_max"] < 18 if code != "ADULT" else r["age_max"] >= 100) and (code == "ADULT" or (r["age_min"] <= {"U13": 5, "13_15": 14, "16_17": 17}[code] <= r["age_max"]))]
        who = sorted({r["who_consents"] for r in rs}) or ["?"]
        allowed = sorted({p for r in rs for p in (r["allowed_purposes"] or "").split("|") if p})
        prohibited = sorted({p for r in rs for p in (r["prohibited_purposes"] or "").split("|") if p})
        cards += (f"<div class='vtier vtier-{code}'><h4>{e(label)}</h4><p><b>Who consents:</b> {'the guardian' if who == ['GUARDIAN'] else 'the person themselves, with fresh consent at 18'}</p>"
                  f"<p><b>Can be asked, with consent:</b> {e(', '.join(PURPOSE_PLAIN[p] for p in allowed if p not in prohibited))}</p>"
                  f"<p class='vnever'><b>Never:</b> {e(', '.join(PURPOSE_PLAIN[p] for p in prohibited)) if prohibited else 'nothing is barred outright; every purpose still needs consent'}{'; no marketing to the child' if code != 'ADULT' else ''}</p></div>")
    return f"<div class='vproduct'><div class='vtiers'>{cards}</div><p class='note'>Project policy informed by public rules, not legal advice. Where a rule is unknown the strictest row applies.</p></div>"


def household_html() -> str:
    return ("<div class='vproduct'><div class='vrules'><div><h4>Household, not child</h4><p>A permission is judged for the <b>guardian</b> of a household and never passes to a child. "
            "The <b>youngest child governs</b>: a message that says \"your child plays in our league\" is about the child. A blank is never a yes.</p></div>"
            "<div><h4>Analytics is not activation</h4><p>Counting linked households moves nobody onto a contact list. Only the last step of the funnel, a guardian who agreed to club marketing, uses consent. "
            "Whether a club counts as a third party is an open question for counsel; nothing here decides it.</p></div>"
            "<div><h4>Fresh consent at 18</h4><p>An adult becomes their own fan record only with fresh consent. Their youth profile does not carry over, so the youth-to-adult step is <b>not measurable by design</b>.</p></div></div></div>")


def unverified_html(rules: list[dict]) -> str:
    by: dict[str, list[str]] = {}
    for r in rules:
        if r["verified"] != "Y":
            by.setdefault(r["jurisdiction"], []).append(f"{r['age_min']} to {r['age_max']}")
    names = {"US_FED": "United States (federal)", "US_CA": "California", "CA_QC": "Quebec", "CA_OTHER": "Canada (other)", "EU": "EU countries (Austria, Germany)", "GB": "United Kingdom", "DEFAULT": "Everywhere else (Mexico, Japan, Panama)"}
    items = "".join(f"<li><b>{e(names.get(j, j))}:</b> not yet verified for ages {e(', '.join(a))}</li>" for j, a in by.items())
    return ("<div class='vproduct'><h4>Open items: rules not yet verified</h4>"
            f"<ul>{items}</ul><p class='note'>Every row is still unverified and has no source link yet. The strictest row applies where unsure, so these gaps make the rules stricter, not looser. {link('docs/product/age-consent-rules.md', 'The full table')}.</p></div>")


def funnel_spec(thumb: bool) -> dict:
    colors = {"domain": ["U13", "13_15", "16_17", "ADULT", "UNKNOWN"], "range": ["#2166ac", "#92c5de", "#f4a582", "#b2182b", "#8A96A3"]}
    return {"data": {"url": "data/conv_tier.json", "format": {"type": "json", "property": "rows"}}, "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"},
            "padding": {"left": 4, "right": 12, "top": 4, "bottom": 4}, "transform": [{"filter": "datum.step_no > 1 && datum.tier_label !== 'Age not known'"}],
            "mark": {"type": "bar", "clip": True},
            "encoding": {"y": {"field": "step", "type": "nominal", "sort": {"field": "step_no", "op": "min"}, "title": None, "axis": {"labelLimit": 300, "labelFontSize": 11 if thumb else 14}},
                         "yOffset": {"field": "tier_label", "type": "nominal", "sort": {"field": "tier_order", "op": "min"}},
                         "x": {"field": "share_of_registered", "type": "quantitative", "title": None if thumb else "Share of registered households in the tier", "axis": {"format": "%", "tickCount": 5}},
                         "color": {"field": "tier_label", "type": "nominal", "title": None, "scale": {"domain": ["Under 13", "13 to 15", "16 to 17", "18 and over"], "range": colors["range"][:4]}, "legend": {"orient": "top", "labelFontSize": 11 if thumb else 13}},
                         "tooltip": [{"field": "tier_label", "title": "Age tier of the youngest child"}, {"field": "step", "title": "Step"}, {"field": "households_text", "title": "Households"}, {"field": "kind_text", "title": "Kind"}]}}


# ---------------------------------------------------------------- D7 is it working
AREA_LABEL = {"quality": "Quality", "freshness": "Freshness", "contract_status": "Contracts", "pipeline": "Pipeline", "trust": "Trust", "privacy": "Privacy", "cost": "Cost proxy"}
STATUS_CLASS = {"OK": "ok", "WATCH": "watch", "ALERT": "alert", "INFO": "info"}
STATUS_TEXT = {"OK": "OK", "WATCH": "Watch", "ALERT": "Alert", "INFO": "Info"}


def health_html(rows: list[dict], ps: dict, compact: bool) -> str:
    cards = ""
    for pid, p in ps.items():
        mine = [r for r in rows if r["product_id"] == pid]
        lines = "".join(f"<tr><th scope='row'>{AREA_LABEL.get(r['area'], r['area'])}</th><td>{e(r['measure'])}</td><td><b>{e(r['value_text'])}</b></td><td><span class='vstat vstat-{STATUS_CLASS[r['status']]}'>{STATUS_TEXT[r['status']]}</span></td></tr>"
                        for r in mine if not compact or r["area"] in ("quality", "trust", "privacy"))
        cards += f"<div class='vhealth'><h4>{e(pid)} {e(p['name'])}</h4><table class='vtable vtable-tight'><tbody>{lines}</tbody></table></div>"
    note = "" if compact else "<p class='note'>Inside view: is each product healthy? Read from the scorecards, the contract results, the share checks and the dbt run history after the latest build. The cost is a proxy (model run time), not money.</p>"
    return f"<div class='vproduct'><div class='vhealths{' vcompact' if compact else ''}'>{cards}</div>{note}</div>"


def fmt(v, unit):
    """Format a value for display: ratios as whole-or-one-decimal percents, percents with a sign, counts with separators. A missing value says so."""
    if v is None:
        return "not shown"
    if unit == "ratio":
        return f"{v:.1%}"
    if unit == "percent":
        return f"{v:g}%"
    if unit == "per_100":
        return f"{v:.1f} per 100"
    return f"{v:,.1f}" if (isinstance(v, float) and not float(v).is_integer()) else f"{v:,.0f}"


KPI_ORDER = ["fan_engagement_uplift", "fans_created_by_flag", "fans_created_per_100_households", "linked_household_rate", "activatable_households", "youth_to_adult_fan_transition"]


def scorecard_html(rows: list[dict], compact: bool) -> str:
    seg_names = {"U13": "under 13", "13_15": "13 to 15", "16_17": "16 to 17", "ADULT": "18 and over", "UNKNOWN": "age not known"}
    body, last = "", None
    rows = sorted(rows, key=lambda r: (r["goal_id"], KPI_ORDER.index(r["kpi_id"]) if r["kpi_id"] in KPI_ORDER else -1, str(r["segment"]), r["kpi_id"]))
    for r in rows:
        if r["year"] is not None and compact and r["goal_id"] == "G1" and r["kpi_id"] not in ("global_participants",):
            continue
        if r["goal_id"] != last:
            body += f"<tr class='vgoal'><th colspan='4'>{e(r['goal_id'])}: {e(GOALS[r['goal_id']].split(' as a safe')[0].split(', while')[0])}</th></tr>"
            last = r["goal_id"]
        label = r["kpi_label"] + (f" ({seg_names.get(r['segment'], r['segment'])})" if r["segment"] else "")
        if r["status"] == "NOT_MEASURABLE_BY_DESIGN":
            val = "<b>not measurable by design</b>"
        elif r["status"] == "SUPPRESSED":
            val = "hidden: fewer than 10"
        else:
            rng = f" <span class='note'>({fmt(r['value_low'], r['unit'])} to {fmt(r['value_high'], r['unit'])})</span>" if r["value_low"] is not None and r["value_high"] is not None else ""
            val = f"<b>{fmt(r['value'], r['unit'])}</b>{rng}"
        trust = f"{e(r['trust_label'])}: <b>{fmt(r['trust_value'], r['trust_unit']) if r['trust_value'] is not None else 'not shown'}</b>"
        body += f"<tr><td>{e(label)}</td><td>{val}</td><td class='note'>{trust}</td><td><a href='#view=D8-1'>{e(r['product_id'])}</a></td></tr>"
    return ("<div class='vproduct'><table class='vtable'><thead><tr><th>KPI</th><th>Latest</th><th>Data-trust companion</th><th>Product</th></tr></thead>"
            f"<tbody>{body}</tbody></table><p class='note'>Outside view: is the portfolio moving the goals? Built from existing marts only. The uplift in G3 is the matched estimate; its naive companion overstates.</p></div>")


def adoption_html(rows: list[dict]) -> str:
    stages = ["Find", "Activate", "Retain", "Refer", "Financial impact"]
    head = "".join(f"<th>{s}</th>" for s in stages)
    body = ""
    for pid in sorted({r["product_id"] for r in rows}):
        cells = ""
        for s in stages:
            r = next(x for x in rows if x["product_id"] == pid and x["stage"] == s)
            cells += f"<td><span class='vstat vstat-info'>Instrumented, awaiting real users</span><span class='note'> {r['real_events']} events</span></td>"
        body += f"<tr><th scope='row'>{e(pid)}</th>{cells}</tr>"
    return (f"<div class='vproduct'><table class='vtable'><thead><tr><th>Product</th>{head}</tr></thead><tbody>{body}</tbody></table>"
            "<p class='note'>There are no real users, so nothing is shown that was not observed. The usage log is defined and a logging stub exists; simulated usage would be badged \"Simulated usage, no real users\" and has not been approved.</p></div>")


def _inner(block: str) -> str:
    """The content of a '<div class="vproduct">...</div>' block, so two blocks can sit side by side."""
    open_tag = "<div class='vproduct'>"
    return block[len(open_tag):-len("</div>")] if block.startswith(open_tag) else block


def working_pair_html(health_rows, score_rows, ps) -> str:
    inside, outside = _inner(health_html(health_rows, ps, True)), _inner(scorecard_html(score_rows, True))
    return f"<div class='vproduct'><div class='vpair'><div><h4>Inside: product health</h4>{inside}</div><div><h4>Outside: goal scorecard</h4>{outside}</div></div></div>"


# ---------------------------------------------------------------- D8 governance, D9 loop and changelog
def governance_html() -> str:
    rows = md_table(ROOT / "docs/product/governance-coverage.md")
    head = "".join(f"<th>{e(c)}</th>" for c in rows[0])
    body = ""
    for r in rows[1:]:
        gap = "<span class='vstat vstat-alert'>GAP</span>"
        cells = "".join((f"<th scope='row'>{md_inline(c)}</th>" if i == 0 else "<td>" + md_inline(c).replace("GAP", gap) + "</td>") for i, c in enumerate(r))
        body += f"<tr>{cells}</tr>"
    return (f"<div class='vproduct'><div class='vscrollx'><table class='vtable vgov'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
            "<p class='note'>A gap is honest output: it is what a real organization would still have to build.</p></div>")


def loop_html() -> str:
    text = (ROOT / "docs/product/feedback-loop.md").read_text(encoding="utf-8")
    steps = re.findall(r"^\d\. \*\*([^*]+)\*\*\s*(.+)$", text, flags=re.M)
    items = "".join(f"<li><b>{md_inline(t)}</b> {md_inline(d)}</li>" for t, d in steps)
    return f"<div class='vproduct'><ol class='vloop'>{items}</ol><p class='note'>The first four links are real outputs of this build (the fourth is a labelled simulation); the last is a proposal.</p></div>"


def changelog_html() -> str:
    rows = md_table(ROOT / "products/CHANGELOG.md")
    head = "".join(f"<th>{e(c)}</th>" for c in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{md_inline(c, 'products')}</td>" for c in r) + "</tr>" for r in rows[1:])
    return f"<div class='vproduct'><div class='vscrollx'><table class='vtable'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div><p class='note'>Methodology version stays 2.0: no counting rule and no published KPI changed.</p></div>"


# ---------------------------------------------------------------- the cards
def charts() -> dict:
    ps = products()
    spec = lambda d, pid: next(r for r in d["product_specs"]["rows"] if r["id"] == pid)  # noqa: E731
    C: dict = {}

    C["d1_goals"] = dict(page="product", title="Goals to products", datasets=["product_prioritization"],
        card=dict(id="D1", datasets=["product_prioritization"], thumb_html=lambda d: matrix_html(ps, True), open_slide=1,
                  slides=lambda d: [dict(title="Goals by products", key="MATRIX", html=lambda dd: matrix_html(ps)), dict(title="What feeds what", key="DEPS", html=lambda dd: dependency_svg())]))
    C["d2_method"] = dict(page="product", title="The method in five stages", datasets=["product_prioritization"],
        card=dict(id="D2", datasets=["product_prioritization"], thumb_html=lambda d: stepper_html(), open_slide=1, slides=lambda d: [dict(title="Five stages", key="STAGES", html=lambda dd: stepper_html())]))
    C["d3_discovery"] = dict(page="product", title="Who the products are for", datasets=["product_prioritization"],
        card=dict(id="D3", datasets=["product_prioritization"], thumb_html=lambda d: personas_html(True), open_slide=1, slides=lambda d: [dict(title="Six personas and what we would ask", key="PERSONAS", html=lambda dd: personas_html(False))]))
    C["d4_mvp"] = dict(page="product", title="The MVP and the roadmap", datasets=["product_prioritization", "product_targets"],
        card=dict(id="D4", datasets=["product_prioritization", "product_targets"], thumb_html=lambda d: prioritization_html(d["product_prioritization"]["rows"]), open_slide=1,
                  slides=lambda d: [dict(title="Priorities", key="PRIO", html=lambda dd: prioritization_html(dd["product_prioritization"]["rows"])), dict(title="Now, next, later", key="ROADMAP", html=lambda dd: roadmap_html(dd["product_targets"]["rows"]))]))
    C["d5_labels"] = dict(page="product", title="The five products", datasets=["product_specs"],
        card=dict(id="D5", datasets=["product_specs"], thumb_html=lambda d: "<div class='vlabels'>" + "".join(label_html(pid, p, spec(d, pid), False) for pid, p in ps.items()) + "</div>", open_slide=1,
                  slides=lambda d: [dict(title=f"{pid} {p['name']}", key="LABEL", html=(lambda pid, p: lambda dd: label_html(pid, p, spec(dd, pid), True))(pid, p)) for pid, p in ps.items()]))
    C["d6_kids"] = dict(page="product", title="Children's privacy, by age", datasets=["age_rules", "conv_tier"],
        card=dict(id="D6", datasets=["age_rules", "conv_tier"], thumb=funnel_spec(True), open_slide=1,
                  slides=lambda d: [dict(title="Four age tiers", key="TIERS", html=lambda dd: tiers_html(dd["age_rules"]["rows"])), dict(title="Household, not child", key="RULES", html=lambda dd: household_html()),
                                    dict(title="The funnel by age tier", key="FUNNEL", spec=funnel_spec(False)), dict(title="Rules still to verify", key="OPEN", html=lambda dd: unverified_html(dd["age_rules"]["rows"]))]))
    C["d7_working"] = dict(page="product", title="Is it working?", datasets=["product_health", "goal_scorecard", "product_adoption"],
        card=dict(id="D7", datasets=["product_health", "goal_scorecard", "product_adoption"], thumb_html=lambda d: working_pair_html(d["product_health"]["rows"], d["goal_scorecard"]["rows"], ps), open_slide=1,
                  slides=lambda d: [dict(title="Product health (inside)", key="HEALTH", html=lambda dd: health_html(dd["product_health"]["rows"], ps, False)),
                                    dict(title="Goal scorecard (outside)", key="SCORE", html=lambda dd: scorecard_html(dd["goal_scorecard"]["rows"], False)),
                                    dict(title="Adoption", key="ADOPT", html=lambda dd: adoption_html(dd["product_adoption"]["rows"]))]))
    C["d8_governance"] = dict(page="product", title="Governance coverage", datasets=["product_prioritization"],
        card=dict(id="D8", datasets=["product_prioritization"], thumb_html=lambda d: governance_html(), open_slide=1, slides=lambda d: [dict(title="Products by policy area", key="GOV", html=lambda dd: governance_html())]))
    C["d9_loop"] = dict(page="product", title="The feedback loop and the changelog", datasets=["product_prioritization"],
        card=dict(id="D9", datasets=["product_prioritization"], thumb_html=lambda d: loop_html(), open_slide=1,
                  slides=lambda d: [dict(title="A worked example", key="LOOP", html=lambda dd: loop_html()), dict(title="Product versions", key="LOG", html=lambda dd: changelog_html())]))
    return C
