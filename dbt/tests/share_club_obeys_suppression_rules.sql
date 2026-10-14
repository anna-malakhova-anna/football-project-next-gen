{{ config(tags=['phase5']) }}
-- Independent of the suppression macro: what reaches a club is aggregate, small cells are hidden together with everything derived from them, and no hidden cell can be recovered by subtraction from a published subtotal.
{% set k = privacy_param('k_min') %}
select 'published_count_below_k_min' as problem, cast(club_market_id as varchar) || ' ' || cast(participation_year as varchar) as detail
from {{ ref('share_club__market_year') }} where suppressed = 'NONE' and participants_allocated < {{ k }}
union all
select 'suppressed_row_still_shows_derived_values', cast(club_market_id as varchar) || ' ' || cast(participation_year as varchar)
from {{ ref('share_club__market_year') }}
where suppressed <> 'NONE' and (grade_count is not null or grade_geo is not null or participants_not_reported_estimate is not null or participants_allocated_interval_low is not null or pct_records_geo_fit is not null or orgs_known is not null)
union all
select 'single_hidden_market_beside_a_published_total', cast(y.participation_year as varchar)
from (select participation_year, count(*) filter (where suppressed <> 'NONE' and club_market_id is not null) as hidden,
             count(*) filter (where suppressed <> 'SECONDARY' and club_market_id is not null and suppressed <> 'NONE') as primary_hidden,
             count(*) filter (where suppressed = 'SECONDARY') as secondary_hidden,
             bool_or(club_market_id is null and suppressed = 'NONE') as total_published
      from {{ ref('share_club__market_year') }} group by 1) y
where y.total_published and y.primary_hidden = 1 and y.secondary_hidden = 0
union all
select 'missingness_cell_below_k_min_published', cast(club_market_id as varchar) || ' ' || cast(participation_year as varchar)
from {{ ref('share_club__market_missingness') }} where suppressed = 'NONE' and youth_participants_in_cell < {{ k }}
union all
select 'funnel_step_below_k_min_published', cast(club_market_id as varchar) || ' ' || cast(participation_year as varchar) || ' step ' || cast(step_no as varchar)
from {{ ref('share_club__activation_funnel') }} where suppressed = 'NONE' and funnel_count < {{ k }}
union all
select 'funnel_loss_shown_for_a_hidden_step', cast(club_market_id as varchar) || ' ' || cast(participation_year as varchar) || ' step ' || cast(step_no as varchar)
from {{ ref('share_club__activation_funnel') }} where suppressed <> 'NONE' and (funnel_count is not null or funnel_lost_dq is not null or funnel_lost_privacy is not null)
union all
select 'row_key_column_in_club_or_privacy_share', table_schema || '.' || table_name || '.' || column_name
from information_schema.columns
where table_schema in ('share_club', 'share_privacy')
  and regexp_matches(column_name, '(participant|household|registration|account|child|person|record).*(id|key)$|email|phone|first_name|last_name|dob|postal')
