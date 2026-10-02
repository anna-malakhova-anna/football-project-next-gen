-- Youth-to-adult transition rate: of the players who were 17 in year t and whose next year is observed, the share registered as adults in t+1.
-- Tracked on its own and never mixed into youth retention: ageing out of the youth programs is not a decision to stop playing, and whether a
-- player continues as an adult is a separate question. Pooled across years and by year.
{% set youth_max = privacy_param('youth_max_age') %}
{% set kmin = privacy_param('k_min') %}
with t as (

    select f.participant_id, f.participation_year,
           exists (select 1 from {{ ref('fct_participant_year') }} n
                   where n.participant_id = f.participant_id and n.participation_year = f.participation_year + 1) as continued
    from {{ ref('fct_participant_year') }} f
    where f.age_at_cutoff = {{ youth_max }} and f.participation_year + 1 <= (select last_observed_year from {{ ref('observation_window') }})

),

g as (

    select participation_year, count(*) as aged_out_n, count(*) filter (where continued) as continued_n
    from t group by grouping sets ((participation_year), ())

)

select
    participation_year,
    aged_out_n,
    continued_n,
    round(continued_n * 1.0 / aged_out_n, 5)                                as youth_to_adult_rate,
    aged_out_n >= {{ kmin }}                                                as reliable,
    '{{ var("methodology_version") }}'                                      as methodology_version
from g
order by participation_year nulls first
