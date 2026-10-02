-- GROUND TRUTH (evaluation only). Does blocking keep the true pairs? If completeness is low, no scoring can
-- fix it. Long format: section / name / value / detail.
--   overall      pair completeness (true pairs found by blocking or by a deterministic link), reduction ratio
--   by_block     for each block: true pairs it finds, and true pairs only that block finds (could it be dropped?)
--   largest_keys the biggest block keys; any key above 500 records is too weak and is flagged
with n as (select count(*) as records from {{ ref('idr_input_records') }}),

tp as (select * from {{ ref('eval_truth_pairs') }}),

hit as (

    select tp.record_a, tp.record_b, tp.is_deterministic, c.blocks_hit
    from tp
    left join {{ ref('idr_candidate_pairs') }} c on c.record_a = tp.record_a and c.record_b = tp.record_b

),

overall as (

    select 'overall' as section, 'true_pairs' as name, count(*)::double as value, 'all true pairs among input records' as detail from tp
    union all
    select 'overall', 'true_pairs_deterministic', count(*) filter (where is_deterministic), 'linked by a source id; never scored'
    from tp
    union all
    select 'overall', 'true_pairs_in_candidates', count(*) filter (where blocks_hit is not null), 'found by blocking' from hit
    union all
    select 'overall', 'true_pairs_missed_by_blocking',
           count(*) filter (where blocks_hit is null and not is_deterministic), 'neither blocked nor deterministic' from hit
    union all
    select 'overall', 'pair_completeness',
           (count(*) filter (where blocks_hit is not null or is_deterministic)) * 1.0 / count(*),
           'true pairs found by blocking or a deterministic link / all true pairs' from hit
    union all
    select 'overall', 'pair_completeness_scored_pairs',
           (count(*) filter (where blocks_hit is not null)) * 1.0 / nullif(count(*) filter (where not is_deterministic), 0),
           'true non-deterministic pairs found by blocking / all true non-deterministic pairs' from hit
    union all
    select 'overall', 'candidate_pairs', count(*), 'pairs the matchers must score' from {{ ref('idr_candidate_pairs') }}
    union all
    select 'overall', 'possible_pairs', records * (records - 1) / 2.0, 'n(n-1)/2' from n
    union all
    select 'overall', 'reduction_ratio',
           1 - (select count(*) from {{ ref('idr_candidate_pairs') }}) / (records * (records - 1) / 2.0),
           '1 - candidate pairs / possible pairs' from n

),

by_block as (

    select 'by_block', b.block, count(*) filter (where list_contains(h.blocks_hit, b.block))::double,
           'true pairs found by this block' as detail
    from hit h cross join (select unnest(['B1', 'B2', 'B3', 'B4', 'B5']) as block) b
    group by b.block
    union all
    select 'by_block_unique', b.block,
           count(*) filter (where list_contains(h.blocks_hit, b.block) and len(h.blocks_hit) = 1)::double,
           'true pairs found ONLY by this block (drop it and these are lost)'
    from hit h cross join (select unnest(['B1', 'B2', 'B3', 'B4', 'B5']) as block) b
    group by b.block

),

sizes as (

    select block, block_key, count(*) as size
    from {{ ref('idr_blocking_keys') }}
    group by 1, 2

),

largest as (

    select 'largest_keys' as section, block || ' ' || block_key as name, size::double as value,
           case when size > 500 then 'TOO WEAK: more than 500 records' else 'ok' end as detail
    from sizes
    qualify row_number() over (order by size desc, block, block_key) <= 10

),

block_summary as (

    select 'block_size' as section, block as name, max(size)::double as value,
           'largest key in this block; keys above 500: ' || count(*) filter (where size > 500) as detail
    from sizes group by block

)

select * from overall
union all select * from by_block
union all select * from block_summary
union all select * from largest
