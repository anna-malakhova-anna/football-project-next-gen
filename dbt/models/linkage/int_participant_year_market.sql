{{ config(tags=['phase5']) }}
-- RESTRICTED (schema `linkage`). Where does each participant-year live, in CLUB MARKETS (phase-5-spec 9)? One row per participant, year and club market, with an allocation weight; the weights of a
-- participant-year add up to 1. Every market-level model reads this one, so the allocation is made once.
--   ZIP3                          the participant's home ZIP3 (the most frequent among their valid registrations of the year, then the latest) mapped through club_market_map; a shared ZIP3 splits equally between
--                                 its markets (the labelled default). A ZIP3 outside any club is NO_CLUB_MARKET.
--   OUTSIDE_US                    Canadian and international participants: the club-market lens is domestic by design.
--   UNPLACED_ALLOCATED_ORG        a US participant with no usable ZIP: spread over the club markets where the PLACED participants of the same organization and year live (an ESTIMATE, labelled)
--   UNPLACED_ALLOCATED_STATE      the same, from the organization's state, when the organization has no placed participant
--   UNALLOCATED                   no way to place them: kept as its own row, never put in a market
-- The basis column is carried everywhere so a market's figure can always be split into placed and allocated parts: nothing is mixed silently.
with py as (select participant_id, participation_year, attributed_country_code from {{ ref('fct_participant_year') }}),

zip3 as (

    select participant_id, participation_year, zip3 from (
        select b.participant_id, f.participation_year, left(u.postal_code, 3) as zip3,
               row_number() over (partition by b.participant_id, f.participation_year order by count(*) desc, max(f.registered_at) desc nulls last, left(u.postal_code, 3)) as rn
        from {{ ref('fct_registration') }} f
        join {{ ref('int_registrations_unioned') }} u on u.registration_key = f.registration_key
        join {{ ref('bridge_registration_participant') }} b on b.registration_key = f.registration_key
        where f.is_valid_registration and u.source_system = 'US_LEAGUE' and u.postal_code is not null
        group by b.participant_id, f.participation_year, left(u.postal_code, 3)
    ) where rn = 1

),

org as (

    -- the organization a US participant-year is attributed to: the most recent valid registration
    select participant_id, participation_year, organization_id, region_code from (
        select b.participant_id, f.participation_year, f.organization_id, u.region_code,
               row_number() over (partition by b.participant_id, f.participation_year order by f.term_order desc, f.registered_at desc nulls last, f.registration_key) as rn
        from {{ ref('fct_registration') }} f
        join {{ ref('int_registrations_unioned') }} u on u.registration_key = f.registration_key
        join {{ ref('bridge_registration_participant') }} b on b.registration_key = f.registration_key
        where f.is_valid_registration and u.source_system = 'US_LEAGUE'
    ) where rn = 1

),

placed as (

    select py.participant_id, py.participation_year, m.club_market_id, m.allocation_weight as weight, 'ZIP3' as basis
    from py join zip3 z using (participant_id, participation_year)
    join {{ ref('club_market_map') }} m on m.zip3 = z.zip3
    where py.attributed_country_code = 'US'

),

outside as (

    select participant_id, participation_year, 'OUTSIDE_US' as club_market_id, 1.0 as weight, 'OUTSIDE_US' as basis from py where attributed_country_code is distinct from 'US'

),

unplaced as (

    select py.participant_id, py.participation_year, o.organization_id, o.region_code
    from py left join org o using (participant_id, participation_year)
    where py.attributed_country_code = 'US' and not exists (select 1 from placed p where p.participant_id = py.participant_id and p.participation_year = py.participation_year)

),

org_dist as (

    select o.organization_id, p.participation_year, p.club_market_id, sum(p.weight) / sum(sum(p.weight)) over (partition by o.organization_id, p.participation_year) as w, count(distinct p.participant_id) over (partition by o.organization_id, p.participation_year) as n_placed
    from placed p join org o on o.participant_id = p.participant_id and o.participation_year = p.participation_year
    group by o.organization_id, p.participation_year, p.club_market_id, p.participant_id, p.weight
),

org_dist_n as (

    select organization_id, participation_year, club_market_id, sum(w) / sum(sum(w)) over (partition by organization_id, participation_year) as w, max(n_placed) as n_placed
    from org_dist group by organization_id, participation_year, club_market_id

),

state_dist as (

    select o.region_code as state, p.participation_year, p.club_market_id, sum(p.weight) / sum(sum(p.weight)) over (partition by o.region_code, p.participation_year) as w
    from placed p join org o on o.participant_id = p.participant_id and o.participation_year = p.participation_year
    group by o.region_code, p.participation_year, p.club_market_id

),

allocated as (

    select u.participant_id, u.participation_year, d.club_market_id, d.w as weight, 'UNPLACED_ALLOCATED_ORG' as basis
    from unplaced u join org_dist_n d on d.organization_id = u.organization_id and d.participation_year = u.participation_year and d.n_placed >= 5
    union all
    select u.participant_id, u.participation_year, s.club_market_id, s.w, 'UNPLACED_ALLOCATED_STATE'
    from unplaced u join state_dist s on s.state = u.region_code and s.participation_year = u.participation_year
    where not exists (select 1 from org_dist_n d where d.organization_id = u.organization_id and d.participation_year = u.participation_year and d.n_placed >= 5)
    union all
    select u.participant_id, u.participation_year, 'UNALLOCATED', 1.0, 'UNALLOCATED'
    from unplaced u
    where not exists (select 1 from org_dist_n d where d.organization_id = u.organization_id and d.participation_year = u.participation_year and d.n_placed >= 5)
      and not exists (select 1 from state_dist s where s.state = u.region_code and s.participation_year = u.participation_year)

)

select * from placed union all select * from outside union all select * from allocated
