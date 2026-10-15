"""Chart cards and the full-screen viewer (Phase 5.1, section 5.1 to 5.3).

A card shows a plain-language headline (a template from site_src/copy/charts.yml filled with numbers from the insight export, by string substitution only), the question, a fixed-height thumbnail,
and three short notes. Its slides (one per use, market, example ...) are written into the page as JSON; site_src/assets/viewer.js shows them full screen. No number is computed here or in the browser:
every number in a sentence is a `value_display` string that SQL already rounded.
"""
from __future__ import annotations

import json
import re
import sys
from html import escape as e
from pathlib import Path

import yaml

COPY_PATH = Path(__file__).resolve().parent.parent / "site_src" / "copy" / "charts.yml"
PLACEHOLDER = re.compile(r"\{([a-z0-9_]+)\}")
_state: dict = {"copy": {}, "insights": {}}


def load_copy(path: Path = COPY_PATH) -> dict:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("charts", {})


def configure(insight_rows: list[dict], copy: dict | None = None) -> None:
    """Index the insight export by (chart_id, field). A field must be unique per chart, whatever its lens."""
    idx: dict = {}
    for r in insight_rows:
        key = (r["chart_id"], r["field"])
        if key in idx:
            raise SystemExit(f"SITE BUILD REFUSED:\n  insight field {key} appears twice")
        idx[key] = r
    _state["insights"] = idx
    _state["copy"] = load_copy() if copy is None else copy
    drafts = sorted(k for k, v in _state["copy"].items() if v.get("status") == "draft")
    if drafts:
        print(f"WARNING: {len(drafts)} chart entries are still `status: draft` in site_src/copy/charts.yml ({', '.join(drafts)}); Anna reviews them before the final build.", file=sys.stderr)


def fill(template: str, chart_id: str, fallback: str | None) -> str:
    """Substitute {field} with value_display. A missing field fails the build unless the entry declares a fallback headline with no numbers."""
    missing: list[str] = []

    def sub(m):
        row = _state["insights"].get((chart_id, m.group(1)))
        if row is None or row["value_display"] is None:
            missing.append(m.group(1))
            return m.group(0)
        return str(row["value_display"])

    out = PLACEHOLDER.sub(sub, template)
    if missing:
        if fallback is not None:
            return fallback
        raise SystemExit(f"SITE BUILD REFUSED:\n  {chart_id}: no insight value for {missing}")
    return out


def safe_md(text: str) -> str:
    """A deliberately tiny renderer: everything is escaped first, then **bold**, *italic*, `code` and blank-line paragraphs. No raw HTML, no links."""
    paras = []
    for block in re.split(r"\n\s*\n", e(text.strip())):
        block = re.sub(r"`([^`]+)`", r"<code>\1</code>", block)
        block = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", block)
        block = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", block)
        paras.append(f"<p>{block}</p>")
    return "".join(paras)


def card_block(cid: str, ch: dict, data: dict, table_html) -> str:
    """HTML for one card plus its slides. `ch['card']` = dict(id, thumb, slides=[dict(title, spec)], open_slide, datasets)."""
    card = ch["card"]
    cp = _state["copy"].get(card["id"])
    if cp is None:
        raise SystemExit(f"SITE BUILD REFUSED:\n  {card['id']}: no entry in site_src/copy/charts.yml")
    headline = fill(cp["headline_template"], card["id"], cp.get("fallback_headline"))
    n = len(card["slides"])
    open_id = f"{card['id']}-{card.get('open_slide', 1)}"
    tables = "".join(f"<p class='note'><b>{e(data[d]['title'])}</b> <code>{e(data[d]['source'])}</code></p>{table_html(data[d])}" for d in card["datasets"])
    per_slide = cp.get("slide_headline_templates", {})

    def slide_headline(s) -> str:
        t = per_slide.get(s.get("key"))
        return fill(t, card["id"], headline) if t else headline

    slides = "".join(
        f'<script type="application/json" class="vspec" data-id="{card["id"]}-{i}" data-card="{card["id"]}" data-title="{e(s["title"])}" data-headline="{e(slide_headline(s))}">{json.dumps(s["spec"])}</script>'
        for i, s in enumerate(card["slides"], 1))
    thumb = f'<script type="application/json" id="thumb-{card["id"]}-spec">{json.dumps(card["thumb"])}</script>'
    tag = '<span class="tag">Synthetic evaluation — not observable in production</span>' if ch.get("evaluation") else ""
    return (
        f'<article class="vcard" id="card-{card["id"]}" data-card="{card["id"]}" data-slides="{n}">'
        f'<div class="vcard-copy"><h3 class="vcard-headline">{e(headline)}{tag}</h3><p class="vcard-question">{e(cp["question"])}</p></div>'
        f'<div class="vthumb-wrap"><button type="button" class="vthumb" data-open="{open_id}" aria-label="Open the full-screen view: {e(cp["question"])}">'
        f'<span class="vthumb-box" id="thumb-{card["id"]}" role="img" aria-label="{e(headline)}"></span></button>'
        f'<button type="button" class="vexpand" data-open="{open_id}" aria-label="Expand: {e(cp["question"])}">Expand ⤢</button></div>'
        f'<div class="vcard-notes">'
        f'<p class="vnote lens-club"><b>What this means.</b> {e(cp["means_club"])}</p><p class="vnote lens-privacy"><b>What this means.</b> {e(cp["means_privacy"])}</p>'
        f'<p class="vnote lens-club"><b>What to do.</b> {e(cp["action_club"])}</p><p class="vnote lens-privacy"><b>What to do.</b> {e(cp["action_privacy"])}</p>'
        f'<p class="vnote vcaution"><b>Be careful.</b> {e(cp["caution"])}</p></div>'
        f'<details class="vanalyst"><summary>For analysts</summary><div class="vanalyst-body">{safe_md(cp.get("analyst_md", ""))}{tables}</div></details>'
        f'{thumb}{slides}</article>')
