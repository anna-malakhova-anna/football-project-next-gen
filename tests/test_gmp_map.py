"""Phase 7 (ADR-032): the map's label points are what the vendored outlines give, every program market has an outline, and the outlines carry their licence."""
import json
from pathlib import Path

from scripts import build_gmp_map_points as mp

ROOT = Path(__file__).resolve().parent.parent


def test_the_seed_matches_the_outlines():
    assert mp.OUT.read_text(encoding="utf-8") == mp.render(), "run `uv run python -m scripts.build_gmp_map_points`"


def test_every_market_has_an_outline_and_a_point_on_land_scale():
    rows = mp.rows()
    assert len(rows) == 22
    ids = {g.get("id") for g in json.loads(mp.TOPO.read_text(encoding="utf-8"))["objects"]["countries"]["geometries"]}
    assert all(r["iso_numeric"] in ids for r in rows)
    assert all(-180 <= float(r["label_lon"]) <= 180 and -90 <= float(r["label_lat"]) <= 90 for r in rows)


def test_the_outlines_keep_their_licence():
    text = (ROOT / "site_src" / "geo" / "LICENSE-world-atlas.txt").read_text(encoding="utf-8")
    assert "Natural Earth" in text and "Permission to use, copy, modify" in text
