"""Generate docs/product/age-consent-rules.md from dbt/seeds/age_consent_rules.csv (Phase 6, ADR-022), so the documented rules cannot drift from the seed the models read.  (make docs)

Every row is project policy informed by public rules, not legal advice. Rows with verified = N are listed as open items for the program owner.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "dbt" / "seeds" / "age_consent_rules.csv"
OUT = ROOT / "docs" / "product" / "age-consent-rules.md"


def rows() -> list[dict]:
    with open(SEED, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def render() -> str:
    rs = rows()
    open_items = [r for r in rs if r["verified"] != "Y"]
    out = ["# Age-tier consent rules (generated)", "",
           "> Generated from `dbt/seeds/age_consent_rules.csv` by `scripts/build_age_rules_doc.py` (`make docs`). **Project policy informed by public rules, not legal advice.** "
           "Where a rule is unknown or unverified, the strictest row applies: guardian-only for every minor (ADR-022). Synthetic project.", "",
           f"**{len(rs)} rows; {len(open_items)} not yet verified.** Whether a club is a \"third party\" is an open question for counsel and is not decided by any row.", "",
           "| Jurisdiction | Ages | Who consents | Allowed purposes | Prohibited purposes | Verified | Stricter than the law by choice | Basis (paraphrase) |", "|---|---|---|---|---|---|---|---|"]
    for r in rs:
        out.append(f"| {r['jurisdiction']} | {r['age_min']} to {r['age_max']} | {r['who_consents']} | {r['allowed_purposes'].replace('|', ', ')} | {r['prohibited_purposes'].replace('|', ', ') or 'none'} | {r['verified']} | {r['project_policy']} | {r['basis_note']} |")
    out += ["", "## Open items: rows still to verify", ""]
    if open_items:
        by: dict[str, list[str]] = {}
        for r in open_items:
            by.setdefault(r["jurisdiction"], []).append(f"{r['age_min']} to {r['age_max']}")
        out += [f"- **{j}**: ages {', '.join(b)}. Source URL: {'missing' if any(not r['source_url'] for r in open_items if r['jurisdiction'] == j) else 'present'}." for j, b in by.items()]
    else:
        out.append("None.")
    return "\n".join(out) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
