"""The Data product tab (Phase 6, section 7): cards and viewer slides for the portfolio, built from products/*/product.yml, the seeds, the Phase 6 marts and the docs.

Every number on the tab comes from a share, a mart, a seed or a product spec; nothing is computed here beyond formatting. Product cards read product.yml and the live quality grade from the scorecards
at build time (scripts/validate_products.resolve_quality). Copy lives in site_src/copy/charts.yml (entries D1 to D9) under the same draft rules as the other pages.
"""
from __future__ import annotations

import re
from html import escape as e
from pathlib import Path

import yaml

from scripts import site_cards as sc
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
    href = (REPO + path if not target.is_dir() else REPO.replace("/blob/", "/tree/") + path) if target.exists() else None
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
        repo_base = REPO.replace("/blob/", "/tree/") if (norm and (ROOT / norm).is_dir()) else REPO
        return f'<a href="{e(repo_base + norm)}">{label}</a>' if norm else label
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


def matrix_html(ps: dict, compact: bool = False, static: dict | None = None) -> str:
    """Goals by products. `static` (the one-page summary) uses short goal and product names so no header wraps tall: static = {goals: {G1: name}, products: {DP1: name}}."""
    if static:
        head = "".join(f"<th scope='col'>{e(pid)} {e(static['products'][pid])}</th>" for pid in ps)
    else:
        head = "".join(f"<th scope='col'>{e(pid)}" + ("" if compact else f"<br><span class='note'>{e(p['name'])}</span>") + "</th>" for pid, p in ps.items())
    body = ""
    for g, text in GOALS.items():
        cells = "".join(f"<td class='vm-{p['value_proposition']}'>{VALUE_WORD[p['value_proposition']] if g in p['goals'] else '&nbsp;'}</td>" for p in ps.values())
        label = static["goals"][g] if static else (SHORT_GOALS[g] if compact else text)
        body += f"<tr><th scope='row'><b>{g}</b> {e(label)}</th>{cells}</tr>"
    note = "" if compact and not static else "<p class='note'>Driver: moves the goal directly. Enabler: makes other products possible. Utility: keeps things running.</p>"
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
def personas_html(compact: bool, static: bool = False) -> str:
    """`static` (the one-page summary): role, who it serves (with its supplier or guardrail tag), the job, and ONE question we would ask; no assumed pain."""
    rows = md_table(ROOT / "docs/product/discovery.md")[1:]
    cards = ""
    for persona, goal, job, pain, questions in rows:
        if static:
            first = re.search(r'"([^"]+)"', questions)
            extra = f"<p><b>We would ask:</b> {e(first.group(1)) if first else md_inline(questions)}</p>"
        else:
            extra = "" if compact else f"<p><b>What we assumed:</b> {md_inline(pain)}</p><p><b>What we would ask:</b> {md_inline(questions)}</p>"
        cards += f"<div class='vpersona'><h4>{md_inline(persona)}</h4><p class='note'>Serves {md_inline(goal)}</p><p>{md_inline(job)}</p>{extra}</div>"
    note = "" if compact or static else "<p class='note'>There are no real users. These are assumption-based personas with the questions we would validate in real interviews. The league operator is a supplier, not a consumer.</p>"
    return f"<div class='vproduct'><div class='vpersonas{' vcompact' if compact else ''}'>{cards}</div>{note}</div>"


# ---------------------------------------------------------------- D4 prioritization and roadmap
def prioritization_html(rows: list[dict], static: dict | None = None) -> str:
    """`static` (the one-page summary) = {products: {DP1: short name}}: short names, short column heads and a one-line formula."""
    body = ""
    for r in rows:
        total = r["value_to_goals"] + r["feasibility_today"] + r["data_readiness"] - r["privacy_risk"]
        name = f"{r['product_id']} {static['products'][r['product_id']]}" if static else f"{r['product_id']} {r['product_name']}"
        body += (f"<tr><th scope='row'>{e(name)}</th><td>{r['value_to_goals']}</td><td>{r['feasibility_today']}</td><td>{r['data_readiness']}</td><td>{r['privacy_risk']}</td>"
                 f"<td><b>{total}</b></td><td>{e(r['reading'])}</td></tr>")
    heads = ("Product", "Value", "Feasibility", "Readiness", "Privacy risk", "Total", "Reading") if static else (
        "Product", "Value to the goals", "Feasibility today", "Data readiness", "Privacy risk (higher is riskier)", "Total", "Reading")
    note = ("Scores 1 to 5. Total = value + feasibility + readiness - privacy risk." if static else
            "Scores 1 to 5, confirmed by the program owner, based on the data quality grades. Total = value + feasibility + readiness - privacy risk.")
    return (f"<div class='vproduct'><table class='vtable'><thead><tr>{''.join(f'<th>{h}</th>' for h in heads)}</tr></thead>"
            f"<tbody>{body}</tbody></table><p class='note'>{note}</p></div>")


