{{ config(tags=['phase4']) }}
-- The synthetic market of each registration (rework spec, section 2): from the postal code (a US ZIP3 or a Canadian FSA, by format), else from the country for
-- international returns, which carry no postal code. NULL market_id means the postal code did not map (a defect worth seeing, never guessed).
with r as (select registration_key, country_code, postal_code, {{ market_prefix('postal_code') }} as prefix from {{ ref('int_registrations_unioned') }}),

country_market as (select country_code, any_value(market_id) as market_id from {{ ref('market_map') }} where (region_code is null or region_code = '') group by 1)

select
    r.registration_key,
    coalesce(g.market_id, cm.market_id)                                     as market_id,
    case when g.market_id is not null then 'POSTAL_PREFIX' when cm.market_id is not null then 'COUNTRY' end as market_basis
from r
left join {{ ref('market_geo_map') }} g on g.prefix = r.prefix
left join country_market cm on cm.country_code = r.country_code and r.prefix is null
