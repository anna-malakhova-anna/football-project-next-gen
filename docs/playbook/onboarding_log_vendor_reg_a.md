# Onboarding log: vendor_reg_a

> Synthetic project; **the shape of this feed is an assumption** made for the demonstration, not a description of any real system. Roles are fictional. Process: [onboard-a-source.md](onboard-a-source.md).
> Phase 5 (ADR-013) onboarded the channel feeds built in the first Phase 5 build to **Contracted**. They are scored by the rule registry as sources but are **not counted**: they describe the same children as `US_LEAGUE`, so adding them would double count.

**Source:** third-party registration platform (ASSUMED shape). **Shape:** CSV; one file per season (data/raw/p5/vendor_reg_a/vendor_reg_a_<year>.csv). **Grain:** one row per registration.
**Owner (role):** Program Partnerships (third-party platform). **Raw table:** `raw.p5_vendor_reg_a` (3,652 rows loaded).

## Stage log

| Stage | Completed | Evidence | Notes |
|---|---|---|---|
| Discovery | 2026-10-13 | the first Phase 5 build (`generator/phase5/feeds.py`); inventory entry in `docs/source_inventory.md` | shape assumed |
| Profiling | 2026-10-13 | the feed's defects are injected and recorded in the Phase 5 defect manifest (answer key, evaluation only) | issue list below |
| Contracted | 2026-10-14 | `contracts/vendor_reg_a.yml` v1.0.0; `make contracts`: 14 PASS, 0 WARN, 0 ERROR; `source_registry` = Contracted | thresholds were set as the program's expectation, then measured |
| Staged | not reached | | held at Contracted until the program decides whether a channel feed joins the counts (ADR-013, question 2) |

## Discovery
- **Purpose:** an additional intake channel into the same domestic network. Registered children here are mostly also in `US_LEAGUE`; that is why the feed is scored but not counted.
- **Minors present:** yes.
- **Consent fields:** `tos_accepted_text`, `marketing_checkbox`.
- **Person identifier:** no person id; the league is a free-text name, not an id.
- **Legal basis (design assumption, not legal advice):** parental consent for minors at registration; a marketing contact needs its own explicit opt-in, and a consent email or a waiver is never that opt-in (purpose limitation, ADR-019). Where the law matters, it is an open question for the privacy lead.

## Contract result (`make contracts`)
- None: every rule passes.

## Open
- Whether the feed should be staged and counted: no (kept out of the counts until Anna decides; `docs/questions-for-stakeholders.md`).
- The feed's real-world shape is unknown; every rate in the contract is a placeholder expectation.
