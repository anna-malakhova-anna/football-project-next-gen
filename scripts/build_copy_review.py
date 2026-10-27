"""Build docs/product/copy-review.md: every card and roadmap row, with its copy as the site shows it, for Anna to approve or edit.

  uv run python -m scripts.build_copy_review          (run `make public` or `make site` first: the rendered copy is read from the built pages)

Per card: page, chart ID, demo-path flag and order, then each slot (headline, question, what it means for the club lens and the privacy lens, what to do for both, caution) with an approve / edit
column, and the reading-level score (Flesch-Kincaid grade, the same measure site_check uses; the limit is 9) for each lens. Demo-path charts come first. The text is the RENDERED copy (numbers filled from
the insight export), so a number can change when the data changes; the source of every slot is the key in site_src/copy/charts.yml. Page intros and the roadmap rows follow.
Nothing is edited here: Anna edits charts.yml and product_roadmap.csv, then sets `status: final`.
"""
from __future__ import annotations

import csv
import html
import re
import sys

import textstat
import yaml
from scripts.common import ROOT

PUBLIC = ROOT / "public"
SITE = ROOT / "site"
COPY = ROOT / "site_src" / "copy" / "charts.yml"
OUT = ROOT / "docs" / "product" / "copy-review.md"
PAGES = [("quality", "Data quality"), ("sure", "How sure are we?"), ("markets", "Club markets"), ("privacy", "Privacy by design"), ("product", "Data products"), ("global", "Global outlook")]
# The detailed walkthrough of each page (the slide tour; called the 5-minute path before 2026-10-27) = the charts its `demo_text` in charts.yml names, in order (checked by hand against the text printed beside each page below).
DEMO = {"quality": ["Q1", "Q3"], "sure": ["U1", "U3"], "markets": ["M1", "M3", "M5"], "privacy": ["P3", "P1"], "product": ["D1", "D2", "D4", "D6", "D7"], "global": ["G0", "G1", "G2", "G3", "G4", "G5"]}
SLOTS = [("headline", "headline_template"), ("question", "question"), ("means_club", "means_club"), ("means_privacy", "means_privacy"),
         ("action_club", "action_club"), ("action_privacy", "action_privacy"), ("caution", "caution")]
LIMIT = 9.0


