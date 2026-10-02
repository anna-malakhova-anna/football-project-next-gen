-- EXEC share: aggregates only, small cells suppressed (macro suppress_small_cells, k_min from privacy_params).
-- One row per participation year. retention_rate is hidden whenever the returning count behind it is small.
with src as (

    select participation_year, unique_participants, registrations, registrations_per_participant,
           multi_org_participants, retention_rate, returning_participants
    from {{ ref('mart_participation_global') }}

)

select participation_year, unique_participants, registrations, registrations_per_participant,
       multi_org_participants, retention_rate, suppressed
from {{ suppress_small_cells('src', ['participation_year'], ['unique_participants', 'registrations', 'multi_org_participants'],
        rates={'registrations_per_participant': ['registrations', 'unique_participants'], 'retention_rate': ['returning_participants']}) }}
order by participation_year
