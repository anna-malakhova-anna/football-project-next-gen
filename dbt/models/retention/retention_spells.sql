-- One row per ENTRY: a participant's first observed participation year, as a survival record. Everything in the retention marts is built from
-- this table, so the censoring rules live in exactly one place.
--
--   entry cohort   first observed year, excluding the first data year (everyone active then may have started earlier: left-censored)
--   step k         the k-th year after entry; a player is "retained at k" if they have a valid registration in entry_year + k
--   event          the FIRST gap: no registration at entry_year + k while still youth-eligible and observable. Reactivation (a later return)
--                  is reported elsewhere (status = REACTIVATED); here the first gap is the event
--   age-out        age at December 31 above the youth maximum (17) means the player has left the youth programs, not the game: CENSORED, not churned
--   right censor   steps after the last observed year are unknown follow-up: CENSORED
-- duration = the last step at which the player was observable and eligible; censor_reason says why follow-up stopped when there was no event.
{% set youth_max = privacy_param('youth_max_age') %}
with p as (

    select participant_id, participation_year, age_at_cutoff, age_band, sex, attributed_country_code, is_multi_org, primary_division
    from {{ ref('fct_participant_year') }}

),

bounds as (select first_observed_year as first_year, last_observed_year as last_year from {{ ref('observation_window') }}),

entry as (

    select participant_id, min(participation_year) as entry_year from p group by 1

),

e as (

    select
        p.participant_id,
        en.entry_year,
        p.age_at_cutoff                                                     as entry_age,
        p.age_band                                                          as entry_age_band,
        p.sex                                                               as entry_sex,
        p.attributed_country_code                                           as entry_country,
        p.is_multi_org                                                      as entry_multi_org,
        p.primary_division                                                  as entry_division,
        b.last_year - en.entry_year                                         as max_k_observed
    from p
    join entry en on en.participant_id = p.participant_id and en.entry_year = p.participation_year
    cross join bounds b
    where en.entry_year > b.first_year

),

ks as (select unnest(range(1, (select last_year - first_year + 1 from bounds))) as k),

first_gap as (

    select e.participant_id, min(ks.k) as first_gap_k
    from e
    join ks on e.entry_year + ks.k <= (select last_year from bounds)
    where not exists (select 1 from p where p.participant_id = e.participant_id and p.participation_year = e.entry_year + ks.k)
    group by 1

),

limits as (

    select
        e.*,
        g.first_gap_k,
        -- last observable step before leaving youth age: an entrant aged a is youth through step ({{ youth_max }} - a); adults never age out
        case when e.entry_age <= {{ youth_max }} then {{ youth_max }} - e.entry_age end                      as youth_limit_k,
        least(e.max_k_observed, coalesce(case when e.entry_age <= {{ youth_max }} then {{ youth_max }} - e.entry_age end, 1000)) as follow_up_k
    from e left join first_gap g using (participant_id)

)

select
    participant_id,
    entry_year,
    entry_age,
    entry_age_band,
    entry_sex,
    entry_country,
    entry_multi_org,
    entry_division,
    max_k_observed,
    youth_limit_k,
    entry_age is not null                                                   as age_known,
    coalesce(first_gap_k <= follow_up_k, false)                             as churned,
    case when first_gap_k <= follow_up_k then first_gap_k else follow_up_k end as duration_k,
    case
        when first_gap_k <= follow_up_k then 'CHURNED'
        when youth_limit_k is not null and youth_limit_k <= max_k_observed then 'AGE_OUT'
        else 'FINAL_YEAR'
    end                                                                     as outcome
from limits
