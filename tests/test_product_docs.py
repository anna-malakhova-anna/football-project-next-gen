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


def test_the_framework_name_appears_nowhere_else_in_the_repo_docs_or_the_site():
    """Only the single citation line in docs/product/README.md may name the framework (handover section 0.1)."""
    scan = [*DOCS, *ROOT.joinpath("docs", "decisions").glob("ADR-02*.md"), ROOT / "README.md", *ROOT.joinpath("site_src").rglob("*.yml"), *ROOT.joinpath("scripts").glob("site_product.py"), *ROOT.joinpath("site").glob("*.html")]
    hits = [f.relative_to(ROOT) for f in scan if f.exists() and "gartner" in f.read_text(encoding="utf-8").lower() and f.relative_to(ROOT) != Path("docs/product/README.md")]
    assert hits == [], hits


def test_no_sentence_of_the_product_docs_or_the_page_is_copied_from_a_local_private_copy_of_the_framework():
    """Runs only if the program owner places an UNCOMMITTED copy of the framework text at ~/.private/gartner.txt; skipped otherwise."""
    private = Path.home() / ".private" / "gartner.txt"
    if not private.exists():
        import pytest
        pytest.skip("no local copy of the framework at ~/.private/gartner.txt")
    ref = re.sub(r"\s+", " ", private.read_text(encoding="utf-8", errors="ignore").lower())
    page = ROOT / "site" / "product.html"
    texts = [f.read_text(encoding="utf-8") for f in DOCS] + ([re.sub(r"<[^>]+>", " ", page.read_text(encoding="utf-8"))] if page.exists() else [])
    for t in texts:
        for sent in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", t)):
            if len(sent.split()) >= 8:
                assert sent.strip().lower() not in ref, sent
