-- RESTRICTED (schema `linkage`). The link rate and how it is made up. Counts only. The denominator is the program's households: a household with
-- no fan account (or an account under a different email) is unlinked, and the unlinked are not a random sample (see linkage_link_bias).
with links as (select * from {{ ref('link_household_fan_account') }} where link_status = 'LINKED'),

h as (select count(*) as households, count(*) filter (where not is_adult_household) as family_households, count(*) filter (where is_adult_household) as adult_households from {{ ref('int_household_profile') }})

select 'households' as measure, 'ALL' as detail, households as n, cast(null as double) as share from h
union all select 'households', 'FAMILY', family_households, null from h
union all select 'households', 'ADULT_PLAYER', adult_households, null from h
union all select 'linked_households', 'ALL', count(*), count(*) * 1.0 / (select households from h) from links
union all select 'linked_households', method, n, n * 1.0 / (select households from h)
from (select link_method as method, count(*) as n from links group by 1)
union all select 'ambiguous_candidates', link_method, count(*), null from {{ ref('link_household_fan_account') }} where link_status = 'AMBIGUOUS' group by link_method
union all select 'accounts', 'ALL', count(*), null from {{ ref('stg_fan_accounts') }}
union all select 'accounts_linked', 'ALL', count(distinct account_id), count(distinct account_id) * 1.0 / (select count(*) from {{ ref('stg_fan_accounts') }}) from links
