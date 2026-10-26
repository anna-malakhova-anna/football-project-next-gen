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
| Staged | 2026-10-26 | `stg_gmp_proxy` (82 rows, 1:1 with raw): 2 superseded double filings, 4 blank events kept as unknown, every market resolved to its country code | treatments as decided at Profiling |
| Modelled | 2026-10-26 | `mart_gmp_market_status` (proxy-only vs dark), `mart_gmp_direction` (proxy direction beside, never combined); `scripts/check_lineage.py` lists `stg_gmp_proxy` as aggregate-only | aggregate-only meaning: a separate fact used only for market status and proxy direction |

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

## Staged (2026-10-26)

`stg_gmp_proxy` types every column and resolves the market name to its country code through `gmp_markets` (all 82 rows resolve). A market-season filed by two clubs keeps the latest `report_date` (ties: the lower club id); the other row is marked `is_superseded`, not dropped. Blank events stay NULL (`events_known` false): unknown, never zero. `has_signal` is true when events are above zero, a game was played, or a national federation exists.

## Modelled (2026-10-26)

For an aggregate-only source, Modelled means a **separate use with a lineage guard**, not participants. The proxy decides only whether a market with no participation source is Proxy-only or Dark (`mart_gmp_market_status`), and it gives a proxy direction shown beside the participation direction (`mart_gmp_direction`, ADR-015). `scripts/check_lineage.py` fails the build if any participant model reads `stg_gmp_proxy`.

**Graded against the synthetic answer key** (`eval_gmp_scenario_summary`, ADR-026): the proxy direction matched the true direction in **0 of the 8** dark markets where it was known. The answer key makes the proxy only weakly related to participation (an assumption), so this shows what weak proxies would do. It is also why the proxy is never turned into players.
