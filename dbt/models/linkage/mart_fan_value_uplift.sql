-- RESTRICTED (schema `linkage`; aggregates only). VALUE UPLIFT AMONG EXISTING FANS (rework spec 5.3): the matched difference-in-differences of the Phase 4 fan analysis, scoped to participant
-- households that already had a fan account (status EXISTING_* or LAPSED_*, grouped as EXISTING and LAPSED; net-new fans have no pre-period), for each engagement type and each spend category.
-- Spend is NET of refunds, SYNTHETIC CURRENCY. For each outcome and status group:
--   did_per_month      (post - pre for the matched participants) - (post - pre for their weighted matched comparisons), in the outcome's unit per account-month
--   did_pct            did_per_month as a share of the participants' counterfactual post level (post mean - did): the relative uplift. se is analytic (household-level changes), 95% = +/- 1.96 se
--   naive_pct          the UNMATCHED comparison on the same eligible households and windows: participants' post level over ALL comparison accounts' post level, minus one
-- READ THE PERCENTAGE ONLY WHERE `pct_is_stable`: for LAPSED households the counterfactual level is near zero (nothing to be relative to), so the percentage explodes or flips sign; the per-month
-- difference (did_per_month, with its interval) is the honest number there. content_views and flag_content_views move in opposite directions because a share of an enrolled household's content
-- views are RELABELLED flag_content_view, not added: all_content_views is the two together.
-- Matching, weights and windows are int_fan_cem_matched's (country, event month, tenure band, pre-period engagement band; 12 months before, 12 after). Within a status group the comparison weights
-- are rescaled to that group's treated households per stratum. The comparison group includes some participant households we could not link (contamination, measured in the evaluation).
{% set outcomes = [('events', 'engagement'), ('app_opens', 'engagement'), ('content_views', 'engagement'), ('all_content_views', 'engagement'), ('game_streams', 'engagement'), ('newsletter_clicks', 'engagement'),
                   ('fantasy_activities', 'engagement'), ('flag_content_views', 'engagement'), ('net_spend_ticket', 'spend'), ('net_spend_merch', 'spend'),
                   ('net_spend_subscription', 'spend'), ('net_spend_other', 'spend'), ('net_spend_total', 'spend')] %}
with cand as (select account_id, e, is_treated from {{ ref('int_fan_cem_candidates') }}),

unit as (

    select
        c.account_id, c.e, c.is_treated,
        {% for o, _ in outcomes %}
        avg(f.{{ o }}) filter (where f.event_month < c.e)  as pre_{{ o }},
        avg(f.{{ o }}) filter (where f.event_month >= c.e) as post_{{ o }}{{ ',' if not loop.last }}
        {% endfor %}
    from cand c
    join {{ ref('int_fan_outcome_month') }} f
      on f.fan_account_id = c.account_id and f.event_month >= c.e - to_months({{ var('fan_pre_months') }}) and f.event_month < c.e + to_months({{ var('fan_post_months') }})
    group by 1, 2, 3

),

grp as (

    select s.household_id, t.account_id, case when s.fan_status in ('EXISTING_ACTIVE', 'EXISTING_COOLING') then 'EXISTING' else 'LAPSED' end as status_group
    from {{ ref('fct_household_fan_status') }} s
    join {{ ref('int_participant_household_timeline') }} t using (household_id)
    where t.is_linked

),

mt as (

    select m.account_id, m.e, m.is_treated, m.country_code, m.tenure_band, m.pre_band, m.n_comparison, g.status_group
    from {{ ref('int_fan_cem_matched') }} m left join grp g on g.account_id = m.account_id and m.is_treated
),

strata as (

    select country_code, e, tenure_band, pre_band, status_group, count(*) as n_treated_group
    from mt where is_treated group by 1, 2, 3, 4, 5

),

