-- depends_on: {{ ref('p5_params') }}
-- depends_on: {{ ref('p5_market_age_cells') }}
-- CLUB-FACING. Children observed per market and age band, with the market total. Aggregate only: no child-level row exists in this table. Primary suppression below club_min_cell (default 10);
-- secondary suppression (macro suppress_small_cells, ADR-006) so a hidden cell cannot be recovered from the published total by subtraction. Placed children only: the market estimate
-- (p5_club_market_view) is the figure that includes unplaced children. Shared markets appear for every club that shares them, with the same market-level figures (never split).
with cells as (

    select market_id, age_band, children
    from {{ ref('p5_market_age_cells') }}
    where market_id in (select market_id from {{ ref('p5_club_territory') }})

),

suppressed as (

    {{ suppress_small_cells('cells', ['market_id', 'age_band'], ['children'], k=p5_param('club_min_cell')) }}

)

select
    t.club_id,
    s.market_id,
    s.age_band,
    s.children,
    s.suppressed,
    t.role                                                                  as club_market_role
from suppressed s
join {{ ref('p5_club_territory') }} t on t.market_id = s.market_id