HORIZONS = [("DELIVERED", "Delivered"), ("NOW", "Now"), ("NEXT", "Next"), ("LATER", "Later")]
LANE_KIND = {"DP1": ("source", "Source-based"), "DP2": ("master", "Master"), "DP3": ("insights", "Insights"), "DP4": ("insights", "Insights"), "DP5": ("restricted", "Insights, restricted")}


def _gate_html(r: dict) -> str:
    """The gate of a roadmap card: bar with a target marker, status text and the value line. Every value is a column of share_exec__roadmap_gates; nothing is computed here."""
    if not r["gate_id"]:
        return ""
    cls = {"MET": "met", "NOT_YET": "not", "PENDING": "pending"}[r["gate_status"]]
    mark = {"MET": "", "PENDING": "… ", "NOT_YET": "○ "}[r["gate_status"]]  # the Met text already carries its tick
    fill = "" if r["bar_fill_pct"] is None else f"<i style='width:{r['bar_fill_pct']}%'></i>"
    return (f"<div class='vgate vg-{cls}'><div class='vgbar' role='img' aria-label='{e(r['gate_id'])}: {e(r['status_text'])}, {e(r['value_text'])}'>{fill}<b style='left:{r['target_marker_pct']}%'></b></div>"
            f"<p class='vgtext'><span class='vgstat'>{mark}{e(r['status_text'])}</span> <span class='vgval'>{e(r['value_text'])}</span></p></div>")


def _decision_html(r: dict) -> str:
    if not r["decision_owner_role"]:
        return ""
    return f"<p class='vdec'><span class='vdia' aria-hidden='true'>◆</span> <b>{e(r['decision_owner_role'])}:</b> {e(r['decision_text'])}</p>"


def roadmap_board_html(rows: list[dict], ps: dict, copy: dict, slide_of: dict, static: bool = False, gap_marks: dict | None = None) -> str:
    """Swimlanes (one per product) by columns Delivered | Now | Next | Later. Cards open the full-screen viewer on their own slide.

    `static` (the one-page summary) is the same board with no click handler and no viewer: each card is a plain block. Same rows, same markup otherwise."""
    head = "".join(f"<div class='vr-colhead'>{label}</div>" for _k, label in HORIZONS)
    lanes = ""
    for pid, p in ps.items():
        key, word = LANE_KIND[pid]
        cells = ""
        for hz, label in HORIZONS:
            cards = ""
            if pid == "DP4" and hz == "DELIVERED":
                cards += f"<div class='vrpivot'><b>What we learned.</b> {e(copy['pivot'])}</div>"
            for r in (x for x in rows if x["product_id"] == pid and x["horizon"] == hz):
                chip = f"{e(r['version'])}" + (f" · {e(r['phase_ref'])}" if r["phase_ref"] else "")
                inner = f"<span class='vrhead'><span class='vrtitle'>{e(r['title'])}</span><span class='vrchip'>{chip}</span></span>{_gate_html(r)}{_decision_html(r)}"
                if static:
                    row_id = f"{pid} {r['version']}"
                    mark = "".join(f"<a class='vrgap' href='#gap-{n}'>&#8617; from gap {n}</a>" for n in (gap_marks or {}).get(row_id, []))
                    cards += f"<div class='vrcard' id='card-{pid}-{e(r['version'])}' style='cursor:default'>{inner}{mark}</div>"
                else:
                    cards += f"<button type='button' class='vrcard' data-open='D10-{slide_of[id(r)]}' aria-label='Open details: {e(r['title'])}'>{inner}</button>"
            cells += f"<div class='vr-cell' data-col='{label}'>{cards}</div>"
        lanes += (f"<div class='vr-lane vl-{key}'><div class='vr-label' title='{e(', '.join(SHORT_GOALS[g] for g in p['goals']))}'><span class='vr-type'>{e(word)}</span><b>{e(pid)} {e(p['name'])}</b>"
                  f"<span class='vr-goal'>{e(', '.join(SHORT_GOALS[g] for g in p['goals']))}</span></div>{cells}</div>")
    strip = "".join(f"<span class='vr-no'>{e(t)}</span>" for t in copy["not_doing"])
    return (f"<div class='vroad' data-roadmap{'-static' if static else ''}><div class='vr-head'><div class='vr-colhead vr-corner'></div>{head}</div>{lanes}"
            f"<div class='vr-notdoing'><span class='vr-nlabel'>Not doing</span>{strip}</div>"
            "<p class='note'>No dates: products move when their data is good enough and the right person has signed off. Bars show where a gate stands; the tick is the target. "
            "◆ marks a decision. Targets are set for a synthetic dataset.</p></div>")


