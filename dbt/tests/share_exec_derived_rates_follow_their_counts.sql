{{ config(tags=['phase3']) }}
-- A derived rate is never published where its row is suppressed, and published shares are proportions. Also: the
-- suppressed label agrees with the NULLs (a SECONDARY or PRIMARY row hides a count; a NONE row hides none).
select 'rate_published_on_suppressed_row' as problem, participation_year, country_code, age_band
from {{ ref('share_exec__participation_segments') }}
where suppressed <> 'NONE' and girls_share_of_youth is not null
union all
select 'share_out_of_range', participation_year, country_code, age_band
from {{ ref('share_exec__participation_segments') }} where girls_share_of_youth < 0 or girls_share_of_youth > 1
union all
select 'none_label_but_count_hidden', participation_year, country_code, age_band
from {{ ref('share_exec__participation_segments') }} where suppressed = 'NONE' and participants is null
union all
select 'suppressed_label_but_count_published', participation_year, country_code, age_band
from {{ ref('share_exec__participation_segments') }} where suppressed <> 'NONE' and participants is not null
union all
select 'retention_published_on_suppressed_row', participation_year, null, null
from {{ ref('share_exec__participation_global') }} where suppressed <> 'NONE' and retention_rate is not null
