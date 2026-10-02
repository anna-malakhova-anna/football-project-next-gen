{{ config(tags=['phase3'], severity='warn') }}
-- WARN-level: how identifying is the analyst share? Counts participant-year rows whose quasi-identifier combination
-- (year, birth year, postal prefix, sex, country) is shared by fewer than privacy_params.analyst_k_warn rows. The share is
-- pseudonymized, not anonymous: a warning here is expected and is the reason analyst access needs a stated purpose (ADR-006).
select participation_year, birth_year, postal_prefix, sex, attributed_country_code, count(*) as class_size
from {{ ref('share_analyst__participant_year') }}
group by 1, 2, 3, 4, 5
having count(*) < {{ privacy_param('analyst_k_warn') }}