def plain(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def cards_of(page_html: str) -> dict[str, dict]:
    out = {}
    for chunk in page_html.split('<article class="vcard"')[1:]:
        cid = re.search(r'data-card="([A-Z0-9]+)"', chunk).group(1)
        head = re.search(r'<h3 class="vcard-headline">(.*?)</h3>', chunk, re.S).group(1)
        head = re.sub(r'<span class="tag">.*?</span>', "", head, flags=re.S)
        q = re.search(r'<p class="vcard-question">(.*?)</p>', chunk, re.S).group(1)
        notes = {}
        for kind, _label, text in re.findall(r'<p class="vnote ([a-z-]+)"><b>(.*?)</b> (.*?)</p>', chunk, re.S):
            notes.setdefault(kind, []).append(plain(text))
        means = [n for n in re.findall(r'<p class="vnote (lens-[a-z]+)"><b>What this means\.</b> (.*?)</p>', chunk, re.S)]
        acts = [n for n in re.findall(r'<p class="vnote (lens-[a-z]+)"><b>What to do\.</b> (.*?)</p>', chunk, re.S)]
        out[cid] = dict(headline=plain(head), question=plain(q), means_club=plain(dict(means).get("lens-club", "")), means_privacy=plain(dict(means).get("lens-privacy", "")),
                        action_club=plain(dict(acts).get("lens-club", "")), action_privacy=plain(dict(acts).get("lens-privacy", "")),
                        caution=plain(re.search(r'<p class="vnote vcaution"><b>Be careful\.</b> (.*?)</p>', chunk, re.S).group(1)))
    return out


def grades(c: dict) -> tuple[float, float]:
    return tuple(round(textstat.flesch_kincaid_grade(" ".join([c["headline"], c[f"means_{lens}"], c[f"action_{lens}"], c["caution"]])), 1) for lens in ("club", "privacy"))


def approve(status: str) -> str:
    return "[x] approved (final) &nbsp; [ ] edit:" if status in ("final", "confirmed") else "[ ] approve &nbsp; [ ] edit:"


def flag(g: float) -> str:
    return f"**{g} (over {LIMIT:g})**" if g > LIMIT else str(g)


def intro_of(page_html: str) -> str:
    m = re.search(r"<p class='note intro'>(.*?)</p>", page_html, re.S)
    return plain(m.group(1)) if m else ""


def card_section(cid: str, page_title: str, c: dict, status: str, demo_rank: int | None) -> str:
    gc, gp = grades(c)
    path = f"demo path, step {demo_rank}" if demo_rank else "not on the demo path"
    lines = [f"### {cid}: {c['question']}", "",
             f"Page: **{page_title}** · Chart ID: **{cid}** · Demo path: **{'yes' if demo_rank else 'no'}** ({path}) · Copy status: `{status}` · Reading level: club lens {flag(gc)}, privacy lens {flag(gp)} (limit {LIMIT:g})", "",
             "| Slot | Text as the site shows it | Source key | Approve / edit |", "|---|---|---|---|"]
    for label, key in SLOTS:
        name = {"headline": "Headline", "question": "Question", "means_club": "What it means (club lens)", "means_privacy": "What it means (privacy lens)",
                "action_club": "What to do (club lens)", "action_privacy": "What to do (privacy lens)", "caution": "Be careful"}[label]
        lines.append(f"| {name} | {c[label].replace('|', '/')} | `{key}` | {approve(status)} |")
    lines.append("")
    return "\n".join(lines)


def roadmap_rows() -> str:
    targets = {r["gate_id"]: r for r in csv.DictReader((ROOT / "dbt/seeds/product_targets.csv").open(encoding="utf-8"))}
    out = ["| Product | Horizon | Version | Card title | Gate | Decision (owner: text) | Status | Reading level | Approve / edit |", "|---|---|---|---|---|---|---|---|---|"]
    order = {"DELIVERED": 0, "NOW": 1, "NEXT": 2, "LATER": 3}
    rows = sorted(csv.DictReader((ROOT / "dbt/seeds/product_roadmap.csv").open(encoding="utf-8")), key=lambda r: (r["product_id"], order[r["horizon"]]))
    for r in rows:
        g = targets.get(r["gate_id"]) if r["gate_id"] else None
        gate = f"{r['gate_id']}: {g['plain_name'] or g['metric']}, {g['comparison']} {g['threshold_value']} {g['unit']} (baseline {g['baseline_2025'] or 'pending'})" if g else ""
        dec = f"{r['decision_owner_role']}: {r['decision_text']}" if r["decision_text"] else ""
        text = " ".join(x for x in [r["title"], dec] if x)
        grade = round(textstat.flesch_kincaid_grade(text), 1)
        out.append(f"| {r['product_id']} | {r['horizon'].title()} | {r['version']} | {r['title'].replace('|', '/')} | {gate} | {dec} | `{r['status']}` | {flag(grade)} | {approve(r['status'])} |")
    return "\n".join(out)


def main() -> int:
    base = PUBLIC if PUBLIC.exists() else SITE
    copy = yaml.safe_load(COPY.read_text(encoding="utf-8"))
    status = {k: v.get("status", "?") for k, v in copy["charts"].items()}
    pages_copy = copy.get("pages", {})
    found: dict[str, tuple[str, dict]] = {}
    intros = {}
    for slug, title in PAGES:
        f = base / f"{slug}.html"
        if not f.exists():
            print(f"missing {f}: run make public first", file=sys.stderr)
            return 1
        h = f.read_text(encoding="utf-8")
        intros[slug] = intro_of(h)
        for cid, c in cards_of(h).items():
            found[cid] = (title, c)
    missing = set(status) - set(found)
    if missing:
        print(f"cards in charts.yml not on any built page: {sorted(missing)}", file=sys.stderr)
        return 1
    demo_rank = {cid: i for slug, ids in DEMO.items() for i, cid in enumerate(ids, 1)}
    demo_ids = [cid for slug, _ in PAGES for cid in DEMO[slug]]
    rest = [cid for slug, _ in PAGES for cid in found if found[cid][0] == dict(PAGES)[slug] and cid not in demo_rank]
    all_grades = {cid: grades(found[cid][1]) for cid in found}
    over = [cid for cid, g in all_grades.items() if max(g) > LIMIT]
    out = ["# Copy review", "",
           "Generated by `scripts/build_copy_review.py` from the built site and `site_src/copy/charts.yml`. **Anna approves or edits each slot**; edit `site_src/copy/charts.yml` (the key is in each row) or `dbt/seeds/product_roadmap.csv`, "
           "then set `status: final` on the entry. Every entry is `draft` until then, and the build prints a warning while any is. Synthetic data; the numbers in the text move when the data does.", "",
           f"- **{len(found)} cards** ({len(demo_ids)} on the demo path), **{len(PAGES)} page intros**, **{sum(1 for _ in csv.DictReader((ROOT / 'dbt/seeds/product_roadmap.csv').open(encoding='utf-8')))} roadmap rows**.",
           f"- Reading level is the Flesch-Kincaid grade of headline + what it means + what to do + caution, per lens (the measure `site_check` enforces, limit {LIMIT:g}). "
           + ("Over the limit: " + ", ".join(over) + "." if over else "Every card is within the limit."),
           "- How to mark a row: change `[ ]` to `[x]` for approve, or write the new wording after `edit:`. A row already marked `[x] approved (final)` has `status: final` (or `confirmed`) in its source.", "",
           "## Summary", "", "| Order | Chart | Page | Demo path | Question | Reading level (club / privacy) | Copy status |", "|---|---|---|---|---|---|---|"]
    for i, cid in enumerate(demo_ids + rest, 1):
        title, c = found[cid]
        gc, gp = all_grades[cid]
        out.append(f"| {i} | {cid} | {title} | {'yes, step ' + str(demo_rank[cid]) if cid in demo_rank else 'no'} | {c['question']} | {flag(gc)} / {flag(gp)} | `{status[cid]}` |")
    out += ["", "## 1. Demo-path charts", "",
            "These are the charts the detailed walkthrough on each page steps through, in order. The path text on each page is in section 3 (`demo_text`).", ""]
    for cid in demo_ids:
        out.append(card_section(cid, found[cid][0], found[cid][1], status[cid], demo_rank[cid]))
    out += ["## 2. Other charts", ""]
    for cid in rest:
        out.append(card_section(cid, found[cid][0], found[cid][1], status[cid], None))
    out += ["## 3. Page intros and demo-path text", "", "| Page | Intro as the site shows it | Source key | Demo-path text (`demo_text`) | Status | Approve / edit |", "|---|---|---|---|---|---|"]
    for slug, title in PAGES:
        p = pages_copy.get(slug, {})
        out.append(f"| {title} | {intros[slug].replace('|', '/')} | `pages.{slug}.intro_template` | {p.get('demo_text', '').replace('|', '/')} | `{p.get('status', '?')}` | {approve(p.get('status', '?'))} |")
    out += ["", "## 4. Roadmap rows", "",
            "The 14 rows of `dbt/seeds/product_roadmap.csv` (the cards on the roadmap board, grouped by product). Gate values come from the gates model at build time, not from this text. The roadmap card itself (D10) is in section 1 or 2. A card title is a few words, so its reading-level score is unreliable (a short fragment of technical nouns scores high); read it as a prompt to check the wording, not as a failure.", "",
            roadmap_rows(), ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(found)} cards ({len(demo_ids)} on the demo path), {len(PAGES)} page intros, roadmap rows; over the reading limit: {over or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
