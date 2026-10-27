"""Layout, content and viewer checks on the built site (Phase 5.1, section 7). Playwright drives the installed Chrome against the locally served site/.

  uv run python -m scripts.site_check              # the four Phase 5 pages
  uv run python -m scripts.site_check --ci         # three pages (Data quality, Club markets and Data product): the same checks, kept short for CI
  uv run python -m scripts.site_check --pages quality

Exit code 1 and one line per failure. Nothing here computes a number for the site; it only reads what the build produced.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import textstat
from playwright.sync_api import sync_playwright

from scripts.site_shots import SITE, pdf_pages, serve

PAGES = ["product", "quality", "sure", "markets", "privacy", "global"]
CI_PAGES = ["quality", "markets", "product", "global"]
MAX_PRINT_PAGES = 12
MAX_THUMB_PX = 320
BANNED = ["interval", "lower bound", "upper bound", "p-chart", "control limit", "sigma", "dimension", "registry", "cumulative share", "additive", "allocated", "attribution", "imputation",
          "mnar", "missing not at random", "manski", "wilson", "k-anonymity", "equivalence class", "quasi-identifier", "provenance", "suppression", "cohort", "censored", "purpose score",
          "grain", "schema"]
BANNED_PREFIXES = ["share_", "mart_", "dq_", "eval_"]
CODE_PATTERNS = [re.compile(r"\b(?:DQ|CM)-[A-Z0-9-]+\b"), re.compile(r"\b[a-z]+_[a-z_]+\b"), re.compile(r"\b(?:COUNT|SEGMENT|GEO|RETAIN|ACTIVATE)\b")]
LONG_DECIMAL = re.compile(r"\d+\.\d{3,}")
SMALL_DECIMAL = re.compile(r"\b0\.\d{3,}")   # Phase 6 one-pager: no visible value like 0.0906 on the product pages
PRODUCT_PAGES = {"product", "product-summary"}
PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_.]+\}")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


def words(s: str) -> int:
    return len(s.split())


def lay_text(card) -> dict:
    """The lay-text slots of a card, outside the collapsed analyst section."""
    return card.evaluate("""el => {
        const t = s => { const n = el.querySelector(s); return n ? n.textContent.trim() : ''; };
        const all = s => Array.from(el.querySelectorAll(s)).map(n => n.textContent.trim());
        return { headline: (() => { const h = el.querySelector('.vcard-headline'); if (!h) return ''; const c = h.cloneNode(true); c.querySelectorAll('.tag').forEach(x => x.remove()); return c.textContent.trim(); })(), question: t('.vcard-question'), means: all('.vnote.lens-club, .vnote.lens-privacy').filter(x => x.startsWith('What this means')),
                 action: all('.vnote.lens-club, .vnote.lens-privacy').filter(x => x.startsWith('What to do')), caution: t('.vcaution') };
    }""")


def check_page(page, base: str, slug: str, insights: set[str]) -> list[str]:
    fails: list[str] = []
    bad = fails.append
    for width, height in ((1440, 900), (1024, 768), (768, 1024), (390, 844)):     # desktop, small laptop window, tablet, phone
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{base}/{slug}.html")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        # ---- layout
        over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        if over > 1:
            bad(f"{slug}@{width}: the page is {over}px wider than the window")
        for el in page.locator(".vcard").all():
            w = el.evaluate("e => [e.scrollWidth, e.clientWidth]")
            if w[0] > w[1] + 1:
                bad(f"{slug}@{width}: card {el.get_attribute('data-card')} is wider than its box ({w[0]} > {w[1]})")
        for th in page.locator(".vthumb").all():
            h = th.bounding_box()["height"]
            if h > MAX_THUMB_PX:
                bad(f"{slug}@{width}: a card thumbnail is {h:.0f}px tall (limit {MAX_THUMB_PX})")
        for t in page.locator(".vthumb svg text").all():
            if (t.text_content() or "").rstrip().endswith("…"):
                bad(f"{slug}@{width}: truncated label in a thumbnail: {t.text_content()!r}")
    if slug == "product":
        fails += check_roadmap(page, base)
    fails += check_tables(page, base, slug)
    # ---- print page count
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{base}/{slug}.html")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)
    n = pdf_pages(page.pdf(format="A4"))
    if n > MAX_PRINT_PAGES:
        bad(f"{slug}: prints on {n} pages (limit {MAX_PRINT_PAGES})")
    # ---- content: cards
    cards = page.locator(".vcard").all()
    if not cards:
        bad(f"{slug}: no chart cards on the page")
    for card in cards:
        cid = card.get_attribute("data-card")
        t = lay_text(card)
        if not (t["headline"] and t["question"] and t["caution"]) or len(t["means"]) != 2 or len(t["action"]) != 2:
            bad(f"{slug}/{cid}: a slot is empty (headline, question, means x2, action x2, caution)")
            continue
        if words(t["headline"]) > 15:
            bad(f"{slug}/{cid}: headline has {words(t['headline'])} words (limit 15): {t['headline']!r}")
        if PLACEHOLDER.search(" ".join([t["headline"], *t["means"], *t["action"], t["caution"]])):
            bad(f"{slug}/{cid}: an unfilled {{placeholder}}")
        for lens in (0, 1):
            text = " ".join([t["headline"], t["means"][lens], t["action"][lens], t["caution"]])
            grade = textstat.flesch_kincaid_grade(text)
            if grade > 9:
                bad(f"{slug}/{cid}: reading grade {grade:.1f} (limit 9) for lens {lens}")
            for s in re.split(r"(?<=[.!?])\s+", text):
                if words(s) > 25:
                    bad(f"{slug}/{cid}: a sentence of {words(s)} words (limit 25)")
        visible = " ".join([t["headline"], t["question"], *t["means"], *t["action"], t["caution"]])
        low = visible.lower()
        for b in BANNED:
            if re.search(rf"\b{re.escape(b)}\b", low):
                bad(f"{slug}/{cid}: banned word {b!r} outside the analyst section")
        for b in BANNED_PREFIXES:
            if b in low:
                bad(f"{slug}/{cid}: model-name fragment {b!r} outside the analyst section")
        for pat in CODE_PATTERNS:
            m = pat.search(visible)
            if m:
                bad(f"{slug}/{cid}: a code in lay text: {m.group(0)!r}")
        if LONG_DECIMAL.search(visible):
            bad(f"{slug}/{cid}: a long decimal in lay text: {LONG_DECIMAL.search(visible).group(0)!r}")
        for num in NUMBER.findall(t["headline"]):
            if not any(num in v for v in insights):
                bad(f"{slug}/{cid}: the number {num!r} in the headline is not in an insight export")
    intro = page.locator(".intro").first
    if intro.count():
        text = intro.text_content().strip()
        if not text.endswith((".", "!", "?")):
            bad(f"{slug}: the intro does not end with a sentence ending: {text[-30:]!r}")
        for pat in CODE_PATTERNS:
            if pat.search(text):
                bad(f"{slug}: a code in the intro: {pat.search(text).group(0)!r}")
        if PLACEHOLDER.search(text) or LONG_DECIMAL.search(text):
            bad(f"{slug}: an unfilled placeholder or long decimal in the intro")
    # ---- rendered chart text anywhere on the page
    for t in page.locator("svg text").all():
        s = (t.text_content() or "").strip()
        if s.endswith("…"):
            bad(f"{slug}: truncated chart text {s!r}")
        if LONG_DECIMAL.search(s):
            bad(f"{slug}: a long decimal in a chart: {s!r}")
    # ---- viewer
    declared = sum(int(c.get_attribute("data-slides")) for c in cards)
    shipped = page.locator("script.vspec").count()
    if declared != shipped:
        bad(f"{slug}: cards declare {declared} slides but {shipped} are on the page")
    if cards:
        trigger = page.locator(".vexpand").first
        trigger.click()
        page.wait_for_timeout(900)
        if not page.evaluate("document.querySelector('dialog.viewer').open"):
            bad(f"{slug}: Expand did not open the viewer")
        else:
            built = page.locator("dialog.viewer section.vslide").count()
            if built != declared:
                bad(f"{slug}: the viewer holds {built} slides, the cards declare {declared}")
            first = page.inner_text(".vcount")
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(700)
            if page.inner_text(".vcount") == first:
                bad(f"{slug}: the arrow key did not advance the viewer")
            vh = page.viewport_size["height"]
            for i in range(min(declared, 40)):
                page.wait_for_timeout(350)
                for box in page.locator("dialog.viewer .vslide-chart svg").all():
                    bb = box.bounding_box()
                    if bb and bb["height"] > 1.2 * vh:
                        bad(f"{slug}: a chart in the viewer is {bb['height']:.0f}px tall (limit {1.2 * vh:.0f})")
                page.keyboard.press("ArrowDown")
            for t in page.locator("dialog.viewer svg text").all():
                if (t.text_content() or "").strip().endswith("…"):
                    bad(f"{slug}: truncated chart text in the viewer: {t.text_content()!r}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            if page.evaluate("document.querySelector('dialog.viewer').open"):
                bad(f"{slug}: Esc did not close the viewer")
            if not page.evaluate("document.activeElement && document.activeElement.classList.contains('vexpand')"):
                bad(f"{slug}: focus did not return to the Expand button")
        page.goto(f"{base}/{slug}.html#view={cards[0].get_attribute('data-card')}-1")
        page.reload()
        page.wait_for_timeout(1500)
        if not page.evaluate("document.querySelector('dialog.viewer').open"):
            bad(f"{slug}: a #view= link did not open the viewer")
    if slug == "markets":
        html = (SITE / "markets.html").read_text(encoding="utf-8")
        club, priv = html.count("Club lens \\u00b7"), html.count("Privacy lens \\u00b7")
        if not club == priv >= 6:
            bad(f"markets: the two-lenses panels are not paired (club {club}, privacy {priv})")
    return fails


TABLE_JS = r"""(sel) => {
  const out = [];
  const vis = (el) => { if (!(el.offsetParent || el.getClientRects().length)) return false; const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < window.innerHeight && r.right > 0 && r.left < window.innerWidth; };
  const tw = (cs, str) => { const c = document.createElement('canvas').getContext('2d'); c.font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily; return c.measureText(str).width; };
  const measure = (cs) => { const c = document.createElement('canvas').getContext('2d'); c.font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily; return c.measureText('0').width; };
  const root = sel ? document.getElementById(sel) : document;
  root.querySelectorAll('table').forEach((t) => {
    if (!vis(t) || t.closest('.vanalyst:not([open])')) return;
    const name = (t.closest('.vcard, dialog, section, main') || document.body).id || 'table';
    if (t.scrollWidth > t.clientWidth + 1 || (t.parentElement && t.getBoundingClientRect().right > window.innerWidth + 1)) out.push(name + ': a table is wider than the window');
    t.querySelectorAll('td, th').forEach((c) => {
      if (!vis(c)) return;
      const hd = c.closest('thead'); if (hd && hd.getBoundingClientRect().width <= 2) return;   // the header row of a stacked table is hidden on purpose
      const text = (c.innerText || '').replace(/\s+/g, ' ').trim();
      if (!text) return;
      const cs = getComputedStyle(c);
      const inner = c.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      if (text.length >= 4 && inner < 4 * measure(cs) - 0.5 && (c.scrollWidth > c.clientWidth + 1 || text.split(' ').some((w) => w.length > 1 && tw(cs, w) > inner + 1))) out.push(name + ': a cell is narrower than 4 characters (' + Math.round(inner) + 'px): ' + text.slice(0, 30));
      if (c.querySelector('details, ul, ol, p, div, table, h4, h5')) return;
      const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.25;
      const rg = document.createRange(); rg.selectNodeContents(c); const h = rg.getBoundingClientRect().height;
      const lines = Math.round(h / lh), nwords = text.split(' ').length;
      if (cs.display !== 'block' && lines > nwords) out.push(name + ': a word is broken across lines in a cell (' + lines + ' lines, ' + nwords + ' words): ' + text.slice(0, 30));
      if (cs.display === 'block' && text.length < 20 && lines > 1 && !/\s/.test(text)) out.push(name + ': a short value wraps: ' + text);
    });
  });
  return out;
}"""


def lint_table_cells(slug: str) -> list[str]:
    """The code-pattern lint of 5.1 applied to table cells: visible cell text (outside the analyst sections) holds no model name or code."""
    src = (SITE / f"{slug}.html").read_text(encoding="utf-8").replace("<\\/", "</")
    src = re.sub(r"<details class=[\"']v(?:analyst|row-detail)[\"'].*?</details>", "", src, flags=re.S)
    fails = []
    for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", src, flags=re.S):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cell)).strip()
        if not text:
            continue
        low = text.lower()
        if slug in PRODUCT_PAGES and SMALL_DECIMAL.search(text):
            fails.append(f"{slug}: a table cell shows a raw decimal ({SMALL_DECIMAL.search(text).group(0)!r}): {text[:50]!r}")
        for b in BANNED_PREFIXES:
            if b in low:
                fails.append(f"{slug}: a table cell shows a model name ({b!r}): {text[:50]!r}")
        for pat in CODE_PATTERNS[:2]:
            m = pat.search(text)
            if m:
                fails.append(f"{slug}: a table cell shows a code ({m.group(0)!r}): {text[:50]!r}")
    return fails


def check_tables(page, base: str, slug: str) -> list[str]:
    """Phase 6 addendum: no cell under about four characters wide, no word broken across lines, no sideways overflow at 1440 or 390, on the page and in every viewer slide."""
    fails: list[str] = []
    for width, height in ((1440, 900), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{base}/{slug}.html")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        fails += [f"{slug}@{width}: {m}" for m in page.evaluate(TABLE_JS, None)]
        ids = page.evaluate("[...document.querySelectorAll('script.vspec[data-kind=html]')].map(e => e.dataset.id)")
        for sid in ids:
            page.evaluate(f"location.hash = '#view={sid}'")
            page.wait_for_timeout(500)
            fails += [f"{slug}@{width} slide {sid}: {m}" for m in page.evaluate(TABLE_JS, 'slide-' + sid)]
        page.evaluate("location.hash = ''")
    return fails + lint_table_cells(slug)


def check_roadmap(page, base: str) -> list[str]:
    """Phase 6 addendum, section 3: the roadmap fits 1440x900, nothing overflows, lanes stack at 390, a PENDING gate never renders as 0 or an empty bar, and values come only from the gates model."""
    fails: list[str] = []
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{base}/product.html")
    page.wait_for_load_state("networkidle")
    road = page.locator("[data-roadmap]")
    if road.count() != 1:
        return ["product: the roadmap section is missing"]
    box = road.bounding_box()
    if box["height"] > 780:     # the card headline and the roadmap must fit one 900px viewport
        fails.append(f"product: the roadmap is {box['height']:.0f}px tall at 1440x900 (limit 780)")
    if road.evaluate("e => e.scrollWidth - e.clientWidth") > 1:
        fails.append("product: the roadmap overflows sideways at 1440")
    lanes = page.locator(".vr-lane").count()
    if lanes != 5:
        fails.append(f"product: {lanes} roadmap lanes, expected 5")
    for g in page.locator(".vgate").all():
        text = g.inner_text()
        pending = "vg-pending" in (g.get_attribute("class") or "")
        if pending and (g.locator(".vgbar i").count() or "baseline pending" not in text.lower() or re.search(r"now 0\b", text)):
            fails.append(f"product: a PENDING gate is drawn as a value or a filled bar: {text!r}")
        if not pending and not g.locator(".vgbar i").count():
            fails.append(f"product: a gate with a value has an empty bar: {text!r}")
        if not re.search(r"Met|Not yet|pending", text):
            fails.append(f"product: a gate shows no status text (colour alone): {text!r}")
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{base}/product.html")
    page.wait_for_load_state("networkidle")
    cols = page.locator(".vr-lane").first.evaluate("e => getComputedStyle(e).gridTemplateColumns.split(' ').length")
    if cols != 1:
        fails.append(f"product: roadmap lanes do not stack at 390px ({cols} columns)")
    if page.evaluate("document.documentElement.scrollWidth - window.innerWidth") > 1:
        fails.append("product: the roadmap makes the page wider than the window at 390")
    if page.locator(".vr-head").first.is_visible():
        fails.append("product: the roadmap column header row still shows at 390 (each cell should carry its own column name)")
    return fails


def load_insights() -> set[str]:
    out: set[str] = set()
    for name in ("chart_insights_club", "chart_insights_privacy", "chart_insights_eval", "chart_insights_exec_global"):
        for r in json.loads((SITE / "data" / f"{name}.json").read_text())["rows"]:
            out.add(str(r["value_display"]))
    return out


PHONE = (390, 844)
PHONE_JS = r"""() => {
  const W = innerWidth, out = [];
  const hidden = e => e.closest('dialog, details:not([open]) > :not(summary)') || getComputedStyle(e).visibility === 'hidden';
  if (document.documentElement.scrollWidth > W + 1) out.push('the page is ' + (document.documentElement.scrollWidth - W) + 'px wider than a phone');
  for (const e of document.querySelectorAll('button, summary, [role=button], .demo-go, .vexpand, .ps-tabs a, .nav-trigger')) {
    const r = e.getBoundingClientRect(); if (!r.width || hidden(e)) continue;
    if (r.height < 40) out.push('a control is ' + Math.round(r.height) + 'px tall (min 40): "' + e.textContent.trim().slice(0, 40) + '"');
  }
  for (const e of document.querySelectorAll('main p, main li, main td, main th, main dd, main dt, main span:not(:has(*))')) {
    const r = e.getBoundingClientRect(); if (!r.width || r.width < 2 || !e.textContent.trim() || hidden(e) || e.closest('.vanalyst, h3, svg')) continue;
    const fs = parseFloat(getComputedStyle(e).fontSize); if (fs < 12) out.push('text is ' + fs + 'px (min 12): "' + e.textContent.trim().slice(0, 40) + '"');
  }
  for (const svg of document.querySelectorAll('main svg')) {
    if (hidden(svg)) continue;
    for (const t of svg.querySelectorAll('text')) { const r = t.getBoundingClientRect(); if (r.width && (r.right > W + 1 || r.left < -1)) { out.push('chart text runs off the screen: "' + t.textContent.slice(0, 40) + '"'); break; } }
  }
  return [...new Set(out)];
}"""


def check_phone(page, base: str, slug: str) -> list[str]:
    """Every page at phone width (ADR-037): no sideways scroll, controls tall enough to tap, reading text at least 12px, chart text on screen.
    Charts draw as they scroll into view, so the page is scrolled through first."""
    page.set_viewport_size({"width": PHONE[0], "height": PHONE[1]})
    page.goto(f"{base}/{slug}.html")
    page.wait_for_load_state("networkidle")
    height = page.evaluate("document.body.scrollHeight")
    for y in range(0, height, PHONE[1] - 100):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(100)
    page.wait_for_timeout(1200)
    return [f"{slug}@phone: {f}" for f in page.evaluate(PHONE_JS)]


def all_pages() -> list[str]:
    return sorted(p.stem for p in SITE.glob("*.html"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", nargs="*")
    ap.add_argument("--ci", action="store_true", help="two pages only")
    args = ap.parse_args()
    pages = args.pages or (CI_PAGES if args.ci else PAGES)
    insights = load_insights()
    srv, base = serve()
    fails: list[str] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome")
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for slug in pages:
                fails += check_page(page, base, slug, insights)
            phone = browser.new_page(is_mobile=True, has_touch=True, viewport={"width": PHONE[0], "height": PHONE[1]})
            for slug in (all_pages() if not args.pages else pages):     # every page, not only the card pages
                fails += check_phone(phone, base, slug)
            fails += [f"script error: {e}" for e in errors]
            browser.close()
    finally:
        srv.shutdown()
    if fails:
        print(f"SITE CHECK FAILED ({len(fails)}):")
        for f in sorted(set(fails)):
            print("  " + f)
        return 1
    print(f"site check OK: {len(pages)} pages ({', '.join(pages)}): layout, content and viewer; {len(all_pages()) if not args.pages else len(pages)} pages at phone width")
    return 0


if __name__ == "__main__":
    sys.exit(main())
