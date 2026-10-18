# Data product portfolio (Phase 6)

> **Synthetic data.** Every number in this project describes a generated population. There are no real users, consumers or targets: personas are assumptions, targets are placeholders that Anna sets, and usage is instrumented but not observed.

This folder shows how a data product manager would take three stated business goals and turn them into a governed portfolio of data products, using the Phase 1 to 5.1 build as the evidence. The matching site page is the **Data product** tab (`site/product.html`).

**Product, not project.** A project ends at delivery. A product has an owner, users, versions, health measures and a retirement plan. Everything here is written to that standard.

## The three goals (as stated)
| ID | Goal |
|---|---|
| **G1** | Grow NFL presence globally through flag football |
| **G2** | Grow flag football popularity in the US as a safe, accessible way into the sport, alongside tackle football |
| **G3** | Track conversion of flag participants (and their families) to NFL fans, while protecting children: no direct marketing to kids, age-specific consent rules, and guardian consent |

## The five products
| ID | Product | Type | Serves |
|---|---|---|---|
| DP1 | League Registration Intake | source-based | G1, G2 (foundation) |
| DP2 | Flag Participant & Household Master | master | all (foundation) |
| DP3 | Global Participation Insights | insights | G1 |
| DP4 | US Flag Growth & Club Market Insights | insights | G2 |
| DP5 | Flag-to-Fan Conversion Insights | insights (restricted) | G3 |

```
DP1 Intake ──► DP2 Master ──► DP3 Global
                     ├──────► DP4 US / clubs
                     └──────► DP5 Conversion
```

## The method, in this project's words
Five stages. Each is implemented by artifacts already in the repo or added in Phase 6.

1. **Prework.** Before building: who is the customer, what is the value, who consumes it and how, what type of product is it, who owns it, what does it depend on. Artifacts: `discovery.md`, the canvases in `products/DPn/canvas.md`, `roles.md`.
2. **Plan and design.** A vision, a minimum viable product and a now/next/later roadmap; a reference design of how products feed each other; a versioning rule; an honest check of what the organization can support. Artifacts: `roadmap.md`, `maturity.md`, the prioritization seed.
3. **Engineer and operationalize.** Pipelines, metadata and the governance policies (definitions, ethics, lifecycle, quality, security, privacy). Artifacts: dbt models and tests, contracts, `governance-coverage.md`.
4. **Package and deliver.** One consistent label per product (name, version, quality indicator, type, owner, consumers, terms, coverage, support), a delivery channel, release management and a retirement plan. Artifacts: `products/DPn/product.yml`, `terms/`, `products/CHANGELOG.md`.
5. **Monitor and observe.** Two separate views: inside (is the product healthy: quality, freshness, contracts, pipeline, trust, privacy, cost) and outside (is anyone using it, and is it moving the goal). Artifacts: `mart_product_health`, `mart_goal_scorecard`, `feedback-loop.md`.

## Where each product is formed
A data product is not a layer. It is a governed **output port** (an owner, a contract, a version) on top of internal models. Each product forms at the point where its data first becomes fit and safe for a named reader. `raw` is never a product: it is unchanged, unchecked and full of children's personal data. In the medallion picture, DP1 and DP2 are source-aligned (silver) and DP3 to DP5 are consumer-aligned (gold). The `share_*` schemas are the ports.

| Product | Formed where (the gate) | Kept inside (not for others to read) | What others may read |
|---|---|---|---|
| DP1 League Registration Intake | At `raw`: each file is checked against its contract and the data standard | Staging, the DQ rules and their results | **Restricted:** the checked registrations, for DP2 only. **Aggregate:** quality scorecards, fix lists and contract status |
| DP2 Participant and Household Master | On DP1's restricted port | Matching, clustering, the review queue | `share_ops`; the participant, household and consent tables as restricted ports for DP3 to DP5 only |
| DP3 Global Participation | On DP2's ports | Facts and measurement tables | `share_exec` |
| DP4 US Growth and Club Markets | On DP2's ports and DP1's aggregate port | Market models | `share_club` (and `share_exec`) |
| DP5 Flag-to-Fan Conversion | On DP2's ports and the fan feed | The `linkage` schema (restricted) | Aggregates only, in `share_exec`, `share_club` and `share_privacy` |

`scripts/check_product_boundaries.py` enforces it (part of `make product`): every model has one owner, a model reads another product only through a declared port, and no port reads `raw` directly. Cross-product reads that exist today are listed with a reason in `products/boundary_debt.csv`; a new one fails the check, and a row that stops applying must be removed.

## Reference
Structure informed by Gartner's data product guidance framework (2024).

## Where things are
| Topic | File |
|---|---|
| Personas and the questions we would validate | `discovery.md` |
| Who decides what | `roles.md` |
| Canvas for each product | `../../products/DP1` to `DP5/canvas.md` |
| Portfolio decision and the existing v1 pages | `../decisions/ADR-021-data-product-portfolio.md` |
