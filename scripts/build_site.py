"""Build the static results site (site/) from the warehouse. All data is SYNTHETIC.

  uv run python -m scripts.build_site            (make site)

Rules the build enforces (and tests/test_build_site.py checks):
  * Every number on the site comes from a dataset in the DATASETS list below, exported to site/data/<name>.json. A dataset may read ONLY
      - a `share_exec` table (the executive share: aggregates, small cells suppressed),
      - an approved analyst aggregate (APPROVED_AGGREGATES: the event studies; nothing household-level),
      - a whitelisted evaluation summary (EVAL_WHITELIST: the synthetic ground truth, always labelled as such on the page), or
      - governance metadata (GOVERNANCE_WHITELIST: contract results, the access policy, the source registry, the restatement log).
    Anything else fails the build.
  * No number is computed in JavaScript. Every chart is a Vega-Lite spec that only maps fields to marks: transforms that calculate, aggregate, bin,
    fold or window are forbidden and the build fails on them. Rates, intervals and shares are computed in SQL, in the models.
  * Every chart has a one-sentence "what this shows" and a one-sentence "what it doesn't show", and a plain table of its numbers under it.

Layout (each module imports only from the ones above it):
  site_data.py    the whitelists and every dataset (SQL)          site_render.py  labels, cell formatting, tables, the chart block
  site_rules.py  checks on datasets, chart specs and built pages  site_charts.py  the Vega-Lite chart specs and the drive chart
  build_site.py   page assembly, the build and the command line (this file); the Phase 5 pages and cards are in site_phase5.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

import duckdb

from scripts import site_cards, site_global as G, site_phase5 as P5, site_product, site_summary, site_tables
from scripts.common import DB, ROOT
from scripts.site_charts import charts
from scripts.site_rules import check_brand_boundary, check_dataset, check_spec
from scripts.site_data import DATASETS
from scripts.site_render import FAVICON, chart_block, esc, fmt_cell, relabel, table_html

OUT = ROOT / "site"

LIBS = ["https://cdn.jsdelivr.net/npm/vega@5", "https://cdn.jsdelivr.net/npm/vega-lite@5", "https://cdn.jsdelivr.net/npm/vega-embed@6"]


# ------------------------------------------------------------------ pages
PAGES = [("product", "Data product"), ("index", "Overview"), ("acquisition", "Acquisition"), ("value", "Value"), ("audience", "Audience"), ("participation", "Participation"), *P5.PAGES, *G.PAGES, ("trust", "Trust")]
# page title (display type) and the one-sentence question under it (ui-spec section 5)
PAGE_HEAD = {
    "index": ("Counting flag football's fans", "What this project is and how to read it."),
    "acquisition": ("Fan acquisition", "How many families become fans, and how many are new?"),
    "value": ("Fan value and activeness", "How engaged and valuable are flag families?"),
    "audience": ("Audience and consent", "How many can we reach, and what are we missing?"),
    "participation": ("Participation", "How many play, and how sure are we?"),
    "trust": ("Data trust and governance", "Why can these numbers be trusted?"),
    "product": ("Data product", "Given these business goals, what data products would you build, in what order, for whom, under what privacy rules, and how would you know they are working?"),
    **P5.PAGE_HEAD,
    **G.PAGE_HEAD,
    "glossary": ("Glossary", "What each plain term on this site means, and what analysts call it."),
    "appendix": ("Appendix: school and recreation programs", "A stretch source: how many children do schools and recreation departments report?"),
}
SRC = ROOT / "site_src"
LOCAL_LOGO = ROOT / "local_assets" / "logo.webp"       # optional and git-ignored: shown on a local build only, so CI and the published site never carry it
APPENDIX = [("appendix", "Appendix"), ("glossary", "Glossary")]          # a stretch source (school and recreation headcounts): built, linked from the footer, not in the main navigation



NAV_GROUPS = [
    ("Data product", [("product.html", "Data product", "product")]),
    ("Global outlook", [("global.html", "Global outlook", "global")]),
    ("Results", [("participation.html", "Participation", "participation"), ("sure.html", "How sure", "sure"), ("acquisition.html", "Acquisition", "acquisition"), ("audience.html", "Audience", "audience")]),
    ("Data quality", [("quality.html", "Data quality", "quality"), ("markets.html", "Club markets", "markets")]),
    ("Privacy", [("privacy.html", "Privacy by design", "privacy"), ("trust.html", "Trust and governance", "trust")]),
    ("About", [("index.html", "Overview", "index"), ("trust.html#documents", "Methodology", "methodology"), ("glossary.html", "Glossary", "glossary")]),
]


def memo_version() -> str:
    """The methodology memo's own version (it differs from the scorecard methodology version on purpose): read from the memo, the single source."""
    import re
    m = re.search(r"Memo version \*\*([0-9.]+)\*\*", (ROOT / "docs" / "methodology" / "counting-a-participant.md").read_text(encoding="utf-8"))
    return m.group(1) if m else "unknown"


