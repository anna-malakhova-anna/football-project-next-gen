-- DP outcomes, the OUTSIDE view of monitoring (Phase 6): is the portfolio moving the three business goals? Goal x KPI x year, built from existing marts and shares ONLY: no new counting logic and no
-- answer-key number. Every KPI carries the product that delivers it and its data-trust companion (Phase 3 principle: trust is shown next to the number). Where the data cannot answer by design, the row
-- says so (status NOT_MEASURABLE_BY_DESIGN) instead of showing a number. Adoption is NOT here: it is instrumented in ops_product_usage_log and has no real users yet.
{% set k = privacy_param('k_min') %}
with y as (select max(participation_year) as y from {{ ref('share_exec__participation_bounds') }}),

bounds as (select participation_year, identity_participants_low as lo, identity_participants_point as pt, identity_participants_high as hi from {{ ref('share_exec__participation_bounds') }}),

idr as (select participation_year, round(100.0 * (hi - lo) / pt, 2) as range_pct from bounds),

country as (select participation_year, country_code, participants_attributed, suppressed from {{ ref('share_exec__participation_by_country') }} where country_code is not null),

girls as (

    select participation_year, value_known_only, bound_low, bound_high, missing_share
    from {{ ref('mart_missingness_bias') }} where kpi = 'girls_share_of_youth' and club_market_id = 'ALL' and segment_value = 'ALL'

),

cov as (

    select participation_year, sum(orgs_known) as known, sum(orgs_reporting) as reporting, sum(orgs_dark) as dark, sum(participants_allocated) as allocated,
           sum(interval_low) as allocated_low, sum(interval_high) as allocated_high, count(*) filter (where orgs_dark > 0) as markets_with_dark
    from {{ ref('mart_market_coverage') }} where regexp_matches(club_market_id, '^CM-') and participants_allocated >= {{ k }} group by 1

),

ret as (select survival, ci_low, ci_high, n_entrants from {{ ref('mart_retention_survival') }} where segment_type = 'ALL' and segment_value = 'ALL' and years_since_entry = 1),

fan as (select estimator, fan_uplift_pct, fan_uplift_ci_low_pct as lo, fan_uplift_ci_high_pct as hi, fan_treated_households as n from {{ ref('share_exec__fan_engagement_effect') }}),

inc as (select * from {{ ref('share_exec__acquisition_incrementality') }}),

link as (select country_code, household_link_rate from {{ ref('share_exec__household_link_rate') }}),

tier as (select age_tier, households, share_of_registered, suppressed from {{ ref('mart_conversion_funnel_by_tier') }} where step_no = 5),

