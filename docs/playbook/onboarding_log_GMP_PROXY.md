# Onboarding log: GMP_PROXY (Global Markets Program proxy returns, Phase 7)

> Synthetic project. Roles are fictional. Process: [onboard-a-source.md](onboard-a-source.md) v1.3. Rules for its use: [ADR-025](../decisions/ADR-025-global-status-direction-and-scenario.md).

**Source:** club-filed returns per program market and season. **Shape:** a CSV per season, with one row per market per filing club. **No individuals and no count of people.**
**Owner (role):** International growth lead. **Partner type:** a club with Global Markets Program rights in that market. How clubs would actually file such a return is an **assumption**.

## Stage log

| Stage | Completed | Evidence | Notes |
|---|---|---|---|
| Discovery | 2026-10-25 | this log; ADR-025 section 4; `source_registry` row | key decision below |
| Profiling | 2026-10-25 | `raw.gmp_proxy` (82 rows) | issue list below |
| Contracted | 2026-10-25 | `contracts/GMP_PROXY.yml` v1.0.0; `make contracts`: 12 PASS, 2 WARN, 0 ERROR; 7 contract rules in `dq_rule_registry` | WARNs accepted below |
| Staged | (step 4) | | |
| Modelled | (step 4) | | aggregate-only meaning: a separate fact used only for market status and proxy direction |

## Discovery (2026-10-25)

- **Purpose:** tell a market with *some* sign of flag football activity (proxy-only) apart from one with none (dark), and show a proxy direction beside the participation direction. It is never a participation count.
- **Key decision recorded at Discovery, before data landed:** proxy values are **never** turned into players. They are never added to, combined with or used to estimate participation; they decide status and appear beside the participation direction (ADR-025, ADR-015).
- **Legal basis / consent (design assumption, not legal advice):** counts of club events and games, plus a yes/no on whether a national federation exists. No individual, no consent field, no minors' data.
- **Small cells:** a market with one filing club reveals that club's activity. Club ids are anonymous, and staging keeps the reporter only to deduplicate.

## Profiling (2026-10-25)

82 rows over five seasons: 16 markets file (the seven with participation data, and 9 of the 15 without), so **6 markets never appear** (dark, including Italy). Issue list (profile counters, not truth):

| Issue | Rows | Share | Treatment decided |
|---|---|---|---|
| Same market-season filed by two clubs | 2 | 2.4% | dedupe at Staged: keep the latest `report_date`; flag |
| `club_events` blank | 4 | 4.9% | keep the row; events unknown for that market-season (games and federation still count as signals); flag |
| Market name outside the 22 | 0 | 0% | none needed |
| `games_in_market` = 1 | 24 | 29% | none: a signal, not a defect |

## Contracted (2026-10-25)

Contract v1.0.0: no consent fields and no person identifier; the market name must be one of the 22 program markets. Two rules breach their WARN thresholds, matching the profile: blank events (4.88% > 2%) and duplicate market-seasons (2.44% > 1%). The thresholds describe a healthy club return, not this file, so the WARNs are real. They are **accepted** with the treatments above.
