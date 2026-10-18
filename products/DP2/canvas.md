# DP2: Flag Participant & Household Master: product canvas

> Synthetic project. All roles are fictional. The headings are the same for every product.

## Customer
Operations and data stewards. Never marketing directly.

## Problem
The same child appears in several leagues and under several spellings, and a family is not one record. Counting, retention and fan linkage all need one reliable person and household.

## Value proposition
**Enabler (makes other things possible).**

## Consumption type
Internal and restricted.

## Product type
Master.

## Owner role and supporting roles
Data Product Manager, NFL FLAG Insights (fictional). Supporting: data steward (review queue), data engineering, privacy and compliance.

## Key dependencies
DP1 (clean registrations), the identity resolution method (ADR-003), the participant id rule (ADR-004), the review queue and steward decisions.

## What we will NOT do
No marketing access. No exposure of names, birth dates or contact details outside the restricted zone. No fuzzy household linkage: only exact contact matches (ADR-009). No promise that an id is stable across a merge (ADR-004).

## Expected shelf life
Long-term; the rules are reviewed when the matching accuracy changes.
