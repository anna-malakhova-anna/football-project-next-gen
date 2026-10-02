-- RESTRICTED (schema `linkage`). Coarsened exact matching: strata are (country, event month, tenure band, pre-period engagement band). A stratum is
-- usable only if it has at least one treated household AND at least one comparison account. Every treated household in a usable stratum is matched;
-- comparison accounts in the stratum share the treated count: weight = treated in stratum / comparisons in stratum (so each stratum's comparison weights
-- add up to its treated count, and the comparison group has the treated group's mix of the matching variables).
-- A comparison account can appear in several strata (it is a candidate at every event month); that repetition is why the standard errors are approximate.
with c as (select * from {{ ref('int_fan_cem_candidates') }}),

strata as (

    select country_code, e, tenure_band, pre_band,
           count(*) filter (where is_treated)       as n_treated,
           count(*) filter (where not is_treated)   as n_comparison
    from c group by 1, 2, 3, 4

)

select
    c.account_id, c.household_id, c.is_treated, c.e, c.country_code, c.tenure_band, c.pre_band,
    c.pre_tenure_months, c.pre_events, c.pre_rate, c.post_months, c.post_events, c.post_rate,
    case when c.is_treated then 1.0 else s.n_treated * 1.0 / s.n_comparison end as weight,
    s.n_treated, s.n_comparison
from c
join strata s using (country_code, e, tenure_band, pre_band)
where s.n_treated > 0 and s.n_comparison > 0
