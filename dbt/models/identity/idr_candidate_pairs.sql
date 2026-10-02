-- Candidate pairs: the union of all blocks, de-duplicated, always ordered record_a < record_b, with the
-- blocks that produced each pair. Pairs already linked deterministically are excluded.
with pairs as (

    select a.match_record_id as record_a, b.match_record_id as record_b, a.block
    from {{ ref('idr_blocking_keys') }} a
    join {{ ref('idr_blocking_keys') }} b
        on a.block = b.block and a.block_key = b.block_key and a.match_record_id < b.match_record_id

)

select
    p.record_a,
    p.record_b,
    list_sort(list_distinct(list(p.block)))                                 as blocks_hit
from pairs p
left join {{ ref('idr_deterministic_links') }} d
    on d.record_a = p.record_a and d.record_b = p.record_b
where d.record_a is null
group by p.record_a, p.record_b
