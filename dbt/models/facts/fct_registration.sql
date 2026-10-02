-- One row per registration (the grain of bridge_registration_participant) with its counting attributes.
-- is_valid_registration (rule C2): not an exact duplicate, not a junk row (junk is dropped in staging, so none reach
-- here), and inside a reporting period. Records with an impossible DOB are VALID: the person is real, only the DOB is bad.
with b as (select * from {{ ref('bridge_registration_participant') }}),

r as (select * from {{ ref('int_registrations_unioned') }}),

periods as (select participation_year from {{ ref('reporting_periods') }} where period_type = 'YEAR'),

flag_severity as (select flag, severity from {{ ref('dq_flag_severity') }}),

flags as (

    select registration_key,
           bool_or(fs.severity = 'AFFECTS_COUNT') as has_counting_dq_issue,
           bool_or(fs.severity = 'MISSING_VALUE') as has_missing_value
    from (select registration_key, unnest(dq_flags) as flag from r) f
    join flag_severity fs using (flag)
    group by registration_key

)

select
    b.registration_key,
    b.participant_id,
    r.season_year                                                           as participation_year,
    r.source_system,
    r.season_term,
    case when r.source_system = 'US_LEAGUE' then r.season_term end          as us_season_term,
    r.organization_id,
    r.country_code,
    r.canonical_division,
    r.age_at_cutoff,
    case
        when r.is_exact_duplicate then false
        when p.participation_year is null then false
        when r.registered_at is not null and extract(year from r.registered_at) <> r.season_year then false
        else true
    end                                                                     as is_valid_registration,
    case
        when r.is_exact_duplicate then 'EXACT_DUPLICATE'
        when p.participation_year is null then 'NO_REPORTING_PERIOD'
        when r.registered_at is not null and extract(year from r.registered_at) <> r.season_year then 'REGISTERED_OUTSIDE_PERIOD'
    end                                                                     as invalid_reason,
    b.link_method,
    b.match_probability,
    r.registered_at,
    {{ term_order('r.season_term') }}                                       as term_order,
    r.dq_flags,
    coalesce(f.has_counting_dq_issue, false)                                as has_counting_dq_issue,
    coalesce(f.has_missing_value, false)                                    as has_missing_value
from b
join r using (registration_key)
left join periods p on p.participation_year = r.season_year
left join flags f on f.registration_key = b.registration_key
