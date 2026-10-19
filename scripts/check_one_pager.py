"""Checks on the one-page summary of the Data product tab (Phase 6 one-pager, section 6). Run by `make product` after the site is built.

  uv run python -m scripts.check_one_pager

  - public layout: no vertical scroll at 1440x900, no horizontal overflow at 1440 and 390 wide;
  - print: the page prints to exactly one US Letter landscape page, and so does the committed docs/product/one-pager.pdf;
  - words: at most 300 visible words, reading grade 8 or lower, no banned word, model name or code, no long decimal, no unfilled {placeholder};
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
MAX_WORDS = 300
MAX_GRADE = 8.0
LETTER_LANDSCAPE = (792, 612)


def prose(text: str) -> str:
    """Lines of the page as sentences: a line that does not end a sentence gets a full stop, so short labels are scored as short sentences."""
    return " ".join(l if l.endswith((".", "!", "?")) else l + "." for l in (x.strip() for x in text.splitlines()) if l)


def pdf_ok(pdf: bytes, label: str) -> list[str]:
    fails = []
    n = pdf_pages(pdf)
    if n != 1:
        fails.append(f"{label}: {n} pages, expected exactly 1")
    boxes = {tuple(round(float(v)) for v in m.split()) for m in re.findall(rb"/MediaBox\s*\[([^\]]*)\]", pdf) for m in [m.decode()]}
    if boxes != {(0, 0, *LETTER_LANDSCAPE)}:
        fails.append(f"{label}: page size {sorted(boxes)}, expected US Letter landscape {LETTER_LANDSCAPE}")
    return fails


def check(page, base: str) -> list[str]:
    fails: list[str] = []
    for width, height in ((1440, 900), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{base}/{SLUG}.html")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        sh, sw = page.evaluate("[document.documentElement.scrollHeight, document.documentElement.scrollWidth]")
        if width == 1440 and sh > 900:
            fails.append(f"{SLUG}@1440: the page is {sh}px tall; it must fit 900px with no scrolling")
        if sw > width:
            fails.append(f"{SLUG}@{width}: horizontal overflow ({sw}px wide)")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{base}/{SLUG}.html")
    page.wait_for_load_state("networkidle")
    text = page.evaluate("document.body.innerText")
    words = len(text.split())
    if words > MAX_WORDS:
        fails.append(f"{SLUG}: {words} visible words (limit {MAX_WORDS})")
    grade = textstat.flesch_kincaid_grade(prose(text))
    if grade > MAX_GRADE:
        fails.append(f"{SLUG}: reading grade {grade:.1f} (limit {MAX_GRADE:g})")
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