weights as (

    -- one row per (pair, group): treated pairs weigh 1 in their own group and in ALL; comparison pairs weigh (treated of the group in the stratum) / (comparisons in the stratum)
    select m.account_id, m.e, m.is_treated, st.status_group as grp, case when m.is_treated then 1.0 else st.n_treated_group * 1.0 / m.n_comparison end as weight
    from mt m join strata st using (country_code, e, tenure_band, pre_band) where (m.is_treated and m.status_group = st.status_group) or not m.is_treated
    union all
    select m.account_id, m.e, m.is_treated, 'ALL', case when m.is_treated then 1.0 else (select sum(n_treated_group) from strata s2 where s2.country_code = m.country_code and s2.e = m.e and s2.tenure_band = m.tenure_band and s2.pre_band = m.pre_band) * 1.0 / m.n_comparison end
    from mt m

),

long as (

    {% for o, kind in outcomes %}
    select '{{ o }}' as outcome, '{{ kind }}' as outcome_kind, u.account_id, u.e, u.is_treated, u.pre_{{ o }} as pre, u.post_{{ o }} as post from unit u
    {{ 'union all' if not loop.last }}
    {% endfor %}

),

joined as (

    select w.grp as status_group, l.outcome, l.outcome_kind, l.is_treated, w.weight, l.pre, l.post, l.post - l.pre as d
    from weights w join long l on l.account_id = w.account_id and l.e = w.e and l.is_treated = w.is_treated
    where l.pre is not null and l.post is not null

),

t as (select status_group, outcome, outcome_kind, count(*) as n_treated, avg(d) as mean_d, var_samp(d) / count(*) as var_mean, avg(pre) as pre, avg(post) as post from joined where is_treated group by 1, 2, 3),

c as (

    select status_group, outcome, count(*) as pairs, sum(weight * d) / sum(weight) as mean_d, sum(weight * post) / sum(weight) as post, power(sum(weight), 2) / sum(weight * weight) as n_eff
    from joined where not is_treated group by 1, 2

),

c2 as (

    select j.status_group, j.outcome, sum(j.weight * j.weight * power(j.d - c.mean_d, 2)) / power(sum(j.weight), 2) as var_mean
    from joined j join c using (status_group, outcome) where not j.is_treated group by 1, 2

),

naive as (

    -- the UNMATCHED comparison: every eligible comparison account, no weights (the status-group split does not apply to the comparison, so it is the same in each group)
    select outcome, avg(post) as control_post from (select l.outcome, l.post from long l where not l.is_treated and l.post is not null) group by 1

)

select
    t.status_group,
    t.outcome,
    t.outcome_kind,
    t.n_treated                                                             as treated_households,
    c.pairs                                                                 as comparison_pairs,
    round(t.pre, 4)                                                         as treated_pre_mean,
    round(t.post, 4)                                                        as treated_post_mean,
    round(t.mean_d - c.mean_d, 5)                                           as did_per_month,
    round(sqrt(t.var_mean + c2.var_mean), 5)                                as se_per_month,
    round(t.mean_d - c.mean_d - 1.96 * sqrt(t.var_mean + c2.var_mean), 5)   as did_ci_low_per_month,
    round(t.mean_d - c.mean_d + 1.96 * sqrt(t.var_mean + c2.var_mean), 5)   as did_ci_high_per_month,
    round(t.post - (t.mean_d - c.mean_d), 5)                                as counterfactual_post_mean,
    (t.post - (t.mean_d - c.mean_d)) >= 0.2 * t.post                        as pct_is_stable,
    round((t.mean_d - c.mean_d) / nullif(t.post - (t.mean_d - c.mean_d), 0), 5) as did_pct,
    round((t.mean_d - c.mean_d - 1.96 * sqrt(t.var_mean + c2.var_mean)) / nullif(t.post - (t.mean_d - c.mean_d), 0), 5) as did_ci_low_pct,
    round((t.mean_d - c.mean_d + 1.96 * sqrt(t.var_mean + c2.var_mean)) / nullif(t.post - (t.mean_d - c.mean_d), 0), 5) as did_ci_high_pct,
    round(t.post / nullif(n.control_post, 0) - 1, 5)                        as naive_pct,
    '{{ var("methodology_version") }}'                                      as methodology_version
from t join c using (status_group, outcome) join c2 using (status_group, outcome) join naive n using (outcome)
order by t.status_group, t.outcome_kind, t.outcome
