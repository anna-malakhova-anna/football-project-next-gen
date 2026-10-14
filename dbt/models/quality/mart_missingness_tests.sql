-- Is the missing value missing at random? (phase-5-spec 6.2.) For each KPI with a missing input and each year, a chi-square test of independence between "the value is missing on this record" and
-- four factors: the organization's registration channel, the division, the registration timing (quartile within the season) and the country. RECORD level (a registration), modelled sources,
-- exact duplicates excluded. p_value is the Wilson-Hilferty approximation (macro chisq_upper_p), good enough to decide "unlikely to be chance", not an exact figure.
-- A factor is flagged when p < 0.05 / 4 (Bonferroni over the four factors) AND the lowest and highest missing rates among its groups differ by at least 2 points, so a huge sample's trivial
-- difference is not called a pattern.
with base as (

    select
        u.season_year as participation_year, u.source_system, u.country_code,
        coalesce(u.canonical_division, 'UNMAPPED') as division,
        coalesce(r.channel, 'UNKNOWN') as channel,
        ntile(4) over (partition by u.season_year, u.season_term, u.source_system order by u.registered_at) as timing_quartile,
        u.registered_at is null as no_timestamp,
        u.sex = 'U' as sex_missing,
        u.birth_year is null as age_missing,
        u.is_minor
    from {{ ref('int_registrations_unioned') }} u
    left join {{ source('raw', 'org_registry') }} r on r.source_system = u.source_system and r.org_id = u.organization_id and r.season_year::integer = u.season_year
    where not coalesce(u.is_exact_duplicate, false)

),

long as (

    select participation_year, 'girls_share_of_youth' as kpi, 'channel' as factor, channel as grp, sex_missing as missing from base where coalesce(is_minor, false)
    union all select participation_year, 'girls_share_of_youth', 'division', division, sex_missing from base where coalesce(is_minor, false)
    union all select participation_year, 'girls_share_of_youth', 'registration_timing', timing_quartile::varchar, sex_missing from base where coalesce(is_minor, false) and not no_timestamp
    union all select participation_year, 'girls_share_of_youth', 'country', country_code, sex_missing from base where coalesce(is_minor, false)
    union all select participation_year, 'age_band_mix', 'channel', channel, age_missing from base
    union all select participation_year, 'age_band_mix', 'division', division, age_missing from base
    union all select participation_year, 'age_band_mix', 'registration_timing', timing_quartile::varchar, age_missing from base where not no_timestamp
    union all select participation_year, 'age_band_mix', 'country', country_code, age_missing from base

),

cells as (

    select participation_year, kpi, factor, grp, count(*) as n, count(*) filter (where missing) as n_missing from long group by all

),

totals as (

    select participation_year, kpi, factor, sum(n) as n_all, sum(n_missing) as missing_all, count(*) as groups,
           min(n_missing::double / n) as min_rate, max(n_missing::double / n) as max_rate
    from cells group by all

),

chi as (

    select c.participation_year, c.kpi, c.factor,
           sum(power(c.n_missing - c.n * t.missing_all::double / t.n_all, 2) / nullif(c.n * t.missing_all::double / t.n_all, 0)
             + power((c.n - c.n_missing) - c.n * (1 - t.missing_all::double / t.n_all), 2) / nullif(c.n * (1 - t.missing_all::double / t.n_all), 0)) as chi2,
           any_value(t.groups) - 1 as df, any_value(t.n_all) as records, any_value(t.missing_all) as records_missing,
           any_value(t.min_rate) as min_group_rate, any_value(t.max_rate) as max_group_rate
    from cells c join totals t using (participation_year, kpi, factor)
    where t.missing_all > 0 and t.missing_all < t.n_all
    group by all

)

select
    participation_year, kpi, factor, records, records_missing,
    round(records_missing::double / records, 5)                             as missing_rate,
    round(chi2, 2)                                                          as chi2,
    df,
    round({{ chisq_upper_p('chi2', 'df') }}, 6)                              as p_value,
    round(min_group_rate, 5)                                                as lowest_group_missing_rate,
    round(max_group_rate, 5)                                                as highest_group_missing_rate,
    {{ chisq_upper_p('chi2', 'df') }} < 0.05 / 4 and max_group_rate - min_group_rate >= 0.02 as associated_with_missingness
from chi
