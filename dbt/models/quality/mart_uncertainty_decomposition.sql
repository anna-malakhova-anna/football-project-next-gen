-- depends_on: {{ ref('observation_window') }}
-- Why there is no single number (phase-5-spec 6.1, ADR-015): the participant count is uncertain for three DIFFERENT reasons, and they are shown SIDE BY SIDE, never added.
--   IDENTITY       Phase 3 low / point / high: how many people the records are, depending on which uncertain links are real. (label-free)
--   DQ_EXCLUSIONS  strict vs lenient handling of records that fail a COUNT rule of the registry: lenient is the Phase 3 count; strict counts only participants who have at least one record
--                  fit for COUNT (dq_record_fitness). (label-free)
--   COVERAGE       participants of KNOWN organizations that sent no file that season: for each dark organization the median (and 25th / 75th percentiles) of the unique participants of reporting
--                  organizations of the same source, season, size band and region, where the size band comes from the organization's own other seasons. Falls back to the same size band in any
--                  region, then to any organization, when fewer than three peers exist. An ESTIMATE with an interval, not a bound, and not independent of the other components. (label-free)
-- Columns: point / low / high are in the component's own quantity (participants counted, or participants missing from the data). interval_low / interval_high put each on the participant scale
-- (coverage: reported point + the missing participants) so the three can be drawn as separate bars around the reported count. contribution = interval width. No row and no column sums components.
with reported as (

    select participation_year, participants_low, participants_point, participants_high
    from {{ ref('mart_identity_uncertainty') }} where grain = 'GLOBAL'

),

lenient as (

    select participation_year, count(distinct participant_id) as participants from {{ ref('fct_participant_year') }} group by 1

),

strict as (

    select season_year as participation_year, count(distinct person_id) as participants
    from {{ ref('dq_record_fitness') }} where fit_for_count and source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by 1

),

-- ---- coverage: per-organization estimates live in int_dark_org_coverage (also used by the club-market coverage) ----
coverage as (

    select season_year as participation_year, count(*) as dark_orgs, sum(q25) as low, sum(q50) as point, sum(q75) as high,
           count(*) filter (where peer_level <> 'SAME_BAND_AND_REGION') as orgs_with_wider_peer_group
    from {{ ref('int_dark_org_coverage') }} group by 1

)

select participation_year, 'IDENTITY' as component, 'participants counted' as quantity,
       participants_point::double as point, participants_low::double as low, participants_high::double as high,
       participants_point::double as reported_point,
       participants_low::double as interval_low, participants_high::double as interval_high,
       (participants_high - participants_low)::double as contribution,
       'Phase 3 bounds: connected components with PROBABLE links merged (low) or flagged clusters split (high)' as method, true as label_free
from reported
union all
select r.participation_year, 'DQ_EXCLUSIONS', 'participants counted', l.participants::double, s.participants::double, l.participants::double, r.participants_point::double,
       s.participants::double, l.participants::double, (l.participants - s.participants)::double,
       'strict (only participants with a record fit for COUNT) vs lenient (Phase 3: every valid registration)', true
from reported r join lenient l using (participation_year) join strict s using (participation_year)
union all
select r.participation_year, 'COVERAGE', 'participants missing from the data', c.point, c.low, c.high, r.participants_point::double,
       r.participants_point + c.low, r.participants_point + c.high, c.high - c.low,
       'dark organizations (' || c.dark_orgs || '; ' || c.orgs_with_wider_peer_group || ' with a wider peer group) x median unique participants of reporting peers of the same size band and region, interval = 25th to 75th percentile', true
from reported r join coverage c using (participation_year)
