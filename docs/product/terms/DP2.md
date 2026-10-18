# Terms of use: DP2 Flag Participant & Household Master

> Synthetic project; every role is fictional. Plain-language terms, not legal terms. Project policy informed by public rules, not legal advice.

## Permitted uses
- Resolving duplicates and reviewing uncertain matches.
- Building the counting facts and the household linkage inside the restricted zones.
- Answering a correction or deletion request for one record.

## Prohibited uses
- Any marketing access, direct or through a list.
- Fuzzy household linkage: only exact contact matches create a household (ADR-009).
- Using a participant id as a stable key outside the data team (it can change on a merge, ADR-004).

## Who can request access, and how
The ops audience only (data stewards, operations). A new reader needs the data product manager's approval and the privacy lead's sign-off, requested through the feedback issue template (label dp2).

## Retention
Governed by the age-out rule: a participant who was ever a minor is anonymized irreversibly after the age-out and grace period (ADR-017). Every period is an assumption and an open question for the privacy lead.

## What happens when a published number is restated
An identity change that moves a published count by more than the restatement threshold triggers a restatement (ADR-007). A merge or split is recorded with its reason in the review queue.

## How to report misuse
Open an issue with the label dp2. Do not paste identifying details; describe the record by its source and a made-up key.
