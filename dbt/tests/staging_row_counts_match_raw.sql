-- Staging is 1:1 with raw grain. US and CA must equal raw; INTL equals raw minus logged junk rows.
with counts as (
    select 'US_LEAGUE' as source_system,
        (select count(*) from {{ source('raw', 'us_league_registrations') }}) as raw_rows,
        (select count(*) from {{ ref('stg_us_registrations') }}) as stg_rows
    union all
    select 'CA_CLUB',
        (select count(*) from {{ source('raw', 'ca_club_records') }}),
        (select count(*) from {{ ref('stg_ca_registrations') }})
    union all
    select 'INTL_FED',
        (select count(*) from {{ intl_classified_rows() }} where junk_reason is null),
        (select count(*) from {{ ref('stg_intl_registrations') }})
)
select * from counts where raw_rows <> stg_rows
