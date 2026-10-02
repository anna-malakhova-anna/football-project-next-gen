{# Methodology versions are 'major.minor'. A KPI exists from `introduced_in` onwards (metric_catalog); comparing as numbers keeps '1.10' > '1.9'. #}
{% macro version_num(v) -%}
(cast(split_part({{ v }}, '.', 1) as integer) * 1000 + cast(split_part({{ v }}, '.', 2) as integer))
{%- endmacro %}

{# The market lookup key for a postal code: the ZIP3 of a US ZIP, or the FSA of a Canadian postal code, whichever the FORMAT says (a mover registered in one country may carry the
   other country's postal code). NULL for anything else, including international returns, which have no postal code and map to their country's market. #}
{% macro market_prefix(postal) -%}
case
    when regexp_matches(coalesce({{ postal }}, ''), '^\s*\d{5}') then left(regexp_replace({{ postal }}, '\D', '', 'g'), 3)
    when regexp_matches(upper(coalesce({{ postal }}, '')), '^\s*[A-Z]\d[A-Z]') then upper(left(regexp_replace({{ postal }}, '\s', '', 'g'), 3))
end
{%- endmacro %}

{# A named window from the fan_params seed (rework spec 4.2): no model hard-codes 90, 180 or 12. #}
{% macro fan_param(name) -%}
(select value from {{ ref('fan_params') }} where param = '{{ name }}')
{%- endmacro %}

{# Kaplan-Meier in SQL for any set of spells (rework spec 5.4, the pattern of mart_retention_survival as a macro).
   spells   a relation/CTE with the columns in `group_cols`, `t` (integer time >= 1 at which the spell ended) and `event` (boolean: the end was the event, not censoring)
   group_cols  list of columns that define the curves
   At each t: at_risk = spells with time >= t, events and censored at t, hazard = events / at_risk, survival = exp(sum(ln(1 - hazard))) (0 once everyone at risk has the event), Greenwood
   standard error and a 95% interval clipped to [0, 1]. Censoring leaves the risk set after t. #}
{% macro kaplan_meier(spells, group_cols) -%}
{%- set g = group_cols | join(', ') -%}
(
    with sp as (select * from {{ spells }}),
    ks as (select unnest(range(1, (select max(t) from sp) + 1)) as t),
    grp as (select distinct {{ g }} from sp),
    steps as (
        select {% for c in group_cols %}grp.{{ c }}, {% endfor %}ks.t,
               count(*) filter (where sp.t >= ks.t)                         as at_risk,
               count(*) filter (where sp.t = ks.t and sp.event)             as events,
               count(*) filter (where sp.t = ks.t and not sp.event)         as censored
        from grp cross join ks
        join sp on {% for c in group_cols %}sp.{{ c }} is not distinct from grp.{{ c }}{{ ' and ' if not loop.last }}{% endfor %}
        group by {% for c in group_cols %}grp.{{ c }}, {% endfor %}ks.t
    ),
    live as (select * from steps where at_risk > 0),
    km as (
        select *,
               events * 1.0 / at_risk                                        as hazard,
               bool_or(events >= at_risk) over w                             as reached_zero,
               sum(ln(greatest(1 - events * 1.0 / at_risk, 1e-12))) over w   as log_s,
               sum(case when at_risk > events then events * 1.0 / (at_risk * (at_risk - events)) else 0 end) over w as greenwood_sum
        from live
        window w as (partition by {{ g }} order by t)
    )
    select {{ g }}, t, at_risk, events, censored, round(hazard, 6) as hazard,
           round(case when reached_zero then 0 else exp(log_s) end, 6) as survival,
           round(case when reached_zero then 0 else exp(log_s) * sqrt(greenwood_sum) end, 6) as greenwood_se,
           round(greatest(0, (case when reached_zero then 0 else exp(log_s) end) - 1.96 * (case when reached_zero then 0 else exp(log_s) * sqrt(greenwood_sum) end)), 6) as ci_low,
           round(least(1, (case when reached_zero then 0 else exp(log_s) end) + 1.96 * (case when reached_zero then 0 else exp(log_s) * sqrt(greenwood_sum) end)), 6) as ci_high
    from km
)
{%- endmacro %}
