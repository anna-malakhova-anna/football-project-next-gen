-- RESTRICTED (schema `linkage`; counts only). The RFM SEGMENT MIX at the end of each year, by fan group: Champions, Loyal, Promising, At risk, Hibernating (rfm_segment_map: the recency quintile and
-- the rounded mean of the frequency and monetary quintiles). The question it answers: are the fans the flag programme brought in (NET_NEW_FLAG_PROMPT) the same kind of fan as existing fans,
-- or a different mix? Shares are of the scored accounts of the group that year. UNLINKED_OR_NON_PARTICIPANT is every account we cannot place in a participant household; it is not "non-participant fans".
with s as (

    select r.year, g.fan_group, m.segment
    from {{ ref('int_fan_rfm_scores') }} r
    join {{ ref('int_fan_account_group') }} g using (fan_account_id)
    join {{ ref('rfm_segment_map') }} m on m.r_score = r.r_score and m.fm_score = r.fm_score

)

select
    year, fan_group, segment,
    count(*)                                                                as accounts,
    round(count(*) * 1.0 / sum(count(*)) over (partition by year, fan_group), 4) as share_of_group,
    '{{ var("methodology_version") }}'                                      as methodology_version
from s
group by year, fan_group, segment
order by year, fan_group, segment
