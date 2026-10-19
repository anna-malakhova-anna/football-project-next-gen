-- DP2. The record-level quality facts of the in-scope (flag) feed records that need the RESOLVED CHILD: which record is the first of the child's season (uniqueness) and whether the child's records
-- agree on date of birth, sex, ZIP3 and age group (consistency; NULL = nothing to compare). Keyed by (feed, source_record_id). p5_record_quality joins these to DP1's p5_record_facts.
with survivor_person as (

    select i.content_hash, c.p5_person_id
    from {{ ref('p5_idr_input_records') }} i
    join {{ ref('p5_clusters') }} c using (match_record_id)

),

base as (

    select
        s.*,
        sp.p5_person_id,
        left(s.postal_code, 3)                                              as zip3
    from {{ ref('stg_p5_registrations') }} s
    left join survivor_person sp on sp.content_hash = s.content_hash
    where s.is_flag

),

placed as (

    select
        b.*,
        g.market_id                                                         as zip_market_id
    from base b
    left join {{ ref('market_geo_map') }} g on g.country_code = 'US' and g.prefix = b.zip3

),

child as (

    -- agreement across the child's records (all feeds, all seasons); NULL when there is nothing to compare
    select
        *,
        count(distinct dob) over w                                          as n_dobs,
        count(distinct sex) filter (where sex <> 'U') over w                as n_sexes,
        count(distinct zip3) filter (where zip_market_id is not null) over w as n_zip3s,
        min(dob) over w                                                     as child_dob,
        count(*) over w                                                     as n_child_records
    from placed
    window w as (partition by p5_person_id)

)

select
    feed,
    source_record_id,
    p5_person_id,
    -- uniqueness facts
    row_number() over (partition by p5_person_id, season_year, season_term order by registered_at nulls last, feed, source_record_id, source_row) = 1 as is_first_of_child_season,
    -- consistency facts (NULL = nothing to compare)
    case when dob is null or n_child_records < 2 or n_dobs < 1 then null else n_dobs = 1 end as dob_consistent,
    case when sex = 'U' or n_child_records < 2 then null else n_sexes = 1 end as sex_consistent,
    case when zip_market_id is null or n_child_records < 2 then null else n_zip3s = 1 end as zip3_consistent,
    case when nullif(trim(age_group_raw), '') is null or child_dob is null or n_dobs <> 1 then null
         else age_group_raw = case when {{ age_at_cutoff('child_dob', 'season_year') }} <= 5 then 'U6' when {{ age_at_cutoff('child_dob', 'season_year') }} <= 7 then 'U8'
                                   when {{ age_at_cutoff('child_dob', 'season_year') }} <= 9 then 'U10' when {{ age_at_cutoff('child_dob', 'season_year') }} <= 11 then 'U12'
                                   when {{ age_at_cutoff('child_dob', 'season_year') }} <= 13 then 'U14' else 'U17' end end as age_group_consistent
from child
