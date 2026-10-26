{{ config(tags=['phase7']) }}
-- PARTNER share (Phase 7, spec section 7): one federation's report card, three rows per federation (its top three fixes). A federation sees ONLY its
-- own rows: `federation` is the row scope, applied when the card is sent (DuckDB has no per-user grants, ADR-006; the scope is a policy, checked by
-- share_partner_rows_are_scoped_to_one_federation). No person, no record id, no club name: clubs appear only as counts. records_affected below k_min
-- is hidden (suppressed = PRIMARY).
select
    country_code                                                            as federation,
    country_name                                                            as federation_name,
    season_year, status, counting_grade, previous_counting_grade, counting_score, counting_score_change, limiting_dimension,
    clubs_known, clubs_filed, clubs_to_file_for_measured,
    fix_rank, fix_guidance, fix_dimension, moves_counting_grade, clubs_affected,
    case when records_affected >= {{ privacy_param('k_min') }} or records_affected = 0 then records_affected end as records_affected,
    case when records_affected > 0 and records_affected < {{ privacy_param('k_min') }} then 'PRIMARY' else 'NONE' end as suppressed
from {{ ref('mart_gmp_federation_report') }}
order by federation, fix_rank
