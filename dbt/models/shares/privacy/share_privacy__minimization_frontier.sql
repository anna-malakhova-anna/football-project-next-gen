{{ config(tags=['phase5']) }}
-- PRIVACY share: the label-free half of the minimization frontier (ADR-018): for each variant, how identifying the data is (share of participant-years that are unique, share in a class below k_min,
-- smallest class, contact fields held) and how fit it stays for each purpose. The identity-accuracy half needs the answer key and is shown only through the whitelisted evaluation summary. Aggregates only.
select
    r.variant_id, r.label as variant_label,
    r.participant_years, r.pct_unique, r.pct_rows_below_k_min, r.smallest_class, r.average_class_size, r.contact_fields_held,
    f.fit_for_count, f.fit_for_segment, f.fit_for_geo, f.fit_for_retain, f.fit_for_activate, f.rules_no_longer_evaluable
from {{ ref('mart_reidentification_risk') }} r join {{ ref('mart_minimization_fitness') }} f on f.variant_id = r.variant_id
order by r.sort_order
