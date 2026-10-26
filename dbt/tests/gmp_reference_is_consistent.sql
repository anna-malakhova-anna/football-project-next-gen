{{ config(tags=['phase7']) }}
-- Phase 7 reference seeds: one row per club and country, 32 anonymous clubs, and every one of the 22 program markets held by at least one club.
select 'duplicate club-country row' as problem, club_id || ' ' || country_code as detail
from {{ ref('gmp_club_rights') }}
group by club_id, country_code
having count(*) > 1
union all
select 'club count is not 32', cast(count(distinct club_id) as varchar)
from {{ ref('gmp_club_rights') }}
having count(distinct club_id) <> 32
union all
select 'market count is not 22', cast(count(*) as varchar)
from {{ ref('gmp_markets') }}
having count(*) <> 22
union all
select 'market held by no club', m.country_code
from {{ ref('gmp_markets') }} m
where not exists (select 1 from {{ ref('gmp_club_rights') }} r where r.country_code = m.country_code)
