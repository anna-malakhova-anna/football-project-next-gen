{{ config(tags=['phase7']) }}
-- The partner share is a set of per-federation report cards: every row names exactly one federation that is a program market sending federation
-- returns, a federation has at most three fixes, and no published records_affected is a small cell.
select 'row without a federation' as problem, cast(null as varchar) as detail from {{ ref('share_partner__federation_report_card') }} where federation is null
union all
select 'federation is not a program market', federation from {{ ref('share_partner__federation_report_card') }} r
where not exists (select 1 from {{ ref('gmp_markets') }} m where m.country_code = r.federation)
union all
select 'more than three fixes', federation from {{ ref('share_partner__federation_report_card') }} group by federation having count(*) > 3
union all
select 'small cell published', federation from {{ ref('share_partner__federation_report_card') }}
where records_affected > 0 and records_affected < {{ privacy_param('k_min') }}
