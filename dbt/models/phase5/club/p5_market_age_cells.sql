{{ config(schema='phase5') }}
-- AGGREGATE input to the age-band view: observed, placed children per market and age band in the latest season, plus a market total row (age_band NULL). Counts only; unplaced
-- children are not here (they have no market). Suppression is applied in the club view.
select market_id, age_band, count(*) as children
from {{ ref('p5_child') }} where market_id <> 'UNPLACED' group by 1, 2
union all
select market_id, cast(null as varchar), count(*)
from {{ ref('p5_child') }} where market_id <> 'UNPLACED' group by 1
