"""Derive the Global outlook map's label point and continent view for each program market from the vendored country outlines (ADR-032).

  uv run python -m scripts.build_gmp_map_points            writes dbt/seeds/gmp_map_points.csv
  uv run python -m scripts.build_gmp_map_points --check    fails if the seed is not what the outlines and gmp_markets give

The outlines are site_src/geo/countries-50m.json (world-atlas 2.0.2, from Natural Earth, public domain; see site_src/geo/LICENSE-world-atlas.txt).
A market is matched to its outline by name. Its label point is the centroid of its largest polygon (planar, in longitude and latitude), so a
country's islands or overseas parts do not pull the label off its mainland. Nothing here is typed per country.
"""
from __future__ import annotations

import csv
import io
import json
import sys

from scripts.common import ROOT

TOPO = ROOT / "site_src" / "geo" / "countries-50m.json"
MARKETS = ROOT / "dbt" / "seeds" / "gmp_markets.csv"
OUT = ROOT / "dbt" / "seeds" / "gmp_map_points.csv"
CONTINENT = {"Europe": "Europe", "North America": "Americas", "Latin America": "Americas", "Asia-Pacific": "Asia-Pacific", "Middle East and Africa": "Middle East and Africa"}


def _arcs(topo: dict) -> list[list[tuple[float, float]]]:
    """Decode the quantized, delta-encoded arcs into longitude/latitude points."""
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    out = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            pts.append((x * sx + tx, y * sy + ty))
        out.append(pts)
    return out


def _ring(indices: list[int], arcs: list) -> list[tuple[float, float]]:
    pts: list = []
    for i in indices:
        a = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        pts.extend(a if not pts else a[1:])
    return pts


def _area_centroid(ring: list) -> tuple[float, float, float]:
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    a /= 2
    return abs(a), cx / (6 * a), cy / (6 * a)


def rows() -> list[dict]:
    topo = json.loads(TOPO.read_text(encoding="utf-8"))
    arcs = _arcs(topo)
    by_name = {g["properties"]["name"]: g for g in topo["objects"]["countries"]["geometries"]}
    out = []
    with open(MARKETS, newline="", encoding="utf-8") as fh:
        for m in csv.DictReader(fh):
            g = by_name.get(m["country_name"])
            if g is None:
                raise SystemExit(f"{m['country_name']}: no outline with that name in {TOPO.name}")
            polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
            best = max((_area_centroid(_ring(p[0], arcs)) for p in polys), key=lambda t: t[0])     # outer ring of each polygon; keep the largest
            out.append({"country_code": m["country_code"], "iso_numeric": g["id"], "continent": CONTINENT[m["region"]],
                        "label_lon": f"{best[1]:.2f}", "label_lat": f"{best[2]:.2f}"})
    return sorted(out, key=lambda r: r["country_code"])


def render() -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["country_code", "iso_numeric", "continent", "label_lon", "label_lat"], lineterminator="\n")
    w.writeheader()
    w.writerows(rows())
    return buf.getvalue()


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("gmp_map_points.csv is out of date: run `uv run python -m scripts.build_gmp_map_points`")
            return 1
        print("gmp_map_points.csv matches the outlines")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {text.count(chr(10)) - 1} markets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
