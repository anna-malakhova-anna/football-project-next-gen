"""Generate docs/access_policy.md from dbt/seeds/audience_column_policy.csv (the policy the share check enforces), so the
audience x data matrix cannot drift from what is actually allowed.  (make docs)
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "dbt" / "seeds" / "audience_column_policy.csv"
OUT = ROOT / "docs" / "access_policy.md"

AUDIENCES = [  # audience, purpose, grain, identifiers, rows
    ("exec", "Program reporting", "Aggregates only", "None", "All, with small-cell suppression (primary and secondary)"),
    ("analyst", "Analysis and modelling", "Participant-year", "Pseudonymous key only; no names or contact info; birth year, not DOB; postal prefix only", "All"),
    ("ops", "Running leagues, resolving data issues", "Registration, participant, review queue", "Full identifiers", "All, plus the review queue"),
    ("marketing", "Outreach", "Contact list (one row per email)", "Contact email; first name only for a sole adult player", "Only addresses where EVERY participant sharing it has marketing consent TRUE (NULL is not consent); never a minor's own details; clusters with an open integrity issue excluded"),
    ("media", "Photo and video clearance", "Roster", "Name, organization, season", "Only participants whose most recent captured photo consent is TRUE; the list means cleared, anyone absent is NOT cleared, including NULL; clusters with an open integrity issue excluded"),
]
ENFORCED = [
    ("Only listed columns exist in a share", "`scripts/check_share_policy.py` compares `information_schema.columns` with this policy and fails on any column not explicitly allowed"),
    ("No `select *` in a share model", "the same check greps the compiled and source SQL under `models/shares/`"),
    ("No direct identifier in exec or analyst", "every share column carries a `meta: pii` tag; the check fails on `direct` in `share_exec` or `share_analyst`"),
    ("Aggregates obey small-cell rules", "`share_exec_obeys_suppression_rules` (independent of the suppression macro), `share_exec_derived_rates_follow_their_counts`"),
    ("Only consented contacts are shared", "`share_marketing_only_consented_contacts` re-derives eligibility from `dim_participant`"),
    ("Only cleared participants are on the roster", "`share_media_only_cleared_participants` re-derives the roster from `dim_participant` and the facts"),
    ("The analyst share has no direct identifiers, names or DOB", "`share_analyst_has_no_direct_identifiers`; `share_analyst_k_anonymity_warning` warns about re-identification risk"),
]


def _cell(s: str) -> str:
    return s.replace("|", "\\|").strip()


def render(path: Path = POLICY) -> str:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    models: dict[tuple, list] = defaultdict(list)
    denied: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["allowed"] == "Y":
            models[(r["audience"], r["model"])].append(r)
        else:
            denied[r["audience"]].append(r)
    out = [
        "# Access policy",
        "",
        "> **Generated** from `dbt/seeds/audience_column_policy.csv` by `scripts/build_access_policy.py` (`make docs`). Edit the CSV and",
        "> the rationale below in the script, not this file. All data in this project is synthetic.",
        "",
        "**These are project policies informed by regimes such as COPPA, CASL and GDPR. They are not legal interpretations**, and no",
        "legal review has taken place. DuckDB has no per-user grants, so each audience gets its own schema (`share_<audience>`) and the",
        "controls below are enforced by tests and a policy check. ADR-006 maps them to Snowflake roles, masking policies and row access",
        "policies (design only; not implemented).",
        "",
        "## Principles",
        "",
        "- **Least privilege by default.** Each audience receives only the columns and rows it needs, listed explicitly.",
        "- **NULL consent is not consent.** A consent that was not captured is never treated as given: not for a contact list, not for a",
        "  clearance roster. A conflict among people who share an address excludes the address.",
        "- **A minor's own details are never shared with marketing.** For a minor the contact is the guardian.",
        "- **Small numbers are not published.** Counts below the threshold are suppressed, with a second cell hidden where a published",
        "  subtotal would otherwise reveal the first.",
        "- **Tests check what is absent**, not only what is present.",
        "",
        "## Audience by data",
        "",
        "| Audience | Schema | Purpose | Grain | Identifiers | Rows |",
        "|---|---|---|---|---|---|",
    ]
    out += [f"| **{a}** | `share_{a}` | {p} | {g} | {i} | {r} |" for a, p, g, i, r in AUDIENCES]
    out += ["", "## What each share contains", ""]
    for aud, *_ in AUDIENCES:
        out += [f"### {aud}", ""]
        for (a, model), cols in sorted(models.items()):
            if a != aud:
                continue
            out += [f"**`{model}`**", "", "| Column | Treatment |", "|---|---|"]
            out += [f"| `{c['column']}` | {_cell(c['treatment'])} |" for c in cols]
            out.append("")
        if denied[aud]:
            out += ["Explicitly **not** available:", "", "| Column | Why |", "|---|---|"]
            out += [f"| `{d['column']}` | {_cell(d['treatment'])} |" for d in denied[aud]]
            out.append("")
    out += ["## How the policy is enforced", "", "| Rule | Enforced by |", "|---|---|"]
    out += [f"| {r} | {e} |" for r, e in ENFORCED]
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
