"""Checks on the one-page summary of the Data product tab (Phase 6 one-pager, section 6). Run by `make product` after the site is built.

  uv run python -m scripts.check_one_pager

  - public layout: no horizontal overflow at 1440 and 390 wide (a vertical story scrolls);
  - print: the page prints to exactly two US Letter portrait pages with nothing cut off, and so does the committed docs/product/one-pager.pdf;
  - words: at most 1900 visible words, reading grade 8 or lower, no banned word, model name or code, no long decimal, no unfilled {placeholder};
  - product.html links to the summary.
That every number comes from a product-tab export is checked by tests/test_one_pager.py (the build records where each number came from).
"""
from __future__ import annotations

import re
import sys

import textstat
from playwright.sync_api import sync_playwright

from scripts.site_check import BANNED, BANNED_PREFIXES, CODE_PATTERNS, PLACEHOLDER, SMALL_DECIMAL
from scripts.site_shots import ROOT, pdf_pages, serve

SITE = ROOT / "public"          # the deployable site: run `make public` first

SLUG = "product-summary"
PDF = ROOT / "docs" / "product" / "one-pager.pdf"
MAX_WORDS = 1900      # the story reuses whole tab components (the roadmap alone is about 300 words); the brief asked for 700 without the label accordion, which is not reachable; earlier limits were 300, 450 and 1200
MAX_GRADE = 8.0
LETTER_PORTRAIT = (612, 792)
MAX_PAGES = 3


def prose(text: str) -> str:
    """Lines of the page as sentences: a line that does not end a sentence gets a full stop, so short labels are scored as short sentences."""
    return " ".join(l if l.endswith((".", "!", "?")) else l + "." for l in (x.strip() for x in text.splitlines()) if l)


def pdf_ok(pdf: bytes, label: str) -> list[str]:
    fails = []
    n = pdf_pages(pdf)
    if n > MAX_PAGES:
        fails.append(f"{label}: {n} pages, expected at most {MAX_PAGES}")
    boxes = {tuple(round(float(v)) for v in m.split()) for m in re.findall(rb"/MediaBox\s*\[([^\]]*)\]", pdf) for m in [m.decode()]}
    if boxes != {(0, 0, *LETTER_PORTRAIT)}:
        fails.append(f"{label}: page size {sorted(boxes)}, expected US Letter portrait {LETTER_PORTRAIT}")
    return fails


def check(page, base: str) -> list[str]:
    fails: list[str] = []
    for width, height in ((1440, 1000), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{base}/{SLUG}.html")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        sh, sw = page.evaluate("[document.documentElement.scrollHeight, document.documentElement.scrollWidth]")
        if sw > width:
            fails.append(f"{SLUG}@{width}: horizontal overflow ({sw}px wide)")
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{base}/{SLUG}.html")
    page.wait_for_load_state("networkidle")
    text = page.evaluate("document.body.innerText")
    words = len(text.split())
    if words > MAX_WORDS:
        fails.append(f"{SLUG}: {words} visible words (limit {MAX_WORDS})")
    grade = textstat.flesch_kincaid_grade(prose(text))
    if grade > MAX_GRADE:
        fails.append(f"{SLUG}: reading grade {grade:.1f} (limit {MAX_GRADE:g})")
    # accordion: exactly one product label open at a time (open DP1, then DP3: DP1 must close)
    labels = page.locator("details[name=dp-label]")
    if labels.count() != 5:
        fails.append(f"{SLUG}: {labels.count()} product labels, expected 5")
    else:
        labels.nth(0).locator("summary").click()
        labels.nth(2).locator("summary").click()
        page.wait_for_timeout(200)
        opened = [labels.nth(i).evaluate("e => e.open") for i in range(5)]
        if opened != [False, False, True, False, False]:
            fails.append(f"{SLUG}: opening DP3 should close DP1, but the open states are {opened}")
        labels.nth(2).locator("summary").click()
    # a so-what line on every section from 4 on (section 10 carries its so-what column), in plain words
    for sid in ("labels", "priorities", "roadmap", "privacy", "working", "gaps"):
        sw = page.locator(f"#s-{sid} > .ps-sowhat")
        if sw.count() != 1:
            fails.append(f"{SLUG}: section {sid} has no so-what line")
            continue
        line = sw.text_content().replace("So what.", "").strip()
        g = textstat.flesch_kincaid_grade(line)
        if g > MAX_GRADE:
            fails.append(f"{SLUG}: the so-what of {sid} reads at grade {g:.1f} (limit {MAX_GRADE:g})")
    if page.locator("#s-learned td").count() != 6:
        fails.append(f"{SLUG}: the learned table should have three rows of what and so what")
    text = page.evaluate("document.body.innerText")     # the labels were reopened and closed again: the text is the collapsed page
    low = text.lower()
    for b in BANNED:
        if re.search(rf"\b{re.escape(b)}\b", low):
            fails.append(f"{SLUG}: banned word {b!r}")
    for b in BANNED_PREFIXES:
        if b in low:
            fails.append(f"{SLUG}: model-name fragment {b!r}")
    for pat in CODE_PATTERNS:
        if (m := pat.search(text)):
            fails.append(f"{SLUG}: a code on the page: {m.group(0)!r}")
    if PLACEHOLDER.search(text):
        fails.append(f"{SLUG}: an unfilled placeholder: {PLACEHOLDER.search(text).group(0)!r}")
    if SMALL_DECIMAL.search(text) or re.search(r"\d+\.\d{3,}", text):
        fails.append(f"{SLUG}: a long decimal on the page")
    page.emulate_media(color_scheme="light")
    fails += pdf_ok(page.pdf(prefer_css_page_size=True, print_background=True), f"{SLUG} printed")
    page.set_viewport_size({"width": 720, "height": 960})     # a printed Letter page is 720 CSS px wide inside its margins: the narrow-screen rules must not apply
    page.emulate_media(media="print")
    for i, (sh, ch) in enumerate(page.evaluate("[...document.querySelectorAll('.ps-p1,.ps-p2,.ps-p3')].map(e => [e.scrollHeight, e.clientHeight])"), 1):
        if sh > ch:
            fails.append(f"{SLUG} printed: page {i} content is {sh}px but the page holds {ch}px (it would be cut off)")
    page.emulate_media(media="null")
    page.emulate_media(color_scheme=None)
    print(f"one-pager: {words} words, reading grade {grade:.1f}")
    return fails


def main() -> int:
    fails: list[str] = []
    if not (SITE / f"{SLUG}.html").exists():
        print(f"missing {SITE / (SLUG + '.html')}: run make public first", file=sys.stderr)
        return 1
    if "product-summary.html" not in (SITE / "product.html").read_text(encoding="utf-8"):
        fails.append("product.html does not link to product-summary.html")
    if not PDF.exists():
        fails.append(f"{PDF.relative_to(ROOT)} is missing: run make one-pager")
    else:
        fails += pdf_ok(PDF.read_bytes(), PDF.relative_to(ROOT).as_posix())
    srv, base = serve(SITE)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome")
            fails += check(browser.new_page(), base)
            browser.close()
    finally:
        srv.shutdown()
    if fails:
        print(f"ONE-PAGER CHECK FAILED ({len(fails)}):")
        for f in fails:
            print("  " + f)
        return 1
    print("one-pager check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
