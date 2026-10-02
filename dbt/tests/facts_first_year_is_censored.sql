{{ config(tags=['phase3']) }}
-- The censoring rule (C11): the first year of data is left-censored, so no first-year participant may be NEW or
-- RETURNING (or REACTIVATED), and no later participant may be CENSORED. Applies to the annual and the US seasonal view.
select 'annual' as view, participant_id, participation_year, status
from {{ ref('fct_participant_year') }}
where (participation_year = (select min(participation_year) from {{ ref('fct_participant_year') }}) and status <> 'CENSORED')
   or (participation_year > (select min(participation_year) from {{ ref('fct_participant_year') }}) and status = 'CENSORED')
union all
select 'us_season', participant_id, participation_year, status
from {{ ref('fct_participant_us_season') }}
where (participation_year = (select min(participation_year) from {{ ref('fct_participant_us_season') }}) and status <> 'CENSORED')
   or (participation_year > (select min(participation_year) from {{ ref('fct_participant_us_season') }}) and status = 'CENSORED')
