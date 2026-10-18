# DP1: League Registration Intake: product canvas

> Synthetic project. All roles are fictional. The headings are the same for every product.

## Customer
Data engineering and stewards (internal) and league operators, who are suppliers and receive the standard and the fix list.

## Problem
Registration data arrives in different shapes, late, and with gaps. Nothing downstream can be trusted until the intake is predictable.

## Value proposition
**Utility (keeps things running).**

## Consumption type
Internal, plus a partner-facing standard that league operators and federations are asked to follow.

## Product type
Source-based.

## Owner role and supporting roles
Data Product Manager, NFL FLAG Insights (fictional). Supporting: data steward, data engineering, league operations.

## Key dependencies
League registration sources and their contracts (`contracts/*.yml`), the onboarding playbook, the minimum data standard (ADR-018), the rule registry (ADR-014).

## What we will NOT do
No person-level data leaves intake. No source is counted before it has a contract and an onboarding log. No field is added to the standard without a named use.

## Expected shelf life
Long-term; the standard is reviewed each season.
