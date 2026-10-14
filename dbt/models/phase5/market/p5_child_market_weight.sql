{{ config(schema='phase5_restricted') }}
-- RESTRICTED. Each child's weight in each market. A child with a usable ZIP counts 1 in their market (PLACED). A child with none cannot be placed, so their one unit is spread over markets in
-- proportion to where placed children of THE SAME LEAGUE live (ALLOCATED_LEAGUE; at least 5 placed children needed), else of the same state (ALLOCATED_STATE), else it stays UNALLOCATED. This is an
-- estimate, labelled as one, and the allocated share of every market is reported next to it. No third-party data is used.
with placed as (

    select c.*, m.region_code as market_state from {{ ref('p5_child') }} c join {{ ref('market_map') }} m on m.market_id = c.market_id
),

league_dist as (

    select league_group, market_id, count(*)::double / sum(count(*)) over (partition by league_group) as w, sum(count(*)) over (partition by league_group) as n_placed
    from placed group by 1, 2

),

state_dist as (

    select league_state as state, market_id, w from (
        select p.league_state, p.market_id, count(*)::double / sum(count(*)) over (partition by p.league_state) as w
        from placed p where p.league_state is not null group by 1, 2
    )

),

unplaced as (select * from {{ ref('p5_child') }} where market_id = 'UNPLACED')

select p5_person_id, market_id, 1.0 as weight, 'PLACED' as basis from placed
union all
select u.p5_person_id, l.market_id, l.w, 'ALLOCATED_LEAGUE'
from unplaced u join league_dist l on l.league_group = u.league_group and l.n_placed >= 5
union all
select u.p5_person_id, s.market_id, s.w, 'ALLOCATED_STATE'
from unplaced u
join state_dist s on s.state = u.league_state
where not exists (select 1 from league_dist l where l.league_group = u.league_group and l.n_placed >= 5)
union all
select u.p5_person_id, 'UNALLOCATED', 1.0, 'UNALLOCATED'
from unplaced u
where not exists (select 1 from league_dist l where l.league_group = u.league_group and l.n_placed >= 5)
  and not exists (select 1 from state_dist s where s.state = u.league_state)
