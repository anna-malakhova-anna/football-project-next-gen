-- u = P(feature level | two RANDOM, NON-MATCHING records), estimated from the data with no labels.
-- Sample about 200,000 record pairs from ALL possible pairs (not from blocks) with a deterministic hash filter,
-- compute the same feature levels as for candidate pairs, and count.
-- Assumption: a random pair is almost surely a non-match (about 15,000 true pairs among 97.5 million), so
-- the level frequencies of random pairs estimate u. Smoothing: (count + 0.5) / (n + 0.5 * levels), so a level
-- never seen in the sample still gets a small positive u instead of an infinite weight.
-- DuckDB: hash(); Snowflake has HASH() too (a signed number; take ABS before the modulus).
with pairs as (

    select
        a.match_record_id as record_a,
        b.match_record_id as record_b,
        cast(null as varchar[]) as blocks_hit,
        {{ pair_attributes() }}
    from {{ ref('idr_input_records') }} a
    join {{ ref('idr_input_records') }} b on a.match_record_id < b.match_record_id
    where hash(a.match_record_id || '|' || b.match_record_id) % {{ var('idr_u_sample_modulus') }} = 0

),

{{ pair_level_ctes() }},

long as (

    select 'first_name' as feature, first_name_level as level from levels
    union all select 'last_name', last_name_level from levels
    union all select 'dob', dob_level from levels
    union all select 'email', email_level from levels
    union all select 'phone', phone_level from levels
    union all select 'postal', postal_level from levels
    union all select 'sex', sex_level from levels
    union all select 'context', context_level from levels

),

counts as (select feature, level, count(*) as n from long group by 1, 2),

sample as (select count(*) as sampled_pairs from levels),

levels_per_feature as (select feature, count(*) as n_levels from {{ ref('match_m_probabilities') }} group by 1)

select
    m.feature,
    m.level,
    coalesce(c.n, 0)                                                        as sample_count,
    s.sampled_pairs,
    (coalesce(c.n, 0) + 0.5) / (s.sampled_pairs + 0.5 * l.n_levels)         as u_probability
from {{ ref('match_m_probabilities') }} m
cross join sample s
join levels_per_feature l on l.feature = m.feature
left join counts c on c.feature = m.feature and c.level = m.level