def roadmap_detail_html(r: dict, ps: dict) -> str:
    p = ps[r["product_id"]]
    rows = [("Product", f"{r['product_id']} {p['name']}"), ("Horizon", r["horizon"].title()), ("Version", r["version"])]
    if r["phase_ref"]:
        rows.append(("Delivered in", r["phase_ref"]))
    if r["gate_id"]:
        rows += [("Gate", f"{r['gate_id']} ({r['kind'].lower()})"), ("Definition", r["definition"]), ("Now", r["value_text"]), ("Status", r["status_text"]),
                 ("2025 baseline", "pending" if r["baseline_2025"] is None else f"{r['baseline_2025']:g}")]
    if r["decision_owner_role"]:
        rows.append(("Decision", f"{r['decision_owner_role']}: {r['decision_text']}"))
    rows.append(("Card status", r["card_status"]))
    body = "".join(f"<tr><th scope='row'>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in rows)
    src = (f"<details class='vrow-detail' open><summary>For analysts</summary><p>The value comes from <code>{e(r['source_model'])}</code> (field <code>{e(r['source_field'])}</code>); "
           f"the gate is <code>{e(r['gate_id'])}</code>.</p></details>") if r["gate_id"] else ""
    return (f"<div class='vproduct'><h4>{e(r['title'])}</h4><table class='vtable vdetail'><tbody>{body}</tbody></table>{src}"
            f"<p class='note'>{'Draft. ' if r['card_status'] == 'draft' else ''}The value is computed in SQL (share_exec__roadmap_gates); a missing value shows as baseline pending, never as 0.</p></div>")


# ---------------------------------------------------------------- D5 product labels
def label_html(pid: str, p: dict, spec_row: dict, full: bool, plain: bool = False) -> str:
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
    if plain:
        return label_plain_html(pid, p, spec_row)
    prohibited = "".join(f"<li>{e(u['use'])} <span class='note'>enforced by {', '.join(e(x['name']) for x in u['enforced_by'])}</span></li>" for u in p["privacy"]["prohibited_uses"])
    return (f"<div class='vproduct'><div class='vlabel'>{base}{ev}<h5>Consumers</h5><ul>{consumers}</ul><h5>Output ports</h5><ul>{ports}</ul>"
            f"<h5>Prohibited uses and what enforces them</h5><ul>{prohibited}</ul>"
            f"<p><b>Shelf life:</b> {e(p['shelf_life'])}. <b>Decommission:</b> {link(p['decommission_plan'])}. <b>Support:</b> {e(p['support_contact'])}. <b>Pricing:</b> {e(p['pricing'])}</p>"
            f"<p class='note'>Fictional roles. The quality grade is read from the scorecards at build time, never typed.</p></div></div>")


def permitted_uses(pid: str) -> list[str]:
    """The bullets under 'Permitted uses' in the product's terms of use (docs/product/terms/<id>.md)."""
    text = (ROOT / f"docs/product/terms/{pid}.md").read_text(encoding="utf-8")
    block = re.search(r"## Permitted uses\n(.*?)\n## ", text, flags=re.S).group(1)
    return [re.sub(r"\s+", " ", md_inline(m)).strip() for m in re.findall(r"^- (.+)$", block, flags=re.M)]


def label_plain_html(pid: str, p: dict, spec_row: dict) -> str:
    """The label in plain words, for the one-page summary: owner, who uses it, what it publishes, the live grade, and the rules for use. No model names, no enforcement detail (that stays on the tab)."""
    users = "".join(f"<li><b>{e(c['role'])}:</b> {e(c['use_case'])}</li>" for c in p["consumers"])
    allowed = "".join(f"<li>{t}</li>" for t in permitted_uses(pid)[:2])      # already inline html from md_inline
    never = "".join(f"<li>{e(u['use'])}</li>" for u in p["privacy"]["prohibited_uses"])
    return (f"<div class='vlabel vlabel-plain'><p>{e(p['description'])}</p><p><b>Owner:</b> {e(p['owner_role'])}</p><p><b>Who uses it</b></p><ul>{users}</ul>"
            f"<p><b>Live quality:</b> {e(spec_row['quality_text'])}</p><div class='vrules'><div><p><b>Allowed</b></p><ul>{allowed}</ul></div><div><p><b>Never allowed</b></p><ul class='vnever'>{never}</ul></div></div></div>")


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
    items = "".join(f"<li><b>{e(names.get(j, j))}:</b> unverified \u2014 strictest rule applies (ages {e(', '.join(a))})</li>" for j, a in by.items())
    n_yes = sum(1 for r in rules if r["verified"] == "Y")
    return ("<div class='vproduct'><h4>Open items: rules not yet verified</h4>"
            f"<ul>{items}</ul><p class='note'>{n_yes} of {len(rules)} rows have sources checked, with a source link (US federal under 13, California 13 to 15, Quebec under 14, the EU under 16). Every other row is unverified and has no source link yet. The strictest row applies where unsure, so these gaps make the rules stricter, not looser. {link('docs/product/age-consent-rules.md', 'The full table')}.</p></div>")


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
AREA_LABEL = {"quality": "Quality", "freshness": "Freshness", "contract_status": "Contracts", "pipeline": "Pipeline", "trust": "Trust", "boundaries": "Boundaries", "privacy": "Privacy", "cost": "Cost proxy"}
STATUS_CLASS = {"OK": "ok", "WATCH": "watch", "ALERT": "alert", "INFO": "info"}
STATUS_TEXT = {"OK": "OK", "WATCH": "Watch", "ALERT": "Alert", "INFO": "Info"}


def health_html(rows: list[dict], ps: dict, compact: bool) -> str:
    cards = ""
    for pid, p in ps.items():
        mine = [r for r in rows if r["product_id"] == pid]
        lines = "".join(f"<tr><th scope='row'>{AREA_LABEL.get(r['area'], r['area'])}</th><td>{e(r['measure'])}</td><td><b>{e(r['value_text'])}</b></td><td><span class='vstat vstat-{STATUS_CLASS[r['status']]}'>{STATUS_TEXT[r['status']]}</span></td></tr>"
                        for r in mine if not compact or r["area"] in ("quality", "trust", "boundaries", "privacy"))
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


def adr_chip(ref: str) -> str:
    hit = sorted((ROOT / "docs/decisions").glob(f"{ref}-*.md"))
    return f"<a class='adr' href='{e(REPO + hit[0].relative_to(ROOT).as_posix())}'>{e(ref)}</a>" if hit else f"<span class='adr'>{e(ref)}</span>"


def changelog_html() -> str:
    """Product, version, a plain-language change, ADR chips. Model names live in the row's analyst detail, never in the visible change text."""
    rows = md_table(ROOT / "products/CHANGELOG.md")
    head = "".join(f"<th>{e(c)}</th>" for c in rows[0][:4])
    body = ""
    for product, version, change, links, detail in (r[:5] for r in rows[1:]):
        chips = " ".join(adr_chip(x.strip()) for x in links.split(",") if x.strip())
        body += (f"<tr><td>{e(product)}</td><td>{md_inline(version, 'products')}</td>"
                 f"<td>{md_inline(change, 'products')}<details class='vrow-detail'><summary>For analysts</summary><p>{md_inline(detail, 'products')}</p></details></td><td>{chips}</td></tr>")
    return (f"<div class='vproduct'><table class='vtable'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
            "<p class='note'>Methodology version stays 2.0: no counting rule and no published KPI changed.</p></div>")


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
                  slides=lambda d: [dict(title="Priorities", key="PRIO", html=lambda dd: prioritization_html(dd["product_prioritization"]["rows"]))]))
    def road_slides(d):
        rows = d["roadmap"]["rows"]
        return [dict(title=r["title"], key="CARD", html=(lambda r: lambda dd: roadmap_detail_html(r, ps))(r)) for r in rows]

    def road_board(d):
        rows = d["roadmap"]["rows"]
        return roadmap_board_html(rows, ps, sc._state["copy"]["D10"], {id(r): i for i, r in enumerate(rows, 1)})

    C["d10_roadmap"] = dict(page="product", title="The roadmap", datasets=["roadmap"],
        card=dict(id="D10", datasets=["roadmap"], no_thumb=True, pre_html=road_board, open_slide=1, slides=road_slides))
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
