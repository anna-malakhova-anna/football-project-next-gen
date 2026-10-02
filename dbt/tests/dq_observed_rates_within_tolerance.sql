-- The pipeline must detect what the generator injected: every detectable defect's observed rate is within
-- +/-50% (relative) of its configured rate (exact for structural counts, zero for never-injected flags).
-- Also fails on any flag the pipeline raises that the config catalog does not know about.
select source_system, defect_id, configured_rate, observed_rate, observed_count, status
from {{ ref('dq_summary') }}
where status in ('OUT_OF_TOLERANCE', 'NOT_CONFIGURED')