rows_ as (

    -- G1: grow NFL presence globally
    select 'G1' as goal_id, 'countries_with_participants' as kpi_id, 'Countries with at least one participant' as kpi_label, cast(null as varchar) as segment, c.participation_year as year,
           cast(count(*) as double) as value, cast(null as double) as value_low, cast(null as double) as value_high, 'count' as unit, 'DP3' as product_id,
           'Countries whose count is hidden (under the small-cell size)' as trust_label, cast(count(*) filter (where c.suppressed <> 'NONE') as double) as trust_value, 'MEASURED' as status
    from country c group by c.participation_year
    union all
    select 'G1', 'international_participants', 'Participants outside the US and Canada (attributed)', null, c.participation_year, cast(sum(c.participants_attributed) as double), null, null, 'count', 'DP3',
           'Identity range, % of the global count', max(i.range_pct), 'MEASURED'
    from country c join idr i using (participation_year) where c.country_code not in ('US', 'CA') and c.suppressed = 'NONE' group by c.participation_year
    union all
    select 'G1', 'global_participants', 'Registered participants worldwide', null, b.participation_year, cast(b.pt as double), cast(b.lo as double), cast(b.hi as double), 'count', 'DP3',
           'Identity range, % of the count', i.range_pct, 'MEASURED'
    from bounds b join idr i using (participation_year)
    union all
    select 'G1', 'federation_clubs_reporting', 'Federation organizations that sent a file, of those known', null, d.season_year, cast(count(*) filter (where d.reported) as double), null, cast(count(*) as double), 'count', 'DP3',
           'Share of known organizations reporting (%)', round(100.0 * count(*) filter (where d.reported) / count(*), 1), 'MEASURED'
    from {{ ref('dq_scorecard_org') }} d where d.source_system = 'INTL_FED' and d.purpose = 'COUNT' and d.dimension = 'PURPOSE_SCORE' group by d.season_year

    -- G2: grow flag football in the US
    union all
    select 'G2', 'us_participants', 'Participants in the US (attributed)', null, c.participation_year, cast(c.participants_attributed as double), null, null, 'count', 'DP4',
           'Identity range, % of the global count', i.range_pct, 'MEASURED'
    from country c join idr i using (participation_year) where c.country_code = 'US' and c.suppressed = 'NONE'
    union all
    select 'G2', 'girls_share_of_youth', 'Girls'' share of youth participants (known gender)', null, g.participation_year, g.value_known_only, g.bound_low, g.bound_high, 'ratio', 'DP4',
           'Share of youth with gender not recorded', g.missing_share, 'MEASURED'
    from girls g
    union all
    select 'G2', 'retention_one_year', 'Still playing one season after entry (Kaplan-Meier)', null, (select y from y), r.survival, r.ci_low, r.ci_high, 'ratio', 'DP4',
           'Entrants behind the estimate', cast(r.n_entrants as double), 'MEASURED'
    from ret r
    union all
    select 'G2', 'leagues_reporting_share', 'Known US leagues that sent a file', null, v.participation_year, round(100.0 * v.reporting / v.known, 1), null, null, 'percent', 'DP4',
           'Known leagues that sent no file', cast(v.dark as double), 'MEASURED'
    from cov v where v.known > 0
    union all
    select 'G2', 'market_participants_with_coverage', 'Players counted in club markets (range allows for leagues that sent no file)', null, v.participation_year, round(v.allocated, 0), round(v.allocated_low, 0), round(v.allocated_high, 0), 'count', 'DP4',
           'Markets with at least one league that sent no file', cast(v.markets_with_dark as double), 'MEASURED'
    from cov v

    -- G3: track conversion of flag participants and families to fans, protecting children
    union all
    select 'G3', 'fan_engagement_uplift', 'Fan engagement uplift after first registration (matched; canonical)', null, (select y from y), f.fan_uplift_pct, f.lo, f.hi, 'ratio', 'DP5',
           'Naive companion (existing fans); it overstates', n.fan_uplift_pct, 'MEASURED'
    from fan f cross join (select fan_uplift_pct from fan where estimator = 'NAIVE_EXISTING') n where f.estimator = 'DID_ADDITIVE'
    union all
    select 'G3', 'fans_created_by_flag', 'Fans created by flag (new fan accounts among families who were not fans)', null, (select y from y), cast(i.incremental_fan_accounts as double), cast(i.incremental_fan_accounts_ci_low as double), cast(i.incremental_fan_accounts_ci_high as double), 'count', 'DP5',
           'Market-years compared', cast(i.market_years_compared as double), 'MEASURED'
    from inc i
    union all
    select 'G3', 'fans_created_per_100_households', 'Fans created by flag, per 100 participant households', null, (select y from y), i.incremental_fan_accounts_per_100_households, i.incremental_fan_accounts_per_100_households_ci_low, i.incremental_fan_accounts_per_100_households_ci_high, 'ratio', 'DP5',
           'Participant households compared', cast(i.participant_households_compared as double), 'MEASURED'
    from inc i
    union all
    select 'G3', 'linked_household_rate', 'Participant households linked to a fan account', null, (select y from y), l.household_link_rate, null, null, 'ratio', 'DP5',
           'Lowest link rate in any country (the bias: linking is uneven)', (select min(household_link_rate) from link where country_code is not null), 'MEASURED'
    from link l where l.country_code is null
    union all
    select 'G3', 'activatable_households', 'Households a guardian has agreed a club may contact, by the age tier of the youngest child', t.age_tier, (select y from y), cast(t.households as double), null, null, 'count', 'DP5',
           'Share of registered households in the tier', t.share_of_registered, case when t.households is null then 'SUPPRESSED' else 'MEASURED' end
    from tier t
    union all
    select 'G3', 'youth_to_adult_fan_transition', 'Players who turn 18 and become their own fan record (fresh consent)', null, (select y from y), cast(null as double), null, null, 'count', 'DP5',
           'Fresh consent at 18 and no carry-over: a youth record is not linked to the adult by design', cast(null as double), 'NOT_MEASURABLE_BY_DESIGN'

)

select goal_id, kpi_id, kpi_label, segment, year, value, value_low, value_high, unit, product_id, trust_label, trust_value, status
from rows_
order by goal_id, kpi_id, segment nulls first, year
