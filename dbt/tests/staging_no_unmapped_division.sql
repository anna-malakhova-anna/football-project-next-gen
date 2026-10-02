-- Every raw division / program / category label must map to a canonical division (division_map seed).
-- Returns the unmapped labels; any row fails the build.
select 'US_LEAGUE' as source_system, division_label_raw, count(*) as n
from {{ ref('stg_us_registrations') }} where canonical_division is null group by 2
union all
select 'CA_CLUB', division_label_raw, count(*)
from {{ ref('stg_ca_registrations') }} where canonical_division is null group by 2
union all
select 'INTL_FED', division_label_raw, count(*)
from {{ ref('stg_intl_registrations') }} where canonical_division is null group by 2
