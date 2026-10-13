{{ config(tags=['phase5']) }}
-- The records scored per league and per market each add up to the in-scope records, and no tackle row got in.
select 'league total' as problem from (select sum(n_records) as n from {{ ref('dq_score_league') }}) where n <> (select count(*) from {{ ref('p5_record_quality') }})
union all
select 'market total' from (select sum(n_records) as n from {{ ref('dq_score_market') }}) where n <> (select count(*) from {{ ref('p5_record_quality') }})
union all
select 'tackle row scored' where exists (select 1 from {{ ref('p5_record_quality') }} q join {{ ref('stg_p5_registrations') }} s using (feed, source_record_id) where not s.is_flag)
