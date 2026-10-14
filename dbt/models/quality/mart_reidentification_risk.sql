{{ config(tags=['phase5']) }}
-- How identifying is a participant-year dataset held at each minimization variant's granularity? Label-free (no ground truth).
-- Quasi-identifiers: (participation year, date of birth at the variant's precision, postal code at the variant's precision, sex, attributed country) - the analyst share's quasi-identifiers
-- (share_analyst__participant_year) with the variant's coarsening applied, so V2 is what that share holds today and V0 is what it would hold if it carried the collected values.
-- An equivalence class is a group of participant-years sharing all of them; a row in a class smaller than privacy_params.k_min is at risk. A participant-year in a class of one is unique.
-- Direct identifiers are not quasi-identifiers and are counted separately: `contact_fields_held` is the number of guardian contact fields the variant keeps (email, phone; a hashed email counts
-- as a pseudonymous identifier, not as zero).
-- Participant-years with an unknown value are grouped with the others that lack it (NULL is a value here). Small groups of the unknown are a finding of the data, not hidden.
with latest_postal as (

    select participant_id, postal_code
    from (
        select b.participant_id, u.postal_code,
               row_number() over (partition by b.participant_id order by u.season_year desc, {{ term_order('u.season_term') }} desc, u.registered_at desc nulls last, u.registration_key) as rn
        from {{ ref('bridge_registration_participant') }} b
        join {{ ref('int_registrations_unioned') }} u on u.registration_key = b.registration_key
        where u.postal_code is not null
    ) where rn = 1

),

py as (

    select f.participant_id, f.participation_year, f.sex, f.attributed_country_code as country_code,
           d.dob, d.dob_precision, d.birth_year, p.postal_code
    from {{ ref('fct_participant_year') }} f
    join {{ ref('dim_participant') }} d on d.participant_id = f.participant_id
    left join latest_postal p on p.participant_id = f.participant_id

),

tokens as (

    select
        v.variant_id, v.sort_order, v.label, py.participation_year, py.sex, py.country_code,
        case v.dob_treatment
            when 'FULL' then case when py.dob_precision = 'DAY' then cast(py.dob as varchar) else cast(py.birth_year as varchar) end
            when 'YEAR_MONTH' then case when py.dob_precision = 'DAY' then strftime(py.dob, '%Y-%m') else cast(py.birth_year as varchar) end
            else cast(py.birth_year as varchar)
        end as dob_token,
        case v.postal_treatment when 'ZIP3' then left(py.postal_code, 3) else py.postal_code end as postal_token,
        1 + (case when v.phone_treatment = 'KEEP' then 1 else 0 end) as contact_fields_held
    from py cross join {{ ref('minimization_variants') }} v

),

classed as (

    select *, count(*) over (partition by variant_id, participation_year, dob_token, postal_token, sex, country_code) as class_size
    from tokens

)

select
    variant_id, sort_order, label,
    count(*)                                                                as participant_years,
    count(distinct (participation_year, dob_token, postal_token, sex, country_code)) as equivalence_classes,
    min(class_size)                                                         as smallest_class,
    round(avg(class_size), 2)                                               as average_class_size_per_row,
    round(count(*) / count(distinct (participation_year, dob_token, postal_token, sex, country_code)), 2) as average_class_size,
    count(*) filter (where class_size = 1)                                  as unique_rows,
    round(100.0 * count(*) filter (where class_size = 1) / count(*), 2)     as pct_unique,
    count(*) filter (where class_size < {{ privacy_param('k_min') }})       as rows_below_k_min,
    round(100.0 * count(*) filter (where class_size < {{ privacy_param('k_min') }}) / count(*), 2) as pct_rows_below_k_min,
    {{ privacy_param('k_min') }}                                            as k_min,
    max(contact_fields_held)                                                as contact_fields_held
from classed
group by 1, 2, 3
