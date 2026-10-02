-- GROUND TRUTH (evaluation only). What we expect of the consent history. Resolving by timestamp trusts a timestamp that is wrong for a few lines (an opt-out stamped before the opt-in it follows). Staging
-- flags such a line when NO earlier opt-in exists on that account and channel; if the account had an earlier opt-in as well, the swap looks like a legal sequence and cannot be seen from the data.
-- So the checks expect: nearly all of the unsafe mismatches (history says opt_in, the account opted out) carry the flag, so a contact use can fail closed on them, and the mismatch rate is tiny. A
-- small residue is NOT flagged and is reported, not hidden: it is the limit of resolving consent by timestamp. Statements about a sound design, not tuning targets.
select 'at_least_90pct_of_mismatches_are_flagged_doubtful' as check_name, mismatches_flagged_as_doubtful >= 0.9 * mismatches as passed, cast(mismatches as varchar) || ' mismatches, ' || cast(mismatches_flagged_as_doubtful as varchar) || ' flagged' as detail
from {{ ref('eval_consent_history') }}
union all
select 'at_least_90pct_of_unsafe_mismatches_are_flagged_doubtful', unsafe_mismatches_flagged_as_doubtful >= 0.9 * unsafe_mismatches, cast(unsafe_mismatches as varchar) || ' unsafe, ' || cast(unsafe_mismatches_flagged_as_doubtful as varchar) || ' flagged'
from {{ ref('eval_consent_history') }}
union all
select 'mismatch_rate_under_half_a_percent', mismatch_rate < 0.005, 'mismatch rate ' || cast(mismatch_rate as varchar) from {{ ref('eval_consent_history') }}
