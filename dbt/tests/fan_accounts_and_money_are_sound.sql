{{ config(tags=['phase4']) }}
-- Guardians only: every fan account holder is an adult at signup. One dimension row per household after the collapse, and every account maps to a dimension row. Transactions net of refunds:
-- orphan refunds are excluded from revenue AND counted in the DQ log (the same number), and the net total equals purchases minus matched refunds. Engagement keeps (almost) every distinct event.
select 'holder_is_a_minor_at_signup' as problem, fan_account_id as detail from {{ ref('dim_fan_account') }} where holder_age_at_signup < 18 or holder_age_at_signup is null
union all
select 'account_without_a_dimension_row', account_id from {{ ref('int_fan_account_xref') }} where fan_account_id not in (select fan_account_id from {{ ref('dim_fan_account') }})
union all
select 'dimension_row_count_differs_from_households', cast(d as varchar) || ' vs ' || cast(x as varchar)
from (select (select count(*) from {{ ref('dim_fan_account') }}) as d, (select count(distinct fan_account_id) from {{ ref('int_fan_account_xref') }}) as x) where d <> x
union all
select 'orphan_refund_counted_in_revenue', txn_id from {{ ref('fct_fan_transaction') }} where is_orphan_refund and (is_in_net or signed_amount <> 0)
union all
select 'orphan_refunds_differ_from_the_dq_log', cast(f as varchar) || ' vs ' || cast(l as varchar)
from (select (select count(*) from {{ ref('fct_fan_transaction') }} where is_orphan_refund) as f,
             (select count(*) from {{ ref('dq_defect_log') }} where source_system = 'FAN_ENGAGEMENT' and flag = 'refund_without_original') as l) where f <> l
union all
select 'net_total_differs_from_purchases_minus_matched_refunds', cast(net as varchar) || ' vs ' || cast(chk as varchar)
from (select (select sum(signed_amount) from {{ ref('fct_fan_transaction') }} where is_in_net) as net,
             (select sum(case when is_refund then -amount else amount end) from {{ ref('fct_fan_transaction') }} where is_in_net) as chk)
where abs(net - chk) > 0.01
union all
select 'too_many_events_lost', cast(lost as varchar)
from (select (select count(*) from {{ ref('stg_fan_events') }} where not is_duplicate) - (select sum(events) from {{ ref('fct_fan_engagement_month') }}) as lost,
             (select count(*) from {{ ref('stg_fan_events') }} where not is_duplicate) as total)
where lost > 0.0001 * total or lost < 0
union all
select 'account_month_twice', fan_account_id || '|' || cast(event_month as varchar)
from {{ ref('fct_fan_engagement_month') }} group by fan_account_id, event_month having count(*) > 1
