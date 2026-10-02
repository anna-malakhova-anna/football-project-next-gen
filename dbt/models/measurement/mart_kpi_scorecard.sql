-- The KPI scorecard in long format: one row per participation year x KPI. Every kpi_id is in metric_catalog (a test
-- enforces it) and every row carries the methodology version. The data-trust KPIs sit beside the headline numbers by
-- design. low / high are the label-free identity bounds and exist only where the edge sets are recomputed (the north
-- star and international participants); they are NULL elsewhere, never faked.
-- A NULL value means "not defined" (for example new / returning / retention in the first data year, which is
-- left-censored), never zero.
-- yoy_change is the absolute change, yoy_change_pct the relative change (NULL for the rate KPIs, where use the points).
with g as (select * from {{ ref('mart_participation_global') }}),

u as (select * from {{ ref('mart_identity_uncertainty') }} where grain = 'GLOBAL'),

uc as (

    select participation_year,
           sum(participants_low) as intl_low, sum(participants_point) as intl_point, sum(participants_high) as intl_high
    from {{ ref('mart_identity_uncertainty') }}
    where grain = 'COUNTRY' and country_code <> 'US' group by 1

),

seg as (select * from {{ ref('mart_participation_segments') }} where grouping_id = 31),

c as (

    select participation_year,
           sum(participants_attributed) filter (where country_code <> 'US') as international_participants,
           count(*) filter (where participants_attributed > 0) as countries_with_participants
    from {{ ref('mart_participation_by_country') }} group by 1

),

dq as (

    select participation_year,
           count(*) filter (where has_counting_dq_issue) * 1.0 / count(*) as pct_registrations_failing_dq
    from {{ ref('fct_registration') }} group by 1

),

sources as (

    select count(*) filter (where onboarding_status in ('Modelled', 'Production')) as sources_onboarded,
           count(*) as sources_known
    from {{ ref('source_registry') }}

),

first_year as (select min(participation_year) as y from g),

kpis as (

    select g.participation_year, 'unique_participants' as kpi_id, g.unique_participants::double as value, u.participants_low::double as low, u.participants_high::double as high from g join u using (participation_year)
    union all select participation_year, 'new_participants', case when participation_year = (select y from first_year) then null else new_participants end, null, null from g
    union all select participation_year, 'returning_participants', case when participation_year = (select y from first_year) then null else returning_participants end, null, null from g
    union all select participation_year, 'reactivated_participants', case when participation_year = (select y from first_year) then null else reactivated_participants end, null, null from g
    union all select participation_year, 'retention_rate', retention_rate, null, null from g
    union all select participation_year, 'youth_girls_participants', youth_girls_participants, null, null from seg
    union all select participation_year, 'girls_share_of_youth', girls_share_of_youth, null, null from seg
    union all select c.participation_year, 'international_participants', c.international_participants::double, uc.intl_low::double, uc.intl_high::double from c join uc using (participation_year)
    union all select participation_year, 'countries_with_participants', countries_with_participants, null, null from c
    union all select participation_year, 'multi_org_participants', multi_org_participants, null, null from g
    union all select participation_year, 'registrations_per_participant', registrations_per_participant, null, null from g
    union all select participation_year, 'identity_range_pct', range_pct, null, null from u
    union all select participation_year, 'pct_participants_high_confidence', pct_participants_high_confidence, null, null from u
    union all select participation_year, 'open_review_items', open_review_items, null, null from u
    union all select g.participation_year, 'sources_onboarded', s.sources_onboarded, null, null from g cross join sources s
    union all select g.participation_year, 'sources_known', s.sources_known, null, null from g cross join sources s
    union all select participation_year, 'pct_registrations_failing_dq', pct_registrations_failing_dq, null, null from dq

)

select
    k.participation_year,
    k.kpi_id,
    m.kpi_group,
    m.name                                                                  as kpi_name,
    k.value,
    lag(k.value) over (partition by k.kpi_id order by k.participation_year) as prior_year_value,
    k.value - lag(k.value) over (partition by k.kpi_id order by k.participation_year) as yoy_change,
    case when m.unit <> 'rate'
         then round((k.value / nullif(lag(k.value) over (partition by k.kpi_id order by k.participation_year), 0) - 1), 5) end as yoy_change_pct,
    k.low,
    k.high,
    '{{ var("methodology_version") }}'                                      as methodology_version,
    current_timestamp                                                       as computed_at
from kpis k
join {{ ref('metric_catalog') }} m on m.metric_id = k.kpi_id
order by k.participation_year, m.kpi_group, k.kpi_id
