"""Sort keys that keep the random draws stable across a country rename. SYNTHETIC.

Phase 7 renamed Panama (PA) to Spain (ES). Wherever the generator sorts by country code or by an organization id that starts with one
("ES|<club>"), Spain sorts in Panama's former alphabetical slot, so every draw, and so the whole synthetic population and every number
built from it, stays exactly as it was. Only labels and Spain's consent jurisdiction change.
"""
from __future__ import annotations

LEGACY_SORT_CODE = {"ES": "PA"}


def country_key(code: str) -> str:
    return LEGACY_SORT_CODE.get(code, code)


def org_key(org_id: str) -> str:
    """For ids of the form '<country>|<name>'; any other id sorts as itself."""
    head, sep, rest = org_id.partition("|")
    return country_key(head) + sep + rest if sep else org_id
