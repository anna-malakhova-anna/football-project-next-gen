{{ config(tags=['phase5']) }}
-- A league (or market) is fit for a purpose exactly when no rule with a threshold for that purpose is below it. Re-derived here from the rule results.
with league as (

    select
        league_group,
        count(*) filter (where threshold_participation_reporting is not null and pass_rate < threshold_participation_reporting) = 0 as rep_ok,
        count(*) filter (where threshold_club_activation is not null and pass_rate < threshold_club_activation) = 0 as act_ok
    from {{ ref('dq_rule_results_league') }}
    group by 1

),

market as (

    select
        market_id,
        count(*) filter (where threshold_participation_reporting is not null and pass_rate < threshold_participation_reporting) = 0 as rep_ok,
        count(*) filter (where threshold_club_activation is not null and pass_rate < threshold_club_activation) = 0 as act_ok
    from {{ ref('dq_rule_results_market') }}
    group by 1

)

select s.league_group as id from {{ ref('dq_score_league') }} s join league l using (league_group)
where s.fit_for_participation_reporting <> l.rep_ok or s.fit_for_club_activation <> l.act_ok
union all
select s.market_id from {{ ref('dq_score_market') }} s join market l using (market_id)
where s.fit_for_participation_reporting <> l.rep_ok or s.fit_for_club_activation <> l.act_ok
