{{ config(tags=['phase2']) }}
-- A given_key / nickname_key pair appears once, and no name is mapped to itself.
select given_key, nickname_key, count(*) as n
from {{ ref('nickname_map') }}
group by 1, 2
having count(*) > 1 or given_key = nickname_key
