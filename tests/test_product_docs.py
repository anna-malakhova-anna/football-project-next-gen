"""Phase 6: the product docs link only to things that exist, cite the framework once, and every canvas has the same headings."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = [*ROOT.joinpath("docs", "product").rglob("*.md"), *ROOT.joinpath("products").rglob("*.md")]
HEADINGS = ["Customer", "Problem", "Value proposition", "Consumption type", "Product type", "Owner role and supporting roles", "Key dependencies", "What we will NOT do", "Expected shelf life"]


def test_relative_links_in_the_product_docs_resolve():
    bad = []
    for f in DOCS:
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", f.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (f.parent / target).resolve().exists():
                bad.append(f"{f.relative_to(ROOT)} -> {target}")
    assert bad == [], bad


def test_the_framework_is_cited_exactly_once_and_never_quoted():
    hits = [(f.relative_to(ROOT), line) for f in DOCS for line in f.read_text(encoding="utf-8").splitlines() if "gartner" in line.lower()]
    assert len(hits) == 1 and hits[0][0] == Path("docs/product/README.md") and "informed by Gartner's data product guidance framework (2024)" in hits[0][1], hits


def test_every_canvas_has_the_same_headings_in_the_same_order():
    for dp in ("DP1", "DP2", "DP3", "DP4", "DP5"):
        heads = re.findall(r"^## (.+)$", ROOT.joinpath("products", dp, "canvas.md").read_text(encoding="utf-8"), flags=re.M)
        assert heads == HEADINGS, dp
