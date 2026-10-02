-- DESCRIPTIVE one-year retention rates by segment. These are associations between who a player was and whether they registered the next year; they
-- say nothing about why. A segment with a higher rate is not a segment that "causes" retention: the segments overlap (an age band and a division
-- describe largely the same players) and nobody was assigned to them at random. No causal language is used or intended.
-- Unit: a participant-year (t) whose next year (t+1) is observed and in which the player is still youth-eligible (an age-out is not a non-return).
-- Rows with participation_year NULL pool every year. Wilson 95% intervals. The segment is the player's attribute in year t.
{% set youth_max = privacy_param('youth_max_age') %}
{% set kmin = privacy_param('k_min') %}
with t as (

    select
        f.participant_id, f.participation_year, f.age_at_cutoff, f.age_band, f.sex, f.attributed_country_code, f.is_multi_org,
        f.primary_division, f.status,
        exists (select 1 from {{ ref('fct_participant_year') }} n
                where n.participant_id = f.participant_id and n.participation_year = f.participation_year + 1) as retained
    from {{ ref('fct_participant_year') }} f
    where f.participation_year + 1 <= (select last_observed_year from {{ ref('observation_window') }})
      and f.age_at_cutoff is not null
      and (f.age_at_cutoff + 1 <= {{ youth_max }} or f.age_at_cutoff > {{ youth_max }})

),

seg as (

    select 'ALL' as segment_type, 'ALL' as segment_value, participation_year, retained from t
    union all select 'sex', sex, participation_year, retained from t
    union all select 'age_band', age_band, participation_year, retained from t
    union all select 'country', attributed_country_code, participation_year, retained from t
    union all select 'multi_org', case when is_multi_org then 'MULTI_ORG' else 'SINGLE_ORG' end, participation_year, retained from t
    union all select 'division', primary_division, participation_year, retained from t
    union all select 'growth_status', status, participation_year, retained from t

),

g as (

    select
        segment_type, segment_value, participation_year,
        count(*)                                                            as eligible_n,
        count(*) filter (where retained)                                    as retained_n
    from seg
    group by grouping sets ((segment_type, segment_value, participation_year), (segment_type, segment_value))

),

w as (

    select *, retained_n * 1.0 / eligible_n as p, 1.96 as z from g

)

select
    segment_type,
    segment_value,
    participation_year,
    eligible_n,
    retained_n,
    round(p, 5)                                                             as retention_rate,
    round((p + z * z / (2 * eligible_n) - z * sqrt(p * (1 - p) / eligible_n + z * z / (4 * eligible_n * eligible_n))) / (1 + z * z / eligible_n), 5) as ci_low,
    round((p + z * z / (2 * eligible_n) + z * sqrt(p * (1 - p) / eligible_n + z * z / (4 * eligible_n * eligible_n))) / (1 + z * z / eligible_n), 5) as ci_high,
    eligible_n >= {{ kmin }}                                                as reliable,
    '{{ var("methodology_version") }}'                                      as methodology_version
from w
order by segment_type, segment_value, participation_year nulls first
