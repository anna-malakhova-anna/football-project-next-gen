{{ config(tags=['phase5']) }}
-- PRIVACY share: what analytics survive the age-out deletion in the identity and linkage zones (ADR-017): each figure at baseline, rebuilt from anonymized facts, and after re-running identity on the
-- anonymized inputs, with whether it moved by no more than the tolerance. Counts and rates only. Empty until `make retention-vs-deletion` has run.
select metric, label as metric_label, baseline, facts_only, identity_rebuilt, facts_only_change, identity_rebuilt_change, survives_facts_only, survives_identity_rebuilt, tolerance
from {{ ref('mart_retention_vs_deletion') }}
order by metric
