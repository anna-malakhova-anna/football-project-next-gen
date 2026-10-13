{{ config(tags=['phase5']) }}
-- Every rule has an id, a known dimension, SQL, a description, a fix text, thresholds in [0, 1], and applies to at least one purpose.
select rule_id
from {{ ref('p5_dq_rules') }}
where rule_id is null or nullif(trim(check_sql), '') is null or nullif(trim(description), '') is null or nullif(trim(fix_text), '') is null
   or coalesce(threshold_participation_reporting, threshold_club_activation) is null
   or threshold_participation_reporting not between 0 and 1 or threshold_club_activation not between 0 and 1
