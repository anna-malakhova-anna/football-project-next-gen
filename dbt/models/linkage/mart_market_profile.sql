-- RESTRICTED (schema `linkage`; one row per synthetic market, counts and rates only). THE MARKET PROFILE and QUADRANTS (rework spec 5.6). All households are the market's SYNTHETIC household population,
-- the fan accounts and participants are what the data holds.
--   participation_per_1000   participant households per 1,000 households in the market
--   fan_accounts_per_1000    fan accounts (duplicates collapsed) per 1,000 households
--   net_new_rate             NET_NEW households / participant households (linked or not: UNLINKED households are in the denominator, never dropped)
--   girls_share              girls' share of the children in the market's youth households
--   consent_capture_rate     share of the market's fan accounts with at least one channel opted in now (guardian accounts)
-- QUADRANT: FLAG_STRONG / FLAG_WEAK by participation_per_1000, FAN_STRONG / FAN_THIN by fan_accounts_per_1000, against thresholds from market_quadrant_params (blank = the median over launched
-- markets for participation, over all markets for fan accounts). Flag strong + fan thin = ACQUISITION WHITE SPACE; strong + strong = RETENTION AND ENGAGEMENT PLAY; weak + strong = PROGRAM GROWTH
-- OPPORTUNITY; weak + thin = LONG-TERM BUILD. A market where the programme launched but has fewer than min_participant_households participant households is UNCLASSIFIED (too small to read).
-- Markets are synthetic: their names, sizes and launch years are invented.
with m as (select * from {{ ref('market_map') }}),

p as (select * from {{ ref('market_quadrant_params') }}),

hh as (

    select market_id, count(*) as participant_households, sum(participants) as participants, count(*) filter (where not is_adult_household) as youth_households
    from {{ ref('int_household_profile') }} where market_id is not null group by 1

),

girls as (

    select hp.market_id, count(*) filter (where d.sex = 'F') as girls, count(*) as children
    from {{ ref('int_household_profile') }} hp
    join {{ ref('int_household') }} h on h.household_id = hp.household_id
    join {{ ref('dim_participant') }} d on d.participant_id = h.participant_id
    where not hp.is_adult_household and hp.market_id is not null group by 1

),

st as (

    select hp.market_id, count(*) filter (where s.fan_status = 'NET_NEW') as net_new_households, count(*) filter (where s.fan_status <> 'UNLINKED') as linked_households
    from {{ ref('fct_household_fan_status') }} s join {{ ref('int_household_profile') }} hp using (household_id) where hp.market_id is not null group by 1

),

fan as (select market_id, count(*) as fan_accounts from {{ ref('dim_fan_account') }} where market_id is not null group by 1),

consented as (

    select d.market_id, count(distinct d.fan_account_id) as accounts_with_consent
    from {{ ref('dim_fan_account') }} d join {{ ref('fct_fan_consent_history') }} c on c.fan_account_id = d.fan_account_id and c.status = 'opt_in' and c.valid_to is null
    where d.market_id is not null group by 1

),

base as (

    select
        m.market_id, m.market_name, m.country_code, m.region_code, m.is_team_market = 'Y' as is_team_market, m.launch_year, m.household_population,
        coalesce(hh.participant_households, 0) as participant_households, coalesce(hh.participants, 0) as participants,
        coalesce(fan.fan_accounts, 0) as fan_accounts,
        coalesce(st.net_new_households, 0) as net_new_households, coalesce(st.linked_households, 0) as linked_households,
        g.girls, g.children,
        coalesce(c.accounts_with_consent, 0) as accounts_with_consent
    from m
    left join hh using (market_id) left join girls g using (market_id) left join st using (market_id) left join fan using (market_id) left join consented c using (market_id)

),

rates as (

    select *,
           participant_households * 1000.0 / household_population as participation_per_1000,
           fan_accounts * 1000.0 / household_population as fan_accounts_per_1000
    from base

),

thr as (

    select
        coalesce((select value from p where param = 'participation_per_1000_threshold'), (select median(participation_per_1000) from rates where launch_year is not null)) as participation_threshold,
        coalesce((select value from p where param = 'fan_accounts_per_1000_threshold'), (select median(fan_accounts_per_1000) from rates)) as fan_threshold,
        (select value from p where param = 'min_participant_households_to_classify') as min_households

)

select
    r.market_id, r.market_name, r.country_code, r.region_code, r.is_team_market, r.launch_year, r.household_population,
    r.participant_households, r.participants, r.fan_accounts, r.linked_households, r.net_new_households,
    round(r.participation_per_1000, 3)                                      as participation_per_1000,
    round(r.fan_accounts_per_1000, 3)                                       as fan_accounts_per_1000,
    round(r.net_new_households * 1.0 / nullif(r.participant_households, 0), 4) as net_new_rate,
    round(r.linked_households * 1.0 / nullif(r.participant_households, 0), 4)  as link_rate,
    round(r.girls * 1.0 / nullif(r.children, 0), 4)                         as girls_share,
    round(r.accounts_with_consent * 1.0 / nullif(r.fan_accounts, 0), 4)     as consent_capture_rate,
    round(t.participation_threshold, 3)                                     as participation_threshold,
    round(t.fan_threshold, 3)                                               as fan_threshold,
    case
        when r.launch_year is not null and r.participant_households < t.min_households then 'UNCLASSIFIED'
        when r.participation_per_1000 >= t.participation_threshold and r.fan_accounts_per_1000 < t.fan_threshold  then 'Acquisition white space'
        when r.participation_per_1000 >= t.participation_threshold and r.fan_accounts_per_1000 >= t.fan_threshold then 'Retention and engagement play'
        when r.participation_per_1000 <  t.participation_threshold and r.fan_accounts_per_1000 >= t.fan_threshold then 'Program growth opportunity'
        else 'Long-term build'
    end                                                                     as quadrant,
    '{{ var("methodology_version") }}'                                      as methodology_version
from rates r cross join thr t
order by r.market_id
