"""Reusable defect injectors. All data is SYNTHETIC.

Defects are injected at *exact* counts, round(rate * N), chosen from the eligible
rows, so DQ results can be checked against the configured rates (spec principle 5).
"""
from __future__ import annotations

import datetime as dt
import random
import string
import unicodedata
from dataclasses import dataclass, field


@dataclass
class SourceOutput:
    """What a source generator returns; main.py writes it to disk."""
    source_system: str
    files: dict[str, list[dict]] = field(default_factory=dict)   # relative path -> rows
    truth: list[dict] = field(default_factory=list)              # record id -> true_person_id
    manifest: list[dict] = field(default_factory=list)           # record id -> defect id
    extra: dict = field(default_factory=dict)                    # source-specific payloads
    n_records: int = 0                                           # records as written, duplicates included


def pick(rng: random.Random, eligible: list[int], rate: float, total: int) -> list[int]:
    """Choose round(rate * total) indices from `eligible` (all of them if too few)."""
    k = min(round(rate * total), len(eligible))
    return rng.sample(eligible, k)


def typo(rng: random.Random, s: str) -> str:
    """One-character edit: substitute, delete, insert or transpose. Always differs from `s`."""
    for _ in range(20):
        i = rng.randrange(len(s))
        op = rng.choice(["sub", "del", "ins", "swap"])
        ch = rng.choice(string.ascii_lowercase)
        if op == "sub":
            out = s[:i] + ch + s[i + 1:]
        elif op == "del" and len(s) > 3:
            out = s[:i] + s[i + 1:]
        elif op == "ins":
            out = s[:i] + ch + s[i:]
        elif op == "swap" and i + 1 < len(s):
            out = s[:i] + s[i + 1] + s[i] + s[i + 2:]
        else:
            continue
        if out.lower() != s.lower():
            return out
    return s + "x"


def can_swap_day_month(d: dt.date) -> bool:
    return d.day <= 12 and d.day != d.month


def swap_day_month(d: dt.date) -> dt.date:
    return dt.date(d.year, d.day, d.month)


def impossible_dob(rng: random.Random, d: dt.date, season_year: int) -> dt.date:
    """Future date (half the time) or an age over 80."""
    if rng.random() < 0.5:
        return dt.date(season_year + rng.randint(1, 3), d.month, min(d.day, 28))
    return dt.date(season_year - rng.randint(81, 100), d.month, min(d.day, 28))


def email_variant(rng: random.Random, email: str) -> str:
    """Case or whitespace variant of an email address."""
    return rng.choice([
        email.upper(), email.title(), " " + email, email + " ", " " + email.upper() + " ",
    ])


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
