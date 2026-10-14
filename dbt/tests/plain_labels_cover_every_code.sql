{{ config(tags=['phase5']) }}
-- Phase 5.1: every code that can reach the site has a plain-language label (rules, purposes, dimensions, grades, sources, channels, club markets), within the length limits.
select 'rule_without_plain_text' as problem, rule_id as detail from {{ ref('dq_rule_registry') }}
where nullif(trim(plain_label), '') is null or nullif(trim(plain_action), '') is null
   or len(string_split(trim(plain_label), ' ')) > 6 or len(string_split(trim(plain_action), ' ')) > 15
union all
select 'purpose_without_plain_text', purpose from {{ ref('dq_purposes') }} where nullif(trim(plain_label), '') is null or nullif(trim(plain_question), '') is null
union all
select 'grade_without_plain_label', grade from {{ ref('dq_grade_bands') }} where nullif(trim(plain_label), '') is null
union all
select 'dimension_without_plain_label', d from (
    select distinct dimension as d from {{ ref('dq_rule_registry') }}
    union select distinct dimension from {{ ref('dq_scorecard_source') }}) u
where d not in (select dimension from {{ ref('dq_dimensions') }})
union all
select 'source_without_display_name', s from (
    select distinct source_system as s from {{ ref('dq_scorecard_source') }} union select distinct source_system from {{ ref('dq_scorecard_org') }}) u
where s not in (select source_system from {{ ref('source_display') }})
union all
select 'channel_without_display_name', c from (select distinct channel as c from {{ ref('dq_scorecard_org') }}) u
where c not in (select channel from {{ ref('channel_display') }})
union all
select 'market_without_plain_name', club_market_id from {{ ref('club_market_map') }} where nullif(trim(plain_name), '') is null
