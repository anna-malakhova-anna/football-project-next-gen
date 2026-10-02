{{ config(tags=['phase4']) }}
-- EXEC share: unique participants per year with the label-free identity bounds (low, point, high): how far identity resolution alone could move the number.
-- Aggregate only, small cells suppressed. The bounds do not cover missing sources or errors in the source data.
with src as (

    select participation_year, participants_low as identity_participants_low, participants_point as identity_participants_point,
           participants_high as identity_participants_high
    from {{ ref('mart_identity_uncertainty') }} where grain = 'GLOBAL'

)

select participation_year, identity_participants_low, identity_participants_point, identity_participants_high, suppressed
from {{ suppress_small_cells('src', ['participation_year'], ['identity_participants_point'],
        rates={'identity_participants_low': ['identity_participants_point'], 'identity_participants_high': ['identity_participants_point']}) }}
order by participation_year
