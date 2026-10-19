"""The copy review lists every chart once in the demo-path or the other-charts section, every page intro and every roadmap row, and the demo-path charts come first."""
import csv
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_copy_review_covers_every_card_page_and_roadmap_row():
    if not (ROOT / "public" / "quality.html").exists():
        pytest.skip("no built site")
    from scripts import build_copy_review as cr
    assert cr.main() == 0
    text = (ROOT / "docs" / "product" / "copy-review.md").read_text(encoding="utf-8")
    charts = yaml.safe_load((ROOT / "site_src" / "copy" / "charts.yml").read_text(encoding="utf-8"))["charts"]
    for cid in charts:
        assert len(re.findall(rf"^### {cid}: ", text, flags=re.M)) == 1, f"{cid} must have exactly one section"
    first_other = text.index("## 2. Other charts")
    demo = [c for ids in cr.DEMO.values() for c in ids]
    assert all(text.index(f"### {c}: ") < first_other for c in demo), "demo-path charts come first"
    assert not any(text.index(f"### {c}: ") < first_other for c in charts if c not in demo)
    for slug in ("quality", "sure", "markets", "privacy", "product"):
        assert f"pages.{slug}.intro_template" in text
    for r in csv.DictReader((ROOT / "dbt/seeds/product_roadmap.csv").open(encoding="utf-8")):
        assert r["title"].replace("|", "/") in text
    for slot in ("headline_template", "question", "means_club", "means_privacy", "action_club", "action_privacy", "caution"):
        assert text.count(f"`{slot}`") == len(charts)
