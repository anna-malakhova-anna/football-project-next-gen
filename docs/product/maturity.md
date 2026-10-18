# Maturity check: what the organization could support

An honest self-assessment in this project's own words. "Current state" is what exists in the repo; "gap" is what a real organization would need; "consequence" is how it limits the product scope.

| Area | Current state (in the repo) | Gap (a real organization would need) | Consequence for product scope |
|---|---|---|---|
| **Governance** | Share schemas per audience, an audience column policy checked in the build, ADRs for decisions | Named owners, an access request process, a review forum | Access is by audience and policy file only; there is no approval workflow, so club access stays aggregate-only |
| **Metadata** | A metric catalog, a data dictionary, contracts per source | A searchable catalog, lineage tooling, owners per column | The product label is a YAML file and a page, not a catalog entry |
| **Data quality** | A rule registry scored per purpose, fix lists, grades A to D | Real operators acting on fix lists; thresholds agreed with consumers | Grades are shown beside every number; products are released with their grade, not after reaching a grade |
| **Identity** | Probabilistic matching with a simulated steward and a review queue | A persisted id registry (ADR-004: ids can change on a merge) and real stewards | DP2 ids can change on a merge, so DP2 v1 is internal only |
| **Privacy** | Suppression, pseudonymization, a minimum data standard, age-out deletion on a copy, consent provenance | Legal review, a real consent record, a real deletion job that reaches raw data | Legal points are open questions. DP5 stays analytics-only until guardian consent for club marketing is captured |
| **Delivery** | A static site and share tables | A governed delivery channel with authentication and usage logging | No real consumer can be logged; adoption is instrumented, not observed |
| **Monitoring** | dbt tests, the contract checks, share-policy checks | Alerting, on-call, a usage feed | Product health is read at build time, not continuously |