def render_page(slug: str, body: str, built: str, version: str, hero: str | None = None, body_class: str | None = None, extra_css: str | None = None) -> str:
    """Render one page through the Jinja base template (site_src/templates/base.html). A page may bring its own full-width banner (`hero`, shown in place
    of the plain title), a body class and a style block: the Global outlook uses them to take the Data product summary's look (ADR-033)."""
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    env = Environment(loader=FileSystemLoader(str(SRC / "templates")), autoescape=True, undefined=StrictUndefined)
    title, question = PAGE_HEAD[slug]
    body = site_tables.enhance(body)
    return env.get_template("base.html").render(title=title, question=question, body=body, built=built, version=version, libs=LIBS,
                                                nav_groups=[{"label": g, "items": items, "current": any(sl == slug for _h, _l, sl in items)} for g, items in NAV_GROUPS], current=slug, appendix=True,
                                                logo=LOCAL_LOGO.exists(), memo_version=memo_version(), hero=hero, body_class=body_class, extra_css=extra_css)


def copy_assets(out: Path) -> None:
    (out / "css").mkdir(parents=True, exist_ok=True)
    (out / "js").mkdir(parents=True, exist_ok=True)
    for name in ("tokens.css", "site.css"):
        shutil.copy(SRC / "styles" / name, out / "css" / name)
    shutil.copy(SRC / "site.js", out / "js" / "site.js")
    (out / "assets").mkdir(exist_ok=True)
    for name in ("viewer.js", "viewer.css"):
        shutil.copy(SRC / "assets" / name, out / "assets" / name)
    (out / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    if LOCAL_LOGO.exists():
        (out / "img").mkdir(exist_ok=True)
        shutil.copy(LOCAL_LOGO, out / "img" / "logo.webp")


def value_explanation(f: dict) -> str:
    """Plain paragraphs on how the estimates sit against the synthetic truth, direction-aware so they stay honest if the numbers move. The matched estimate (fan_uplift_pct, DID_ADDITIVE) is the canonical one;
    its naive companion is the same kind of household without matching; the pooled naive (every linked account) is analyst detail and is explained by its composition."""
    did, truth = f["did_pct"], f["truth_pct"]
    ne, ne_truth, pooled, pooled_truth = f["naive_pct"], f["naive_existing_truth_pct"], f["naive_pooled_pct"], f["naive_pooled_truth_pct"]
    p1 = (f"Households that already followed the NFL: the matched estimate is {did:+.1%} (the uplift they actually got is {truth:+.1%}). Its naive companion, the same kind of household compared without matching, "
          f"says {ne:+.1%} against a truth of {ne_truth:+.1%} for those households.")
    if ne > ne_truth:
        p1 += " It overstates, as designed: households that enroll a child were already more engaged before they enrolled (selection), and a naive comparison cannot see that."
    p2 = (f"Pooling every linked account, including accounts the programme itself created, gives {pooled:+.1%} (truth {pooled_truth:+.1%} for that mix). That number is analyst detail: the accounts the programme created "
          "belong to households that engage less than the average fan, so they pull the pooled average down, and it hides the second effect of flag (new fan accounts; see Acquisition). The direction of a pooled "
          "average is not the direction of the selection bias, which is why it is not the number to quote.")
    parts = [p1, p2]
    if did > truth:
        parts.append("The matched estimate overshoots its truth slightly. The table below points to why: "
                     f"matching on observed engagement did not balance the underlying fan inclination, which averages {f['fandom_treated']:.2f} for the matched participating households "
                     f"against {f['fandom_comparison']:.2f} for their matched comparisons, so the before/after change still leans high. "
                     "Read the matched figure as an upper-leaning estimate, not a correction.")
    return "".join("<p class='note'>" + esc(x) + "</p>" for x in parts)


RESTATEMENT_EXAMPLES = """<p class="note">The restatement log is empty because the latest published snapshots match the rebuilt numbers. That is the good case. Four recorded runs show what it looks like when it is not empty
(full tables in <code>docs/reports/restatement_demo.md</code>; all synthetic):</p>
<table><thead><tr><th>Example</th><th>Cause</th><th>What changed</th><th>Restatement?</th></tr></thead><tbody>
<tr><td>One steward decision</td><td>Identity change</td><td>Two registrations of one child, kept apart by a mistyped first name, were merged. 2025 unique participants went from 3,962 to 3,961 (-0.025%).</td><td>No: below the 1% threshold; logged for the next snapshot</td></tr>
<tr><td>The observation window grew from 3 to 5 years</td><td>New source data</td><td>41 changed KPIs; 23 exceeded the threshold. 2025 unique participants went from 3,962 to 2,837 (-28.4%).</td><td>Yes: three published years restated, new baselines published</td></tr>
<tr><td>A methodology bump that only adds KPIs</td><td>New KPI</td><td>Four school and recreation KPIs added for five years. Every existing KPI was identical to its published value.</td><td>No: additions are listed, never restated</td></tr>
<tr><td>The generator changed upstream (more people, staggered market launches)</td><td>New source data</td><td>88 changed KPI rows; 59 required a restatement. 2025 unique participants went from 2,837 to 8,959 (+215.8%).</td><td>Yes: methodology v2.0 published new baselines</td></tr>
</tbody></table>"""


G3_FRAME = ("Flag does two things: families already following the NFL engage about {uplift} more, and flag creates about {fans} new fan accounts among families who weren't fans "
            "(about {per100} per 100 participant households). A pooled average hides the second effect.")


def g3_frame(facts: dict) -> str:
    r10 = lambda x: f"{int(round(x, -1)):,}"  # noqa: E731  estimates are rounded to the nearest 10 and prefixed "about"
    return esc(G3_FRAME.format(uplift=f"{round(facts['did_pct'] * 100):.0f}%", fans=r10(facts["incremental"]), per100=f"{facts['per100']:.0f}"))


def build_pages(data: dict, chart_defs: dict, facts: dict) -> dict[str, tuple[str, str]]:
    built = {}
    blocks = {p: [] for p, _ in PAGES + APPENDIX}
    for cid, ch in chart_defs.items():
        blocks[ch["page"]].append(chart_block(cid, ch, data))

    flow = " <i>&rarr;</i> ".join(f"<span>{esc(s)}</span>" for s in ["sources", "contracts", "raw", "staging", "identity", "households", "fan models", "shares", "this site"])
    latest = facts["latest_year"]
    built["index"] = ("Overview", f"""
<p>Flag football registers children. This project asks a different question: <i>how many fans does that create, how engaged and valuable are they, and how many can we actually contact?</i>
It is a governed data platform built end to end on <b>synthetic</b> data (the real equivalent would be minors' personal data), and every claim is graded against the generator's answer key.</p>
<div class="flow">{flow}</div>
<p class="note">Five sources (a league CSV, a club API, a federation workbook, school headcounts and a fan feed) are contracted, loaded as-is, cleaned in SQL, resolved to people and households,
linked to fan accounts under a restricted-zone policy, shared by audience with small numbers suppressed, and published as versioned snapshots.</p>
<h2>Headline</h2>
<table><tbody>
<tr><td>Fan accounts the programme added (incremental estimate, with interval)</td><td>{fmt_cell(facts['incremental'])} ({fmt_cell(facts['inc_low'])} to {fmt_cell(facts['inc_high'])}); the naive count says {fmt_cell(facts['naive_scaled'])}</td></tr>
<tr><td>Addressable audience, {facts['audience_month']} (households a guardian has opted in)</td><td>{fmt_cell(facts['contactable'])} of {fmt_cell(facts['registered'])} registered households</td></tr>
<tr><td>Consent gap (active households with no opt-in)</td><td>{fmt_cell(facts['gap'])}, about {facts['gap_share']:.0%} of active households</td></tr>
<tr><td>Unique registered participants, {latest}</td><td>{fmt_cell(facts['participants'])} (identity range {fmt_cell(facts['low'])} to {fmt_cell(facts['high'])})</td></tr>
<tr><td>Fan engagement uplift after a first registration (matched, households that already followed the NFL)</td><td>{facts['did_pct']:+.1%} (naive companion {facts['naive_pct']:+.1%}; truth {facts['truth_pct']:+.1%})</td></tr>
</tbody></table>
<h2>A five-minute tour</h2>
<ol class="tour">
<li><a href="acquisition.html">Fan acquisition</a>: how many fans flag football created, and why the naive count is too big.</li>
<li><a href="audience.html">Audience &amp; consent</a>: how many fans can be contacted, where consent is captured, and the gap. Governance sets the size of the marketable audience.</li>
<li><a href="participation.html">Participation</a>: the original question, how many people play, and who stays.</li>
<li><a href="trust.html">Data trust &amp; governance</a>: identity resolution (why the household count is right), contracts, who sees what, what changed after publishing.</li>
</ol>
<p class="note">Decisions and their reasons are in the ADRs; the counting rules are in the methodology memos. Both are linked from <a href="trust.html">Data trust &amp; governance</a>.</p>""")
    built["acquisition"] = ("Fan acquisition", f"<p class='note'><b>{g3_frame(facts)}</b></p><p class='note'><b>Fans created by flag: about {fmt_cell(facts['incremental'])} fan accounts. Counting every new sign-up and scaling it up for unseen families says {fmt_cell(facts['naive_scaled'])}, about {facts['naive_scaled'] / facts['incremental']:.1f} times too many, because many of those families would have become fans anyway.</b> The first chart is the answer; the rest show where it comes from. Funnel and status describe households linked to a fan account; "
                            "identity resolution is why the denominator is right (a child in several leagues is one household member, not several).</p>" + "".join(blocks["acquisition"]))
    built["value"] = ("Fan value & activeness", f"<p class='note'><b>{g3_frame(facts)}</b></p><p class='note'><b>Registering a child raises a linked family's fan engagement by about a fifth, and the effect follows the NFL season. New fans from flag football are worth nearly as much as other new fans, but stay active for less time.</b> Estimates describe households linked to a fan account, under a restricted-zone policy (ADR-009). Nothing household-level is shown; money is synthetic currency.</p>"
                      + "".join(blocks["value"]) + "<h2>Why the matched engagement estimate is where it is</h2>" + value_explanation(facts) + table_html(data["fan_diagnostics"]))
    built["audience"] = ("Audience & consent", f"<p class='note'><b>Only {fmt_cell(facts['contactable'])} of {fmt_cell(facts['registered'])} registered households can be contacted. The bigger constraint is linking families to fan accounts, not consent: once linked, most families say yes.</b> Governance determines the size of the marketable audience: only a guardian's recorded opt-in makes a household contactable. "
                         "Counts only; nobody here is a list, and no linked household reaches marketing or media (ADR-009).</p>"
                         + "".join(blocks["audience"]) + "<h2>Latest month by household group</h2>" + table_html(data["audience_latest"])
                         + "<h2>Markets per quadrant</h2>" + table_html(data["quadrant_counts"])
                         + "<h2>Who can be linked</h2>" + table_html(data["link_rate"]))
    built["participation"] = ("Participation", f"<p class='note'><b>{fmt_cell(facts['participants'])} unique children played in {latest}, up from {fmt_cell(facts['first_participants'])} in {facts['first_year']}. Younger entrants stay much longer than teenagers, and boys and girls stay at the same rate.</b> The original question, condensed: how many people play, with the band that identity resolution leaves, and who stays. Retention is Kaplan-Meier from the first season, computed in SQL: "
                              "a player who turns 18, or whose follow-up ends with the data, is censored, not counted as gone.</p>" + "".join(blocks["participation"]))
    built["appendix"] = ("Appendix", "<p class='note'>A <b>stretch</b> source: school districts and recreation departments report how many "
                         "children are in their programs. The counts have no people in them, so they are never added to participants.</p>" + "".join(blocks["appendix"])
                         + "<h2>Against the synthetic truth</h2>" + table_html(data["reach_vs_truth"]))
    built["trust"] = ("Trust", f"""<h2>Identity: can the numbers be trusted?</h2>
<p class='note'>Matching people across sources is the hard part. The generator's answer key grades it; real projects have no key.</p>
{"".join(blocks["trust"])}
<h3>Rules vs probabilistic, before any steward review</h3>{table_html(data["matcher_comparison"])}
<p class="note"><b>What this shows.</b> A rules baseline, a literal Fellegi-Sunter matcher (fs_naive) and the corrected one (fs) on the same data. <b>What it does not show.</b> Real-world accuracy; the sibling and twin merges are the incidents that matter.</p>
<h3>Error categories</h3>{table_html(data["error_categories"])}
<h3>Identity bounds against the synthetic truth</h3>{table_html(data["identity_truth_check"])}
<h3>Household linkage precision and recall against the synthetic truth</h3>{table_html(data["household_linkage_vs_truth"])}
<h2>Who sees what</h2>{table_html(data['audience_matrix'])}
<p class="note"><b>What this shows.</b> Five audiences, each with a column-level allow list; the executive audience gets aggregates only, and nothing linked reaches marketing or media. <b>What it does not show.</b> Real access control: this is a policy enforced by a build check, not by a database role (ADR-006).</p>
<h2>Suppression example</h2><p class="note">Participants by sex, every year. In 2021, 2022 and 2024 the count of participants with unknown sex is below 10 and is hidden, and so is the female count, because the total and the male count would reveal it by subtraction.</p>{table_html(data['suppression_example'])}
<p class="note"><b>What this shows.</b> A count below 10 is hidden (primary suppression) and, where subtraction would reveal it, a second cell too (secondary suppression). <b>What it does not show.</b> Formal disclosure control; production would use sdcMicro or tau-Argus.</p>
<h2>Data contracts per source</h2>{table_html(data['contract_status'])}
<h2>Onboarding status</h2>{table_html(data['source_status'])}
<h2>What changed after publishing</h2>{table_html(data['restatement_log']) if data['restatement_log']['rows'] else ''}{RESTATEMENT_EXAMPLES}
<h2 id="documents">Documents</h2><ul>
<li><code>docs/methodology/counting-a-participant.md</code>: the counting rules C1 to C15</li>
<li><code>docs/methodology/flag-as-fan-acquisition.md</code>: fan status, why unlinked is not a non-fan, market-level acquisition, LTV assumptions (draft)</li>
<li><code>docs/decisions/</code>: ADR-001 to ADR-011, including the linkage governance decision (ADR-009), the fandom design (ADR-010) and the acquisition measurement design (ADR-011)</li>
<li><code>docs/playbook/onboard-a-source.md</code>: how a source is onboarded, with the logs for the two Phase 4 sources</li>
<li><code>docs/access_policy.md</code>, <code>docs/metrics.md</code>, <code>docs/data_dictionary.md</code></li></ul>""")
    built.update(phase5_pages(blocks, data))
    built["glossary"] = ("Glossary", glossary_body(data))
    return built


def lens_scope(inner: str, default: str, demo: str, demo_slide: str = "") -> str:
    """Page-level Club lens / Privacy lens toggle. It only shows and hides precomputed annotations and panels (CSS attribute selectors); it never filters or computes."""
    toggle = ('<div class="lens-toggle" role="group" aria-label="Choose a lens"><span class="note">Lens</span>'
              f'<button type="button" data-set-lens="club" aria-pressed="{"true" if default == "club" else "false"}">Club lens</button>'
              f'<button type="button" data-set-lens="privacy" aria-pressed="{"true" if default == "privacy" else "false"}">Privacy lens</button></div>')
    go = f' <a class="demo-go" href="#view={esc(demo_slide)}">Start the 5-minute path \u2192</a>' if demo_slide else ""
    path = f'<aside class="demo-path"><span><b>5-minute path.</b> {esc(demo)}</span>{go}</aside>'
    return f'{path}{toggle}<div class="lens-scope" data-lens-active="{default}">{inner}</div>'


def glossary_body(data: dict) -> str:
    """The glossary: hand-written terms (site_src/copy/glossary.yml), then the uses, checks and grades from the seeds, then every problem we check (in a collapsed section: codes live there)."""
    import yaml
    terms = yaml.safe_load((SRC / "copy" / "glossary.yml").read_text(encoding="utf-8"))["terms"]
    dl = "".join(f"<dt>{esc(t['term'])}</dt><dd>{esc(t['definition'])} <span class='tech'>Analysts call this: {esc(t['technical'])}.</span></dd>" for t in terms)
    seeds = "".join(f"<dt>{esc(r['term'])} <span class='tech'>({esc(r['kind'].lower())})</span></dt><dd>{esc(r['meaning'])} <span class='tech'>Analysts call this: {esc(r['technical'])}.</span></dd>"
                    for r in data["glossary_checks"]["rows"])
    rules = "".join(f"<tr><td>{esc(r['problem'])}</td><td>{esc(r['what_to_do'])}</td><td><code>{esc(r['technical'])}</code></td></tr>" for r in data["glossary_rules"]["rows"])
    return (f"<p class='note intro'><b>Plain words first. Each term has the name analysts use for it, so the two can be matched.</b></p><dl class='glossary'>{dl}{seeds}</dl>"
            f"<details><summary>Every problem we check ({len(data['glossary_rules']['rows'])})</summary><table><thead><tr><th>Problem</th><th>What to do</th><th>Code</th></tr></thead><tbody>{rules}</tbody></table></details>")


def group_cards(blocks: list[str]) -> str:
    """Consecutive chart cards go into one responsive grid (2 columns at 1100 px and wider); other blocks pass through."""
    out, run = [], []
    for b in blocks + [""]:
        if b.startswith('<article class="vcard"'):
            run.append(b)
            continue
        if run:
            out.append('<div class="vgrid">' + "".join(run) + "</div>")
            run = []
        out.append(b)
    return "".join(out)


GLOBAL_CSS_EXTRA = """
/* Global outlook in the Data product summary's look (ADR-033): each numbered section holds one card; the section title is the card's question,
   so the card's own question line is kept for screen readers and the page check but not shown twice */
body.summary .ps-sec .vcard{margin:0}
body.summary .ps-sec .vcard-question{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
body.summary .ps-tabs{top:0}
body.summary main{padding-top:0}
body.summary .lens-toggle,body.summary .demo-path{margin-top:24px}
"""


def global_hero(pg: dict) -> str:
    """The Global outlook's banner and section bar, built like the Data product summary's: every number is an insight value filled by site_cards.fill."""
    record = "".join(f"<div class='ps-rec'><div class='n'>{esc(site_cards.fill(r['value'], None, None))}</div><div class='l'>{esc(r['label'])}</div></div>" for r in pg["record"])
    tabs = "".join(f"<a href='#s-{esc(s['id'])}'{' class=on' if i == 0 else ''}>{esc(s['tab'])}</a>" for i, s in enumerate(pg["sections"]))
    return (f"<header class='ps-hero'><div class='ps-inner'><p class='ps-eyebrow'>{esc(site_cards.fill(pg['hero_eyebrow'], None, None))}</p><h1>{esc(pg['hero_title'])}</h1>"
            f"<span class='ps-badge'>{esc(pg['hero_badge'])}</span><p class='ps-pitch'>{esc(site_cards.fill(pg['intro_template'], None, pg.get('fallback_intro')))}</p>"
            f"<div class='ps-record'>{record}</div></div></header><nav class='ps-tabs' aria-label='Sections'><div class='ps-inner'>{tabs}</div></nav>")


def global_sections(blocks: list[str], pg: dict, copy: dict) -> str:
    """One numbered section per card, in the order of the page copy; the section title is the card's question."""
    by_card = {re.search(r'data-card="([A-Z][0-9])"', b).group(1): b for b in blocks}
    out = []
    for i, s in enumerate(pg["sections"], 1):
        out.append(f"<section class='ps-sec' id='s-{esc(s['id'])}'><header class='ps-sh'><div class='ps-sht'><p class='ps-kicker'>{i} · {esc(s['tab'])}</p>"
                   f"<h2>{esc(copy[s['card']]['question'])}</h2></div></header>{by_card[s['card']]}</section>")
    return "".join(out)


def phase5_pages(blocks: dict, data: dict) -> dict:
    out = {}
    pages = site_cards.load_pages()
    for slug in ("product", "quality", "sure", "markets", "privacy", "global"):
        inner = ("<ul class='vgoals'>" + "".join(f"<li><b>{g}</b> {esc(t)}</li>" for g, t in site_product.GOALS.items()) + "</ul>" if slug == "product" else "") + group_cards(blocks[slug])
        if slug == "privacy":
            inner += ("<h2>Share-policy check</h2>" + table_html(data["policy_results"])
                      + "<p class='note'>Violations found on the last run of the check that guards every share (no direct or quasi identifier in the club or privacy shares, only approved aggregate marts upstream, every metric in the catalog). Zero is the expected result.</p>")
        default = "privacy" if slug in ("privacy",) else "club"
        title = PAGE_HEAD[slug][0]
        pg = pages[slug]
        if slug == "global":       # the summary look: the banner carries the intro, the sections carry the cards (ADR-033)
            out[slug] = (title, lens_scope(global_sections(blocks[slug], pg, site_cards.load_copy()), "club", pg["demo_text"], pg["demo_slide"]))
            continue
        intro = f"<p class='note intro'><b>{esc(site_cards.fill(pg['intro_template'], None, pg.get('fallback_intro')))}</b></p>"
        if slug == "product":
            intro += f"<p class='note'><a class='summary-link' href='{site_summary.SLUG}.html'>One-page summary &rarr;</a></p>"
        out[slug] = (title, intro + lens_scope(inner, default, pg["demo_text"], pg["demo_slide"]))
    return out


# ------------------------------------------------------------------ build
def export(con: duckdb.DuckDBPyConnection) -> dict:
    data = {}
    for ds in DATASETS:
        problems = check_dataset(ds)
        if problems:
            raise SystemExit("SITE BUILD REFUSED:\n  " + "\n  ".join(problems))
        cur = con.execute(ds["sql"])
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        data[ds["name"]] = {"name": ds["name"], "title": ds["title"], "source": ", ".join(sorted(ds["relations"])), "kind": ds["kind"], "columns": cols, "rows": rows}
    data["product_specs"] = product_specs(con)
    return data


def product_specs(con) -> dict:
    """The five product specs with their live quality indicator, read from products/*/product.yml and the scorecards at build time."""
    from scripts import validate_products as vp
    rows = []
    for pid, p in vp.load().items():
        q = vp.resolve_quality(p["quality_indicator"], con)
        if q["kind"] == "grade_distribution":
            text = ", ".join(f"{g} {n}" for g, n in q["value"].items() if n) + f" ({q['detail']})"
        elif q["kind"] == "identity_range_pct":
            text = f"identity range {q['value']}% of the count ({q['detail']})"
        else:
            text = f"grade {q['value']} ({q['detail']})"
        rows.append({"id": pid, "name": p["name"], "version": p["version"], "type": p["type"], "status": p["status"], "goals": ", ".join(p["goals"]), "value_proposition": p["value_proposition"],
                     "owner_role": p["owner_role"], "quality_text": text, "output_ports": ", ".join(pt["model"] for pt in p["output_ports"]), "terms_of_use": p["terms_of_use"]})
    return {"name": "product_specs", "title": "The five product specs with their live quality grade", "source": "products/*/product.yml, quality scorecards", "kind": "governance",
            "columns": list(rows[0]), "rows": rows}


def build(db: Path = DB, out: Path = OUT) -> dict:
    con = duckdb.connect(str(db), read_only=True)
    try:
        data = export(con)
        latest = con.execute("select max(participation_year) from share_exec.share_exec__participation_bounds").fetchone()[0]
        con_version = con.execute("select max(methodology_version) from measurement.mart_kpi_scorecard").fetchone()[0]
    finally:
        con.close()
    chart_defs = charts()
    known = {f"data/{n}.json" for n in data} | {G.GEO_URL}       # plus the country outlines (shapes only, no figures: ADR-032)
    problems = [p for cid, ch in chart_defs.items() if ch.get("spec") for p in check_spec(ch["spec"], known, cid)]
    for cid, ch in chart_defs.items():
        if ch.get("card"):
            for k, sp in [("thumb", ch["card"].get("thumb") if not callable(ch["card"].get("thumb")) else None)] + [(f"slide {i}", s.get("spec")) for i, s in enumerate([] if callable(ch["card"]["slides"]) else ch["card"]["slides"], 1)]:
                if sp is None:
                    continue
                problems += check_spec(sp, known, f"{cid} {k}")
    for cid, ch in chart_defs.items():
        for n in ch["datasets"]:
            if n not in data:
                problems.append(f"{cid}: dataset {n} is not defined")
    if problems:
        raise SystemExit("SITE BUILD REFUSED:\n  " + "\n  ".join(problems))
    rows = lambda n: data[n]["rows"]  # noqa: E731
    bounds = next(r for r in rows("participation_bounds") if r["participation_year"] == latest)
    fan = {r["estimator"]: r for r in rows("fan_vs_truth")}
    first = min(rows("participation_bounds"), key=lambda r: r["participation_year"])
    facts = {"first_year": first["participation_year"], "first_participants": first["identity_participants_point"], "latest_year": latest, "participants": bounds["identity_participants_point"], "low": bounds["identity_participants_low"], "high": bounds["identity_participants_high"],
             "did_pct": fan["DID_ADDITIVE"]["estimate_pct"], "naive_pct": fan["NAIVE_EXISTING"]["estimate_pct"], "truth_pct": fan["DID_ADDITIVE"]["true_effect_pct"],
             "naive_existing_truth_pct": fan["NAIVE_EXISTING"]["true_effect_pct"], "naive_pooled_pct": fan["NAIVE"]["estimate_pct"], "per100": rows("acq_headline")[0]["incremental_fan_accounts_per_100_households"], "naive_pooled_truth_pct": fan["NAIVE"]["true_effect_pct"],
             "km1": next(r["km_survival"] for r in rows("retention_km_all") if r["years_since_entry"] == 1)}
    acq = {r["method"][0]: r for r in rows("acq_estimates")}
    aud = next(r for r in rows("audience_latest") if r["household_group"] == "ALL")
    facts.update({"incremental": round(acq["1"]["estimate"]), "inc_low": round(acq["1"]["ci_low"]), "inc_high": round(acq["1"]["ci_high"]), "naive_scaled": round(acq["2"]["estimate"]),
                  "contactable": aud["audience_contactable"], "registered": aud["audience_registered"], "gap": aud["consent_gap_households"], "gap_share": aud["consent_gap_share_of_active"],
                  "audience_month": str(max(r["month"] for r in rows("audience_series")))[:7]})
    diag = {r["measure"]: r["value"] for r in rows("fan_diagnostics")}
    facts.update({"fandom_treated": diag["fandom_matched_treated"], "fandom_comparison": diag["fandom_matched_comparison"]})
    site_cards.configure(data["chart_insights_club"]["rows"] + data["chart_insights_privacy"]["rows"] + data["chart_insights_eval"]["rows"] + data["chart_insights_exec_global"]["rows"])
    relabel(data)                       # plain labels for every code name, after the facts above have used the codes
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    for name, d in data.items():
        (out / "data" / f"{name}.json").write_text(json.dumps(d, default=str), encoding="utf-8")
    (out / "data" / "manifest.json").write_text(json.dumps({"datasets": [{"name": n, "source": d["source"], "kind": d["kind"], "rows": len(d["rows"])} for n, d in data.items()]}, indent=1), encoding="utf-8")
    # SOURCE_DATE_EPOCH (the reproducible-builds convention) pins the footer date, so rebuilding unchanged data gives byte-identical pages.
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    stamp = (dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc) if epoch else dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%d")
    version = con_version
    copy_assets(out)
    (out / G.GEO_URL).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / G.GEO_SOURCE, out / G.GEO_URL)
    extras = {"global": dict(hero=global_hero(site_cards.load_pages()["global"]), body_class="summary", extra_css=site_summary.CSS + GLOBAL_CSS_EXTRA)}
    for slug, (_title, body) in build_pages(data, chart_defs, facts).items():
        (out / f"{slug}.html").write_text(render_page(slug, body, stamp, version, **extras.get(slug, {})), encoding="utf-8")
    (out / f"{site_summary.SLUG}.html").write_text(site_summary.render(data, version)[0], encoding="utf-8")      # the one-page summary of the Data product tab
    problems = check_brand_boundary(out, local_logo=LOCAL_LOGO.exists())
    if problems:
        shutil.rmtree(out)
        raise SystemExit("SITE BUILD REFUSED:\n  " + "\n  ".join(problems))
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return {"datasets": len(data), "charts": len(chart_defs), "pages": len(PAGES)}


def main(argv: list[str] | None = None) -> int:
    """`--public [--out DIR]` builds the deployable site: the git-ignored local logo is never included, whatever is on this machine."""
    argv = sys.argv[1:] if argv is None else argv
    out = OUT
    if "--public" in argv:
        global LOCAL_LOGO
        LOCAL_LOGO = ROOT / "local_assets" / "__none__"
    if "--out" in argv:
        out = Path(argv[argv.index("--out") + 1]).resolve()
    res = build(out=out)
    print(f"built {out.name}/: {res['pages']} pages, {res['charts']} charts, {res['datasets']} datasets (share_exec, approved aggregates, whitelisted evaluation summaries, governance metadata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
