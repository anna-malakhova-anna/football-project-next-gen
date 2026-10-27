-- GROUND TRUTH (evaluation only). How many record pairs each matcher got wrong, by kind and likely cause, at the AUTO scope
-- (automatic merges only), per review stage. Counts every error in eval_errors_all, not the capped list in eval_errors.
-- Unit: record pairs. A false merge of one child's a records with another child's b records is a*b pairs, so these counts
-- are larger than the cluster counts in eval_clusters (sibling_or_twin_false_merges counts clusters).
select
    matcher,
    stage,
    'AUTO'          as scope,
    error_type,
    likely_cause,
    count(*)        as record_pairs
from {{ ref('eval_errors_all') }}
group by all
order by matcher, stage, error_type, likely_cause
