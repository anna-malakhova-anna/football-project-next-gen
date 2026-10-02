-- Links that need no scoring because the source itself says "same person".
--   CA_CLUB   same member_uuid (stable within a club)
--   INTL_FED  same Player ID, except in countries that reissue IDs every year
--             (var intl_unstable_person_id_countries, from docs/source_inventory.md)
--   US_LEAGUE none: the source has no person id
{% set unstable = var('intl_unstable_person_id_countries') %}
with keyed as (

    select
        match_record_id,
        source_system,
        case
            when source_system = 'CA_CLUB' then 'CA_CLUB|' || source_person_id
            when source_system = 'INTL_FED'
                 and country_code not in ({{ unstable | map('tojson') | join(', ') | replace('"', "'") }})
                then 'INTL_FED|' || country_code || '|' || source_person_id
        end as id_key
    from {{ ref('idr_input_records') }}
    where source_person_id is not null

)

select
    a.match_record_id                                                       as record_a,
    b.match_record_id                                                       as record_b,
    'SOURCE_ID'                                                             as link_method,
    'DETERMINISTIC'                                                         as link_tier,
    'same ' || case a.source_system when 'CA_CLUB' then 'member_uuid' else 'Player ID' end as link_reason,
    {{ source_pair('a.source_system', 'b.source_system') }}                 as source_pair
from keyed a
join keyed b on a.id_key = b.id_key and a.match_record_id < b.match_record_id
where a.id_key is not null
