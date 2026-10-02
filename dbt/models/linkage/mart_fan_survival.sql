-- RESTRICTED (schema `linkage`; counts only). Kaplan-Meier survival of FAN ACTIVENESS: time in months from a fan's origin to its first lapse (6 quiet months), by fan group and market type
-- (and with market type rolled up). Origins: the first month for new accounts, the first registration month for existing fans who were not lapsed then (int_fan_account_group). The end of the
-- data censors a spell; it is never a lapse. A step with fewer than k_min accounts at risk is flagged `reliable = false`.
{% set kmin = privacy_param('k_min') %}
with sp as (select fan_group, market_type, t, event from {{ ref('int_fan_lapse_spells') }}),

curves as (select fan_group, market_type, t, event from sp union all select fan_group, 'ALL', t, event from sp),

km as {{ kaplan_meier('curves', ['fan_group', 'market_type']) }}

select
    fan_group, market_type, t as months_since_origin, at_risk, events as lapses, censored, hazard, survival, greenwood_se, ci_low, ci_high,
    at_risk >= {{ kmin }}                                                   as reliable,
    '{{ var("methodology_version") }}'                                      as methodology_version
from km
order by fan_group, market_type, t
