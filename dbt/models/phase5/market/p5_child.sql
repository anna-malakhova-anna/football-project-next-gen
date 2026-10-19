{{ config(schema='phase5_restricted') }}
-- RESTRICTED (child side). One row per resolved child with a registration in the latest season: home market (most frequent ZIP3-derived market among their records), state of their league,
-- age band, and the child's id in the LOW identity range. Child-level; nothing downstream outputs a row from it, only counts.
with latest as (select max(season_year) as latest_season from {{ ref('stg_p5_registrations') }}),

recs as (

    select
        q.p5_person_id, q.market_id, q.league_group, q.league_id, q.season_year,
        s.birth_year, nullif(trim(s.age_group_raw), '') as age_group_raw, nullif(trim(s.grade_raw), '') as grade_raw,
        l.low_id, rp.contact_email
    from {{ ref('p5_record_quality') }} q
    join {{ ref('stg_p5_registrations') }} s on s.feed = q.feed and s.source_record_id = q.source_record_id
    join {{ ref('p5_record_person') }} rp on rp.feed = q.feed and rp.source_record_id = q.source_record_id
    left join (
        select i.content_hash, min(c.p5_low_person_id) as low_id
        from {{ ref('p5_idr_input_records') }} i join {{ ref('p5_clusters_probable') }} c using (match_record_id) group by 1
    ) l on l.content_hash = s.content_hash
    where q.season_year = (select latest_season from latest)

),

market_votes as (

    select p5_person_id, market_id, count(*) as n,
           row_number() over (partition by p5_person_id order by count(*) desc, market_id) as rn
    from recs where market_id not in ('UNPLACED', 'UNMAPPED_ZIP')
    group by 1, 2

),

birth_votes as (

    -- the child's birth year: the most frequent one among their records. On a tie the LATER year wins (the younger band): protective, and consistent with "the youngest child governs".
    select p5_person_id, birth_year,
           row_number() over (partition by p5_person_id order by count(*) desc, birth_year desc) as rn
    from recs where birth_year is not null
    group by 1, 2

),

per_child as (

    select
        p5_person_id,
        min(league_group)                                                   as league_group,
        min(league_id)                                                      as league_id,
        any_value(bv.birth_year)                                            as birth_year,
        min(age_group_raw)                                                  as age_group_raw,
        min(grade_raw)                                                      as grade_raw,
        min(low_id)                                                         as low_person_id,
        -- weakly identified: no record of the child in the latest season has a parent email or a birth year (school rosters), so nothing could have matched it to another registration
        bool_and(contact_email is null and r.birth_year is null)            as is_weakly_identified
    from recs r left join (select p5_person_id, birth_year from birth_votes where rn = 1) bv using (p5_person_id) group by 1

)

select
    c.p5_person_id,
    coalesce(v.market_id, 'UNPLACED')                                       as market_id,
    c.league_group,
    lg.state                                                                as league_state,
    c.low_person_id,
    c.is_weakly_identified,
    case
        when c.birth_year is not null and (select latest_season from latest) - c.birth_year between 0 and 17 then
            case when (select latest_season from latest) - c.birth_year <= 5 then 'U6' when (select latest_season from latest) - c.birth_year <= 7 then 'U8'
                 when (select latest_season from latest) - c.birth_year <= 9 then 'U10' when (select latest_season from latest) - c.birth_year <= 11 then 'U12'
                 when (select latest_season from latest) - c.birth_year <= 13 then 'U14' else 'U17' end
        when c.birth_year is not null then 'UNKNOWN'          -- an implausible birth year is not an age
        when c.age_group_raw is not null then c.age_group_raw
        when c.grade_raw is not null then
            case when try_cast(replace(c.grade_raw, 'K', '0') as integer) + 5 <= 5 then 'U6' when try_cast(replace(c.grade_raw, 'K', '0') as integer) + 5 <= 7 then 'U8'
                 when try_cast(replace(c.grade_raw, 'K', '0') as integer) + 5 <= 9 then 'U10' when try_cast(replace(c.grade_raw, 'K', '0') as integer) + 5 <= 11 then 'U12'
                 when try_cast(replace(c.grade_raw, 'K', '0') as integer) + 5 <= 13 then 'U14' else 'U17' end
        else 'UNKNOWN'
    end                                                                     as age_band
from per_child c
left join (select * from market_votes where rn = 1) v using (p5_person_id)
left join {{ source('raw_p5', 'p5_league_catalog') }} lg on lg.league_id = c.league_id
