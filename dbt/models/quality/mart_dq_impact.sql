-- depends_on: {{ ref('dq_rule_registry') }}
-- depends_on: {{ ref('dq_record_base') }}
-- depends_on: {{ ref('observation_window') }}
-- What each rule COSTS, in the units a KPI is counted in (phase-5-spec 6.3): not "8% null DOB" but "this many participants". One row per rule x population x season x purpose.
--   participants_lost   persons whose EVERY evaluable record in the season fails the rule: for COUNT they drop out of a strict count, for SEGMENT / GEO / RETAIN they cannot be placed in a
--                       segment, a place or a cohort. Bounds, not estimates: it is exactly what would be lost if the rule's failures were excluded.
--   households_lost     (modelled sources, where the Phase 4 household linkage exists) households whose every active member is lost this way: the ACTIVATE unit.
--   identity_merges_touched  (COUNT rows) the PROBABLE identity links that widen the participant count's bounds (point minus low) where either record fails the rule: the uncertain merges the rule
--                       is entangled in. An upper-bound attribution: one merge can be touched by several rules.
--   impact_units        households_lost for ACTIVATE where known, participants_lost otherwise; impact_per_failing_record = impact_units / records_failing (the rule's yield, used to rank fixes).
--   rank_in_purpose, cumulative_share   the Pareto: rules ordered by impact within a season, population and purpose, with the running share of the total.
-- population: MODELLED (US_LEAGUE, CA_CLUB, INTL_FED: the headline KPIs) or CHANNEL_FEED (the six Contracted feeds, outside the counts).
with p as (

    {{ dq_impact_person_rows() }}

),

pop as (select p.*, case when source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') then 'MODELLED' else 'CHANNEL_FEED' end as population from p),

persons as (

    select rule_id, population, season_year, sum(records_failing) as records_failing, count(*) as persons_with_failures,
           count(*) filter (where all_fail) as participants_lost
    from pop group by all

),

active as (

    select h.household_id, b.season_year, count(distinct b.person_id) as members
    from {{ ref('dq_record_base') }} b join {{ ref('int_household') }} h on h.participant_id = b.person_id
    where b.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by all

),

hh as (

    select p.rule_id, p.season_year, count(*) as households_lost
    from (
        select p.rule_id, p.season_year, h.household_id, count(*) filter (where p.all_fail) as lost_members
        from pop p join {{ ref('int_household') }} h on h.participant_id = p.person_id
        where p.population = 'MODELLED' group by all
    ) p
    join active a on a.household_id = p.household_id and a.season_year = p.season_year
    where p.lost_members = a.members
    group by 1, 2

),

merges as (

    select e.record_a, e.record_b
    from {{ ref('idr_match_edges') }} e
    join {{ ref('idr_clusters') }} ca on ca.matcher = e.matcher and ca.stage = e.stage and ca.scope = 'AUTO' and ca.match_record_id = e.record_a
    join {{ ref('idr_clusters') }} cb on cb.matcher = e.matcher and cb.stage = e.stage and cb.scope = 'AUTO' and cb.match_record_id = e.record_b
    where e.matcher = '{{ var("matcher") }}' and e.stage = 'POST_REVIEW' and e.tier = 'PROBABLE' and ca.cluster_id <> cb.cluster_id

),

merge_rows as (

    {{ dq_impact_merge_rows() }}

),

reg as (

    select rule_id, dimension, severity, owner_role, fix_guidance, unnest(string_split(purposes, '|')) as purpose
    from {{ ref('dq_rule_registry') }} where coalesce(purposes, '') <> ''

),

joined as (

    select
        r.rule_id, r.dimension, r.severity, r.purpose, s.population, s.season_year,
        s.records_failing, s.participants_lost,
        case when s.population = 'MODELLED' then coalesce(h.households_lost, 0) end                        as households_lost,
        case when r.purpose = 'COUNT' and s.population = 'MODELLED' then coalesce(m.merges_touched, 0) end as identity_merges_touched,
        case when r.purpose = 'ACTIVATE' and s.population = 'MODELLED' then coalesce(h.households_lost, 0) else s.participants_lost end as impact_units,
        case when r.purpose = 'ACTIVATE' and s.population = 'MODELLED' then 'HOUSEHOLDS' else 'PARTICIPANTS' end as unit
    from persons s
    join reg r on r.rule_id = s.rule_id
    left join hh h on h.rule_id = s.rule_id and h.season_year = s.season_year
    left join merge_rows m on m.rule_id = s.rule_id and m.season_year = s.season_year

)

select
    *,
    round(impact_units::double / nullif(records_failing, 0), 6)                                            as impact_per_failing_record,
    rank() over (partition by season_year, population, purpose order by impact_units desc, rule_id)        as rank_in_purpose,
    round(sum(impact_units) over (partition by season_year, population, purpose order by impact_units desc, rule_id)::double
          / nullif(sum(impact_units) over (partition by season_year, population, purpose), 0), 4)          as cumulative_share
from joined
