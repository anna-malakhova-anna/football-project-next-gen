-- One row per resolved person. Survivorship rules (spec section 11):
--   names                most frequent display form; ties go to the accented form, then the most recent
--   dob                  mode of DAY-precision values (NULL if none); birth_year from dob, else mode of birth_year
--   sex                  mode excluding U; tied -> U
--   home country/region  most recent registration
--   email / phone        most recent non-null
--   consent_*            most recent CAPTURED (non-null) value with the season it came from. Never derived from NULL,
--                        never borrowed from another participant.
-- Recency = season year, then term (SPRING < FALL), then registration time.
with b as (

    select distinct participant_id, match_record_id, cluster_size, link_methods
    from {{ ref('bridge_registration_participant') }}
    where registration_key = match_record_id

),

r as (

    select
        b.participant_id,
        b.cluster_size,
        b.link_methods,
        i.*,
        i.season_year * 10 + case i.season_term when 'FALL' then 2 else 1 end   as season_order,
        row_number() over (
            partition by b.participant_id
            order by i.season_year desc, case i.season_term when 'FALL' then 2 else 1 end desc,
                     i.registered_at desc nulls last, i.match_record_id
        )                                                                   as recency_rank
    from b join {{ ref('idr_input_records') }} i using (match_record_id)

),

first_names as (

    select participant_id, first_name from (
        select participant_id, first_name,
               row_number() over (partition by participant_id
                   order by count(*) desc, (first_name <> strip_accents(first_name)) desc, min(recency_rank)) as rn
        from r where first_name is not null group by participant_id, first_name
    ) where rn = 1

),

last_names as (

    select participant_id, last_name from (
        select participant_id, last_name,
               row_number() over (partition by participant_id
                   order by count(*) desc, (last_name <> strip_accents(last_name)) desc, min(recency_rank)) as rn
        from r where last_name is not null group by participant_id, last_name
    ) where rn = 1

),

dobs as (

    select participant_id, dob from (
        select participant_id, dob,
               row_number() over (partition by participant_id order by count(*) desc, min(recency_rank)) as rn
        from r where dob is not null and dob_precision = 'DAY' group by participant_id, dob
    ) where rn = 1

),

birth_years as (

    select participant_id, birth_year from (
        select participant_id, birth_year,
               row_number() over (partition by participant_id order by count(*) desc, min(recency_rank)) as rn
        from r where birth_year is not null group by participant_id, birth_year
    ) where rn = 1

),

sex_counts as (

    select participant_id, sex, count(*) as n from r where sex <> 'U' group by 1, 2

),

sexes as (

    -- the most common known sex; a tie for first place leaves it unknown
    select t.participant_id, case when count(*) = 1 then max(c.sex) else 'U' end as sex
    from (select participant_id, max(n) as top_n from sex_counts group by 1) t
    join sex_counts c on c.participant_id = t.participant_id and c.n = t.top_n
    group by t.participant_id

),

latest as (

    select participant_id, country_code as home_country_code, region_code as home_region_code
    from r where recency_rank = 1

),

emails as (

    select participant_id, contact_email from (
        select participant_id, contact_email, row_number() over (partition by participant_id order by recency_rank) as rn
        from r where contact_email is not null) where rn = 1

),

phones as (

    select participant_id, contact_phone from (
        select participant_id, contact_phone, row_number() over (partition by participant_id order by recency_rank) as rn
        from r where contact_phone is not null) where rn = 1

),

photo as (

    select participant_id, consent_photo, registered_at as consent_photo_captured_at, season_year as consent_photo_season_year
    from (select *, row_number() over (partition by participant_id order by recency_rank) as rn
          from r where consent_photo is not null) where rn = 1

),

marketing as (

    select participant_id, consent_marketing, registered_at as consent_marketing_captured_at, season_year as consent_marketing_season_year
    from (select *, row_number() over (partition by participant_id order by recency_rank) as rn
          from r where consent_marketing is not null) where rn = 1

),

agg as (

    select
        participant_id,
        min(season_year)                                                    as first_season,
        max(season_year)                                                    as last_season,
        count(distinct season_year)                                         as seasons_active,
        count(*)                                                            as registration_count,
        list_sort(list_distinct(list(source_system)))                       as source_systems,
        max(cluster_size)                                                   as cluster_size,
        list_distinct(flatten(list(link_methods)))                          as all_link_methods
    from r group by participant_id

),

latest_season as (select max(season_year) as year from {{ ref('idr_input_records') }})

select
    a.participant_id,
    fn.first_name,
    ln.last_name,
    d.dob,
    coalesce(extract(year from d.dob)::integer, byr.birth_year)              as birth_year,
    case when d.dob is not null then 'DAY' else 'YEAR' end                  as dob_precision,
    coalesce(sx.sex, 'U')                                                    as sex,
    l.home_country_code,
    l.home_region_code,
    e.contact_email,
    p.contact_phone,
    (ls.year - coalesce(extract(year from d.dob)::integer, byr.birth_year)) < 18 as is_minor_current,
    ph.consent_photo,
    ph.consent_photo_captured_at,
    ph.consent_photo_season_year,
    m.consent_marketing,
    m.consent_marketing_captured_at,
    m.consent_marketing_season_year,
    a.first_season,
    a.last_season,
    a.seasons_active,
    a.registration_count,
    a.source_systems,
    case
        when a.cluster_size = 1 then 'SINGLETON'
        when list_contains(a.all_link_methods, 'STEWARD') then 'REVIEWED'
        when len(a.all_link_methods) = 1 and a.all_link_methods[1] = 'SOURCE_ID' then 'DETERMINISTIC_ONLY'
        else 'HIGH'
    end                                                                     as resolution_confidence,
    ci.cluster_id is not null                                               as has_open_integrity_issue
from agg a
left join first_names fn using (participant_id)
left join last_names ln using (participant_id)
left join dobs d using (participant_id)
left join birth_years byr using (participant_id)
left join sexes sx using (participant_id)
left join latest l using (participant_id)
left join emails e using (participant_id)
left join phones p using (participant_id)
left join photo ph using (participant_id)
left join marketing m using (participant_id)
cross join latest_season ls
left join (
    select distinct participant_id, ci2.cluster_id
    from {{ ref('bridge_registration_participant') }} br
    join {{ ref('idr_cluster_integrity') }} ci2 on ci2.cluster_id = br.cluster_id
) ci on ci.participant_id = a.participant_id
