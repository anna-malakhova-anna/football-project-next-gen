{{ config(tags=['phase5']) }}
-- The data standard cites exactly one minimization variant (seed minimization_variants.in_standard), and the standard's own evidence column names it.
select 'not_exactly_one_standard_choice' as problem, cast(count(*) filter (where in_standard) as varchar) as detail
from {{ ref('minimization_variants') }} having count(*) filter (where in_standard) <> 1
union all
select 'standard_evidence_does_not_cite_the_chosen_variant', v.variant_id
from {{ ref('minimization_variants') }} v
where v.in_standard and not exists (select 1 from {{ ref('data_standard_fields') }} f where f.evidence like '%' || v.variant_id || '%')
