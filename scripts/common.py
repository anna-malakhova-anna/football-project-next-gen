"""Shared paths and small helpers for the scripts.

Every script used to work out the repository root and the warehouse path on its own (about 40 copies of the same two lines).
They now import them from here. The warehouse path comes from `paths.warehouse` in config/generation.yaml, the same key the
generator and loaders use, so moving the warehouse is one config change.

Scripts keep a module-level `DB` name (`from scripts.common import DB`) so a test can still monkeypatch `module.DB`.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "generation.yaml"


def _warehouse_path() -> Path:
    try:
        rel = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["paths"]["warehouse"]
    except (OSError, KeyError, TypeError):
        rel = "warehouse/flag.duckdb"
    return ROOT / rel


DB = _warehouse_path()


def connect(db: Path | str | None = None, read_only: bool = True):
    """Open the warehouse (read-only by default)."""
    import duckdb

    return duckdb.connect(str(db or DB), read_only=read_only)


def _default_cell(v) -> str:
    return "-" if v is None else str(v)


def print_table(rows: Iterable[Sequence], cols: Sequence[str], cell: Callable[[object], str] = _default_cell) -> None:
    """Print rows as a left-aligned plain-text table, two-space indented. `cell` formats one value (None handling included)."""
    cells = [[cell(v) for v in r] for r in rows]
    widths = [max(len(c), *(len(r[i]) for r in cells)) if cells else len(c) for i, c in enumerate(cols)]
    print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in cells:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(r, widths)))
