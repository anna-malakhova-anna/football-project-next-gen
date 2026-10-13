-- Candidate pairs: union of the blocks, de-duplicated, ordered record_a < record_b, with the blocks that produced each pair.
select
    a.match_record_id as record_a,
    b.match_record_id as record_b,
    list_sort(list_distinct(list(a.block))) as blocks_hit
from {{ ref('p5_blocking_keys') }} a
join {{ ref('p5_blocking_keys') }} b
    on a.block = b.block and a.block_key = b.block_key and a.match_record_id < b.match_record_id
group by a.match_record_id, b.match_record_id
