"""Screenshots and print page counts of the built site (Phase 5.1). Needs Chrome (Playwright drives the installed Chrome; nothing is downloaded).

  uv run python -m scripts.site_shots --out docs/reports/site_baseline [--pages quality markets ...]

For every page: a screenshot at 1440x900 and 390x844 (the full page, capped at MAX_SHOT_HEIGHT pixels so a runaway chart cannot produce an unreadable image), the document height,
the tallest chart element, and the print-to-PDF page count. Writes <out>/<page>_<width>.png and <out>/pages.csv.
"""
from __future__ import annotations

import argparse
import csv
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
VIEWPORTS = {"1440": (1440, 900), "390": (390, 844)}
MAX_SHOT_HEIGHT = 7000


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(directory: Path = SITE) -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def pdf_pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf))


def settle(page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)                                  # vega-embed renders asynchronously


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--pages", nargs="*")
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    pages = args.pages or sorted(p.stem for p in SITE.glob("*.html"))
    srv, base = serve()
    rows = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome")
            for name in pages:
                for label, (w, h) in VIEWPORTS.items():
                    ctx = browser.new_context(viewport={"width": w, "height": h})
                    page = ctx.new_page()
                    page.goto(f"{base}/{name}.html")
                    settle(page)
                    doc_h = page.evaluate("document.documentElement.scrollHeight")
                    tallest = page.evaluate("Math.max(0, ...Array.from(document.querySelectorAll('.chart svg, .chart canvas, .chart .vega-embed')).map(e => e.getBoundingClientRect().height))")
                    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                    page.screenshot(path=str(out / f"{name}_{label}.png"), full_page=False, clip={"x": 0, "y": 0, "width": w, "height": min(doc_h, MAX_SHOT_HEIGHT)}, scale="css") if doc_h > h else page.screenshot(path=str(out / f"{name}_{label}.png"))
                    pdf_n = ""
                    if label == "1440":
                        pdf_n = pdf_pages(page.pdf(format="A4", print_background=True))
                    rows.append(dict(page=name, viewport=label, document_height=doc_h, tallest_chart=round(tallest), horizontal_overflow=overflow, print_pages=pdf_n))
                    ctx.close()
            browser.close()
    finally:
        srv.shutdown()
    with open(out / "pages.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
