# ADR-028: DP6's exec outputs are split by the legal regime assumed to apply

- **Status:** Accepted for step 6 of the Phase 7 spec, 2026-10-26. Applies Anna's decision D10: one DP6, with outputs split by privacy regime rather than three products.
- **Synthetic data.** Every regime is an **unverified assumption** (`legal_regime`, ADR-024), named for design only and never as a legal finding.

## Decision
1. **Eight exec ports**, one per regime and kind, replacing the three combined share models of steps 4 and 5:

   | Regime port | Markets | Market view | Quality trend | Planning scenario |
   |---|---|---|---|---|
   | `global_eu_uk` | 9: AT, CH, DE, ES, FR, GB, GR, IE, IT | `share_exec__gmp_markets_eu_uk` | `share_exec__gmp_quality_trend_eu_uk` | `share_exec__gmp_scenario_eu_uk` |
   | `global_canada` | 1: CA | `share_exec__gmp_markets_canada` | `share_exec__gmp_quality_trend_canada` | none: Canada has participation data |
   | `global_other` | 12 | `share_exec__gmp_markets_other` | `share_exec__gmp_quality_trend_other` | `share_exec__gmp_scenario_other` |

2. **One macro per kind** (`dbt/macros/gmp_shares.sql`) writes every regime's model, so the ports cannot drift apart. Each model is two lines that call it.
3. **Each row carries its regime** (`regime_name`, and `regime_verification`, `UNVERIFIED` until the privacy lead checks it). Each port in `products/DP6/product.yml` carries a `regime_note`: the questions for the privacy lead that apply to that regime. Examples are the age of digital consent per EU country, Quebec's Law 25, and which markets can send only aggregate returns.
4. **Each port has its own rows in `audience_column_policy.csv`**. Today they allow the same columns, but each regime can now be tightened on its own without touching the others.
5. **`gmp_regime_ports_partition_the_markets`**, a dbt test, checks that every one of the 22 markets is in exactly one market port, every market without data is in exactly one scenario port, and no row sits in another regime's port.
6. The partner report card (ADR-027) stays one port. Each card already belongs to one federation.

## Consequences
- DP6 moves to version 0.2.0. The site tab (step 9) will read the three market ports and show them as one map, without recomputing anything.
- The split is a design for the access rules the privacy lead may set. Until then, it changes who could be given what, not what anyone sees.
