"""Table layout as data (Phase 6 addendum to 5.1, table rules).

Every table gets explicit column sizing in its HTML: a <colgroup> and a class on each header and cell.
  c-short  version, id, status, grade, year, counts: nowrap, width 1%, sized to the content
  c-name   names: wrapped on words only, with a minimum width (~12rem; narrower when a table has three or more)
  c-link   ADR references: each is a non-breaking chip; several stack
  c-flex   exactly ONE column per table: takes the remaining width; only here may a long code token break
Each cell also carries data-label (its column header) and the table data-stack, so below 700px a row becomes a stacked card (label: value) instead of squeezed columns.
`enhance(html)` is idempotent and works on our own generated HTML (no nested tables).
"""
from __future__ import annotations

import re

TABLE = re.compile(r"<table\b([^>]*)>(.*?)</table>", re.S)
ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S)
CELL = re.compile(r"<(t[hd])\b([^>]*)>(.*?)</\1>", re.S)
TAGS = re.compile(r"<[^>]+>")
ADR = re.compile(r"\bADR-\d{3}\b")


def _text(cell_html: str) -> str:
    return re.sub(r"\s+", " ", TAGS.sub(" ", re.sub(r"<details\b.*?</details>", "", cell_html, flags=re.S))).strip()


def _classes(cols: list[list[str]], heads: list[str]) -> list[str]:
    n = len(cols)
    avg = [sum(len(t) for t in c) / max(len(c), 1) for c in cols]
    kind = []
    for i, c in enumerate(cols):
        words = max((len(t.split()) for t in c), default=0)
        longest = max((len(t) for t in c), default=0)
        if c and all(ADR.search(t) for t in c if t):
            kind.append("c-link")
        elif longest <= 16 and words <= 2:
            kind.append("c-short")
        else:
            kind.append("c-name")
    flex = max(range(n), key=lambda i: (avg[i], i))
    kind[flex] = "c-flex"
    if kind.count("c-name") >= 3:
        kind = [("c-name c-narrow" if k == "c-name" else k) for k in kind]
    return kind


def enhance_table(attrs: str, inner: str) -> str:
    if "<colgroup" in inner:
        return f"<table{attrs}>{inner}</table>"
    rows = ROW.findall(inner)
    if not rows:
        return f"<table{attrs}>{inner}</table>"
    parsed = [CELL.findall(r) for r in rows]
    has_head = "<thead" in inner
    heads = [_text(c[2]) for c in parsed[0]] if has_head else []
    body = parsed[1:] if has_head else parsed
    ncols = max(len(r) for r in parsed)
    if ncols < 2 or any(len(r) != ncols for r in parsed):
        return f"<table{attrs}>{inner}</table>"      # ragged or single-column: leave alone
    cols = [[_text(r[i][2]) for r in body] for i in range(ncols)]
    kinds = _classes(cols, heads)
    colgroup = "<colgroup>" + "".join(f"<col class='{k.split()[0]}'>" for k in kinds) + "</colgroup>"

    def rebuild_row(rowhtml: str, is_head: bool) -> str:
        i = {"v": 0}

        def sub(m):
            tag, at, content = m.group(1), m.group(2), m.group(3)
            k = kinds[i["v"]]
            label = heads[i["v"]] if heads else ""
            i["v"] += 1
            if tag == "td":
                content = _chips(content) if k == "c-link" else content
            extra = f" class='{k}'" + (f" data-label=\"{label}\"" if (label and tag == "td") else "")
            at = re.sub(r"\s*class=(['\"]).*?\1", "", at)
            return f"<{tag}{at}{extra}>{content}</{tag}>"
        return CELL.sub(sub, rowhtml)

    new_inner = ROW.sub(lambda m: m.group(0).replace(m.group(1), rebuild_row(m.group(1), False)), inner)
    stack = " data-stack" if has_head and "data-stack" not in attrs else ""
    if ncols >= 7:   # a wide table cannot give every column its minimum: columns shrink to their longest word (words are never broken)
        attrs = attrs + " data-wide"
    return f"<table{attrs}{stack}>{colgroup}{new_inner}</table>"


def _chips(content: str) -> str:
    """ADR references become non-breaking chips (a link when the cell already holds one)."""
    if "class='adr'" in content or "class=\"adr\"" in content:
        return content
    if "<a " in content:
        return re.sub(r"(<a\b[^>]*>)(.*?)(</a>)", lambda m: m.group(1).replace("<a ", '<a class="adr" ', 1) + m.group(2) + m.group(3), content)
    return "".join(f"<span class='adr'>{a}</span> " for a in ADR.findall(content)).strip() or content


def enhance(html: str) -> str:
    """Tables outside <script> blocks (viewer slides are enhanced before they are written as JSON)."""
    parts = re.split(r"(<script\b.*?</script>)", html, flags=re.S)
    return "".join(p if p.startswith("<script") else TABLE.sub(lambda m: enhance_table(m.group(1), m.group(2)), p) for p in parts)
