"""The build's checks on datasets, chart specs and the built pages (what may be read, what a chart may do, no logos or league names).

Split out of scripts/build_site.py without changing a line; tests/test_build_site.py exercises them.
"""
from __future__ import annotations

from pathlib import Path

from scripts import site_p5_data as P5
from scripts.site_data import APPROVED_AGGREGATES, EVAL_WHITELIST, GOVERNANCE_WHITELIST
from scripts.site_render import FAVICON


FORBIDDEN_TRANSFORMS = {"calculate", "aggregate", "joinaggregate", "window", "bin", "fold", "pivot", "regression", "loess", "density", "timeUnit", "stack"}

def check_dataset(ds: dict) -> list[str]:
    problems = []
    for rel in ds["relations"]:
        ok = (rel.startswith(P5.SHARE_PREFIXES) or rel in APPROVED_AGGREGATES or rel in EVAL_WHITELIST or rel in GOVERNANCE_WHITELIST)
        if not ok:
            problems.append(f"dataset {ds['name']} reads {rel}: not share_exec, an approved aggregate, a whitelisted evaluation summary or governance metadata")
    sql = ds["sql"].lower()
    import re
    for found in set(re.findall(r"\b(?:from|join)\s+([a-z_]+\.[a-z_0-9]+)", sql)):
        if found not in {r.lower() for r in ds["relations"]}:
            problems.append(f"dataset {ds['name']}: SQL reads {found}, which is not declared in its relations")
    return problems


def check_spec(spec: dict, known: set[str], chart: str) -> list[str]:
    """A chart spec may only map fields to marks, from a registered dataset file. Walks the whole spec, layers included."""
    problems: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            if "data" in node and isinstance(node["data"], dict):
                url = node["data"].get("url")
                if url is None and "values" not in node["data"]:
                    problems.append(f"{chart}: a data block has no url")
                elif url is not None and url not in known:
                    problems.append(f"{chart}: data url {url} is not a registered dataset file")
                if "values" in node["data"]:
                    problems.append(f"{chart}: inline data values are not allowed (every number comes from a registered dataset)")
            for t in node.get("transform", []) or []:
                bad = FORBIDDEN_TRANSFORMS & set(t)
                if bad:
                    problems.append(f"{chart}: transform {sorted(bad)} computes numbers in the browser")
            for enc in (node.get("encoding") or {}).values():
                if isinstance(enc, dict):
                    bad = FORBIDDEN_TRANSFORMS & set(enc)
                    if bad:
                        problems.append(f"{chart}: encoding uses {sorted(bad)}, which computes numbers in the browser")
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(spec)
    return problems


def check_brand_boundary(out: Path, local_logo: bool = False) -> list[str]:
    """The site must not carry anyone else's mark. Text is easy to review; images are not, so refuse them outright:
    no image files, no <img>/<image>/url(...) references, and every inline SVG must be the project's own mark, the drive chart, the Data product dependency diagram (text and boxes only, drawn here) or a decorative icon.
    The one exception is the git-ignored local logo (local_logo=True, a local build only): exactly img/logo.webp, shown only as the wordmark image."""
    import re
    problems = []
    for f in sorted(out.rglob("*")):
        if local_logo and f == out / "img" / "logo.webp":
            continue
        if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".ico", ".bmp", ".tif", ".tiff", ".heic"}:
            problems.append(f"{f.relative_to(out)}: image files are not allowed on this site (no third-party logos); the project mark is inline SVG")
    if (out / "img").exists() and not local_logo:
        problems.append("site/img exists: the site carries no image directory")
    fav = out / "favicon.svg"
    if not fav.exists() or fav.read_text(encoding="utf-8") != FAVICON:
        problems.append("favicon.svg is missing or is not the project's own mark")
    for f in sorted(out.glob("*.html")):
        text = f.read_text(encoding="utf-8")
        if local_logo:
            text = text.replace('<img class="wordmark-logo" src="img/logo.webp" alt="" width="36" height="36">', "", 1)
        if re.search(r"<img\b|<image\b|<picture\b|<object\b|<embed\b", text, re.I):
            problems.append(f"{f.name}: contains an image element")
        for m in re.finditer(r"<svg\b([^>]*)>", text):
            if 'aria-hidden="true"' not in m.group(1) and 'data-mark="project"' not in m.group(1) and 'class="drive"' not in m.group(1) and not re.search(r"data-diagram=.{0,2}dependencies", m.group(1)):
                problems.append(f"{f.name}: an inline SVG is neither the project mark, the drive chart nor a decorative icon")
        if re.search(r"\b(?:rel=\"(?:icon|apple-touch-icon|shortcut icon)\"[^>]*href=\"(?!favicon\.svg)|og:image)", text, re.I):
            problems.append(f"{f.name}: an icon or social image other than favicon.svg")
    for f in sorted(out.glob("css/*.css")):
        if re.search(r"url\(\s*['\"]?(?!https://fonts\.)", f.read_text(encoding="utf-8")):
            problems.append(f"{f.name}: references an external or local image with url()")
    return problems
