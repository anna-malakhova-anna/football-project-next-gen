{{ config(tags=['phase3']) }}
-- The policy is unambiguous: each audience / model / column appears once, no column is both allowed and denied for the
-- same audience and model, and share models are named for their audience (share_<audience>__<name>).
select 'duplicate_row' as problem, audience || '.' || model || '.' || "column" as detail
from {{ ref('audience_column_policy') }} group by audience, model, "column" having count(*) > 1
union all
select 'allowed_and_denied', a.audience || '.' || a.model || '.' || a."column"
from {{ ref('audience_column_policy') }} a join {{ ref('audience_column_policy') }} d
  on a.audience = d.audience and a."column" = d."column" and (a.model = d.model or d.model = '*' or a.model = '*')
where a.allowed = 'Y' and d.allowed = 'N'
union all
select 'model_name_does_not_match_audience', audience || '.' || model
from {{ ref('audience_column_policy') }}
where model <> '*' and model not like 'share\_' || audience || '\_\_%' escape '\'
