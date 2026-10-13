-- Phase 5 input to the Phase 2 identity machinery: the same columns as idr_input_records, so the shared macros (pair_attributes, pair_level_ctes,
-- name_similarity, dob_agreement_level, idr_rules_rule_id, connected_components) run unchanged on the six Phase 5 feeds.
--   * Pop Warner tackle rows are not flag registrations and never enter matching
--   * byte-identical rows (a manual upload pasted twice) are collapsed to one survivor; the copies keep the survivor's person through content_hash
--   * an impossible DOB keeps its record, with DOB and birth year nulled for matching (as in Phase 2)
-- The organization is the resolved league, or the feed when the league could not be resolved.
select
    md5(feed || '|' || source_record_id)                                    as match_record_id,
    feed                                                                    as source_system,
    source_record_id,
    content_hash,
    season_key,
    season_year,
    league_group                                                            as organization_id,
    'US'                                                                    as country_code,
    first_name_key,
    last_name_key,
    case when age_at_cutoff between 0 and 80 then dob end                   as dob,
    case when age_at_cutoff between 0 and 80 then birth_year end            as birth_year,
    case when age_at_cutoff between 0 and 80 then dob_precision end         as dob_precision,
    sex,
    contact_email,
    cast(null as varchar)                                                   as contact_phone,
    postal_code,
    registered_at,
    -- the oldest age an age-group label allows (U10 -> 9) and the age implied by a DOB: used only by the R7 guard in p5_pair_scores
    case when regexp_matches(age_group_raw, '^U\d+$') then case when age_group_raw = 'U17' then 17 else cast(substr(age_group_raw, 2) as integer) - 1 end end as age_group_cap,
    age_at_cutoff
from {{ ref('stg_p5_registrations') }}
where is_flag and not is_exact_duplicate_row
