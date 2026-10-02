{{ config(tags=['phase2']) }}
-- Every input record is in exactly one cluster per matcher x stage x scope.
select c.matcher, c.stage, c.scope, c.match_record_id, count(*) as n
from {{ ref('idr_clusters') }} c group by 1, 2, 3, 4 having count(*) > 1
union all
select c.matcher, c.stage, c.scope, null, count(distinct c.match_record_id)
from {{ ref('idr_clusters') }} c group by 1, 2, 3
having count(distinct c.match_record_id) <> (select count(*) from {{ ref('idr_input_records') }})
