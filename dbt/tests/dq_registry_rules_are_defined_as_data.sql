{{ config(tags=['phase5']) }}
-- The registry is the only place a rule is defined. A RECORD or ORG_SEASON rule has SQL; a CONTRACT rule has NONE (the contract owns its measurement) and names its contract; a STANDARD rule has none
-- (the validate_against_standard macro measures it), is INFO and at ORG_SEASON grain;
-- an INFO rule has no threshold; an ERROR or WARN rule has at least one; every purpose named is a known purpose; every threshold is a rate; every rule has guidance and an owner.
select rule_id, 'bad definition' as problem
from {{ ref('dq_rule_registry') }} r
where (r.origin not in ('CONTRACT', 'STANDARD') and nullif(trim(r.check_sql), '') is null)
   or (r.origin = 'STANDARD' and (nullif(trim(r.check_sql), '') is not null or r.grain <> 'ORG_SEASON' or r.severity <> 'INFO'))
   or (r.origin = 'CONTRACT' and (nullif(trim(r.check_sql), '') is not null or nullif(trim(r.contract_ref), '') is null or r.grain <> 'SOURCE_SEASON'))
   or (r.severity = 'INFO' and coalesce(r.threshold_count, r.threshold_segment, r.threshold_geo, r.threshold_retain, r.threshold_activate) is not null)
   or (r.severity in ('ERROR', 'WARN') and coalesce(r.threshold_count, r.threshold_segment, r.threshold_geo, r.threshold_retain, r.threshold_activate) is null)
   or coalesce(r.threshold_count, 0) not between 0 and 1 or coalesce(r.threshold_segment, 0) not between 0 and 1 or coalesce(r.threshold_geo, 0) not between 0 and 1
   or coalesce(r.threshold_retain, 0) not between 0 and 1 or coalesce(r.threshold_activate, 0) not between 0 and 1
   or nullif(trim(r.fix_guidance), '') is null or nullif(trim(r.owner_role), '') is null
union all
select r.rule_id, 'unknown purpose ' || p.purpose
from {{ ref('dq_rule_registry') }} r, unnest(string_split(coalesce(r.purposes, ''), '|')) as p(purpose)
where p.purpose <> '' and p.purpose not in (select purpose from {{ ref('dq_purposes') }})
union all
select r.rule_id, 'purpose listed without a threshold or threshold without a purpose'
from {{ ref('dq_rule_registry') }} r
where (list_contains(string_split(coalesce(r.purposes, ''), '|'), 'COUNT') <> (r.threshold_count is not null))
   or (list_contains(string_split(coalesce(r.purposes, ''), '|'), 'SEGMENT') <> (r.threshold_segment is not null))
   or (list_contains(string_split(coalesce(r.purposes, ''), '|'), 'GEO') <> (r.threshold_geo is not null))
   or (list_contains(string_split(coalesce(r.purposes, ''), '|'), 'RETAIN') <> (r.threshold_retain is not null))
   or (list_contains(string_split(coalesce(r.purposes, ''), '|'), 'ACTIVATE') <> (r.threshold_activate is not null))
