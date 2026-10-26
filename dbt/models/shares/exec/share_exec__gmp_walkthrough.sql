{{ config(tags=['phase7']) }}
-- EXEC share (DP6 port global_walkthroughs, spec section 10): the onboarding walkthroughs of Canada (a market with a signal) and Italy (no signal),
-- one row per playbook stage (Discovery to Production) with its state (DONE, EXPERIMENT on a copy of the warehouse, NOT_STARTED), the artifact, and
-- what happened. Each row also carries the market's LIVE status and counting grade from the published build, so the timeline never restates a number.
select
    w.country_code, m.country_name, w.stage_order, w.stage, w.state, w.artifact, w.what_happened,
    s.status                                                                as market_status_now,
    s.counting_grade                                                        as counting_grade_now
from {{ ref('gmp_walkthrough_stages') }} w
join {{ ref('gmp_markets') }} m using (country_code)
join {{ ref('mart_gmp_market_status') }} s using (country_code)
order by w.country_code, w.stage_order
