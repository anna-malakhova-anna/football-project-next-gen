{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). Grades the Kaplan-Meier retention curves against the generator's true churn parameters, and shows what the
-- NAIVE version (an age-out counted as churn) would have reported instead. Synthetic data, labelled as such wherever it is shown.
--
-- true_survival   the curve the true parameters imply for exactly the players who were at risk: at each step the true hazard is the average, over the
--                 at-risk players, of the true churn probability for their age (zero for the few cross-border players, who never churn in the
--                 generator), and true_survival is the running product of (1 - true hazard). Using the observed at-risk set means the comparison
--                 isolates the estimator, not the mix of players.
-- naive_survival  the same Kaplan-Meier calculation where a player who turns 18 is counted as a churn event. Right censoring is still handled
--                 correctly in both, so the difference between the two columns is the age-out rule and nothing else.
-- truth_in_ci     the true curve lies inside the 95% interval of the KM estimate (about 95% of cells should, if the intervals are honest).
with s as (select * from {{ ref('retention_spells') }} where age_known),

true_person as (

    select b.participant_id, min(t.true_person_id) as true_person_id
    from {{ ref('fct_registration') }} r
    join {{ ref('eval_record_truth') }} t on t.match_record_id = r.registration_key
    join {{ ref('bridge_registration_participant') }} b on b.registration_key = r.registration_key
    group by 1

),

person as (

    select
        s.participant_id, s.entry_age, s.entry_sex, s.entry_age_band, s.entry_country, s.entry_multi_org, s.entry_division,
        s.duration_k, s.outcome,
        s.churned or (s.outcome = 'AGE_OUT' and s.duration_k + 1 <= s.max_k_observed)                 as naive_event,
        case when s.outcome = 'AGE_OUT' and s.duration_k + 1 <= s.max_k_observed then s.duration_k + 1 else s.duration_k end as naive_duration_k,
        coalesce(pr.is_cross_border, false)                                                           as is_cross_border
    from s
    left join true_person tp using (participant_id)
    left join {{ source('ground_truth', 'person_registry') }} pr on pr.true_person_id = tp.true_person_id

),

seg as (

    select 'ALL' as segment_type, 'ALL' as segment_value, * from person
    union all by name select 'sex' as segment_type, entry_sex as segment_value, * exclude (entry_sex) from person
    union all by name select 'entry_age_band' as segment_type, entry_age_band as segment_value, * exclude (entry_age_band) from person
    union all by name select 'entry_country' as segment_type, entry_country as segment_value, * exclude (entry_country) from person
    union all by name select 'multi_org_at_entry' as segment_type, case when entry_multi_org then 'MULTI_ORG' else 'SINGLE_ORG' end as segment_value, * exclude (entry_multi_org) from person
    union all by name select 'entry_division' as segment_type, entry_division as segment_value, * exclude (entry_division) from person

),

ks as (select unnest(range(1, (select last_observed_year - first_observed_year + 1 from {{ ref('observation_window') }}))) as k),

steps as (

    select
        g.segment_type, g.segment_value, ks.k,
        count(*) filter (where g.duration_k >= ks.k)                                               as at_risk,
        sum(case when g.duration_k >= ks.k and not g.is_cross_border then c.churn_p else 0 end)    as expected_events,
        count(*) filter (where g.naive_duration_k >= ks.k)                                         as naive_at_risk,
        count(*) filter (where g.naive_duration_k = ks.k and g.naive_event)                        as naive_events
    from seg g
    cross join ks
    left join {{ source('ground_truth', 'churn_truth') }} c on g.entry_age + ks.k between c.min_age and c.max_age
    group by 1, 2, 3

),

curves as (

    select
        *,
        exp(sum(ln(greatest(1 - expected_events / at_risk, 1e-12))) over w)                        as true_survival,
        case when bool_or(naive_events >= naive_at_risk) over w then 0
             else exp(sum(ln(greatest(1 - naive_events * 1.0 / naive_at_risk, 1e-12))) over w) end as naive_survival
    from steps
    where at_risk > 0
    window w as (partition by segment_type, segment_value order by k)

)

select
    km.segment_type,
    km.segment_value,
    km.years_since_entry,
    km.at_risk,
    km.survival                                                                                    as km_survival,
    km.ci_low                                                                                      as km_ci_low,
    km.ci_high                                                                                     as km_ci_high,
    round(c.true_survival, 6)                                                                      as true_survival,
    round(km.survival - c.true_survival, 6)                                                        as km_error,
    c.true_survival between km.ci_low and km.ci_high                                               as truth_in_ci,
    round(c.naive_survival, 6)                                                                     as naive_survival,
    round(c.naive_survival - c.true_survival, 6)                                                   as naive_error,
    round(km.survival - c.naive_survival, 6)                                                       as naive_understates_by,
    km.reliable
from {{ ref('mart_retention_survival') }} km
join curves c on c.segment_type = km.segment_type and c.segment_value = km.segment_value and c.k = km.years_since_entry
order by km.segment_type, km.segment_value, km.years_since_entry
