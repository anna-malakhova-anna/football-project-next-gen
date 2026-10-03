{{ config(tags=['phase4']) }}
-- EXEC share: RFM segment mix of fan accounts by year and fan group (EXISTING_FAN, NET_NEW...): how many accounts sit in each recency / frequency / monetary segment and the share of the group.
-- Segments are quintile-based (NTILE 5) and relative to the year's own accounts. AGGREGATE ONLY (restricted `linkage` schema, ADR-009): counts and shares, small cells suppressed.
with src as (

    select year, fan_group, segment, accounts as rfm_accounts, share_of_group as rfm_share
    from {{ ref('mart_fan_rfm') }}

)

select year, fan_group, segment, rfm_accounts, rfm_share, suppressed
from {{ suppress_small_cells('src', ['year', 'fan_group', 'segment'], ['rfm_accounts'], rates={'rfm_share': ['rfm_accounts']}) }}
order by year, fan_group, segment
