# Roles (RACI)

> All roles are fictional. R = does the work, A = accountable (exactly one per row), C = consulted, I = informed.

| Activity | Data product manager | Data product owner | Data steward(s) | Data engineering | Analytics | Privacy / compliance | League operations | Club partner | International growth |
|---|---|---|---|---|---|---|---|---|---|
| **Prework:** customer, value, type, owner, dependencies | **A** | R | C | C | C | C | C | C | C |
| **Plan and design:** vision, MVP, roadmap, versioning | **A** | R | C | C | C | C | C | C | C |
| **Engineer:** pipelines, metadata, governance policies | C | **A** | R | R | C | C | I | I | I |
| **Package and deliver:** label, terms, release | **A** | R | C | R | C | C | I | I | I |
| **Monitor and observe:** health and adoption | C | **A** | R | R | R | C | I | I | I |
| **Approve club access** to an aggregate share | C | R | I | I | I | **A** | I | C | I |
| **Approve a new consent purpose** | C | C | C | I | I | **A** | C | C | I |
| **Restate a published number** | C | **A** | R | R | R | I | I | I | I |
| **Retire a product** | **A** | R | C | R | C | C | I | I | I |

**Without a named data product manager, the portfolio has no owner.** Each product would have a pipeline and a steward, but nobody would decide what to build first, when to retire something, or how to trade a consumer's wish against a privacy rule. That role, deciding across products, is the one this project demonstrates.

Notes
- The **data product owner** runs one product day to day (a product's `owner_role` in `product.yml`). The **data product manager** owns the portfolio.
- **Privacy and compliance is the only accountable party** for club access and for new consent purposes: a product team cannot approve its own exception.
- A **restatement** follows the published rules in ADR-007 and the methodology CHANGELOG; this table only says who acts.
