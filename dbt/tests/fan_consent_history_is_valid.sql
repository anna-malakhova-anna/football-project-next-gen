{{ config(tags=['phase4']) }}
-- Consent as an SCD2 per fan account x channel: no overlapping intervals, valid_from < valid_to (or open-ended), exactly one open interval per account x channel, consecutive intervals differ in
-- status, and no interval for an account that is not in the dimension. A channel with no line has no interval: not captured is never turned into FALSE.
select 'overlapping_intervals' as problem, a.fan_account_id || '|' || a.channel as detail
from {{ ref('fct_fan_consent_history') }} a
join {{ ref('fct_fan_consent_history') }} b
  on a.fan_account_id = b.fan_account_id and a.channel = b.channel and a.valid_from < b.valid_from and (a.valid_to is null or a.valid_to > b.valid_from)
union all
select 'valid_from_not_before_valid_to', fan_account_id || '|' || channel
from {{ ref('fct_fan_consent_history') }} where valid_to is not null and valid_from >= valid_to
union all
select 'not_exactly_one_open_interval', fan_account_id || '|' || channel
from {{ ref('fct_fan_consent_history') }} group by fan_account_id, channel having count(*) filter (where valid_to is null) <> 1
union all
select 'is_current_disagrees_with_open_interval', fan_account_id || '|' || channel
from {{ ref('fct_fan_consent_history') }} where is_current <> (valid_to is null)
union all
select 'same_status_twice_in_a_row', fan_account_id || '|' || channel
from (select *, lag(status) over (partition by fan_account_id, channel order by valid_from) as prev from {{ ref('fct_fan_consent_history') }}) where prev = status
union all
select 'history_for_an_account_not_in_the_dimension', fan_account_id
from {{ ref('fct_fan_consent_history') }} where fan_account_id not in (select fan_account_id from {{ ref('dim_fan_account') }})
union all
select 'status_not_opt_in_or_opt_out', fan_account_id || '|' || channel
from {{ ref('fct_fan_consent_history') }} where status not in ('opt_in', 'opt_out')
