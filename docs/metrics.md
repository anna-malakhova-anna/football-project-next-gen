# Metric catalog

> **Generated** from `dbt/seeds/metric_catalog.csv` by `scripts/build_metrics_doc.py` (`make docs`). Edit the CSV, not this
> file. Every KPI in `mart_kpi_scorecard` and every metric column in `share_exec` must be in the catalog; a test enforces it.
> All data is synthetic. A count is **registered participants in onboarded sources**, not total flag football participation.

Methodology version: **1.0** (see [the methodology memo](methodology/counting-a-participant.md) and the
[CHANGELOG](methodology/CHANGELOG.md)). Counting rules C1 to C15 are in ADR-005.

## Additivity

| Value | Meaning |
|---|---|
| `ADDITIVE` | can be summed across any dimension of its grain |
| `ADDITIVE_BY_ATTRIBUTION` | sums across countries only in the attributed view (a person assigned to one country); never in the presence view |
| `NON_ADDITIVE` | distinct counts that overlap across a dimension; never sum them |
| `RATIO` | never summed or averaged; recompute from numerator and denominator |
| `STATE` | a point-in-time value, not a flow |

## North star

| Metric | Name | Definition | Grain | Additivity | Unit | Owner |
|---|---|---|---|---|---|---|
| `unique_participants` | Unique participants | Resolved persons (participant_id) with at least one valid registration in the participation year (rules C1, C2, C3). The north-star metric. A person counts once however many leagues, divisions or countries they played in. | participation year (global) | `ADDITIVE_BY_ATTRIBUTION` | count | Program Insights Lead |

## Growth

| Metric | Name | Definition | Grain | Additivity | Unit | Owner |
|---|---|---|---|---|---|---|
| `new_participants` | New participants | Unique participants whose first valid registration year is this year (rule C11). 2023 is excluded: it is the first year of data, so every participant would look new (left-censored). | participation year | `ADDITIVE_BY_ATTRIBUTION` | count | Program Insights Lead |
| `returning_participants` | Returning participants | Unique participants with a valid registration this year and the prior year (rule C12). Not defined for 2023. | participation year | `ADDITIVE_BY_ATTRIBUTION` | count | Program Insights Lead |
| `reactivated_participants` | Reactivated participants | Unique participants with a valid registration this year, none last year, and at least one earlier year (rule C13). Only possible from 2025 in this data (it needs an earlier year plus a gap year). | participation year | `ADDITIVE_BY_ATTRIBUTION` | count | Program Insights Lead |
| `retention_rate` | Year-over-year retention rate | Returning participants divided by the prior year's unique participants (rule C12). Defined from 2024 (2023 has no prior year in the data). | participation year | `RATIO` | rate | Program Insights Lead |

## Reach

| Metric | Name | Definition | Grain | Additivity | Unit | Owner |
|---|---|---|---|---|---|---|
| `youth_girls_participants` | Youth girls participants | Unique youth participants (age 17 or under at December 31) whose registration-reported sex is F (rules C7, C9, C10). Reported sex only; gender identity is not collected. | participation year | `ADDITIVE_BY_ATTRIBUTION` | count | Program Insights Lead |
| `girls_share_of_youth` | Girls' share of youth participation | Youth girls participants divided by youth participants (sex F, M and U all in the denominator; U is never imputed, rule C9). | participation year | `RATIO` | rate | Program Insights Lead |
| `international_participants` | International participants (attributed, outside the US) | Unique participants whose attributed country (rule C6) is not US. | participation year | `ADDITIVE_BY_ATTRIBUTION` | count | Program Insights Lead |
| `countries_with_participants` | Countries with at least one participant | Number of countries with one or more attributed participants in the year, after reading the data (suppression does not apply to this count). | participation year | `STATE` | count | Program Insights Lead |

## Depth

| Metric | Name | Definition | Grain | Additivity | Unit | Owner |
|---|---|---|---|---|---|---|
| `registrations_per_participant` | Registrations per participant | Valid registrations divided by unique participants for the same year and grain. A depth measure: multi-league and spring-plus-fall players raise it. | participation year | `RATIO` | ratio | Program Insights Lead |
| `multi_org_participants` | Multi-organization participants | Unique participants with valid registrations in two or more organizations (leagues, clubs, federation clubs) in the year (rule C5). Counted once in the global count and in each organization's own count. | participation year | `NON_ADDITIVE` | count | Program Insights Lead |

## Data trust (reported beside the headline numbers, never hidden)

| Metric | Name | Definition | Grain | Additivity | Unit | Owner |
|---|---|---|---|---|---|---|
| `identity_range_pct` | Identity range (% of point estimate) | (high - low) / point estimate. How much identity resolution alone could move the count. Covers identity only, not source coverage or data entry errors in the sources. | participation year | `RATIO` | rate | Flag Football Data Lead |
| `pct_participants_high_confidence` | Participants resolved with high confidence | Share of unique participants whose resolution confidence is SINGLETON, DETERMINISTIC_ONLY, HIGH or REVIEWED and who sit in no cluster with an open integrity issue and touch no open review item. | participation year | `RATIO` | rate | Flag Football Data Lead |
| `open_review_items` | Open review items | Items in the identity review queue (cluster conflicts and probable pairs) awaiting a steward decision. | snapshot | `STATE` | count | Flag Football Data Lead |
| `sources_onboarded` | Sources onboarded | Sources at Modelled or Production status in the source inventory. | snapshot | `STATE` | count | Data Governance Lead |
| `sources_known` | Sources known | Sources in the source inventory at any status, including those not yet onboarded. | snapshot | `STATE` | count | Data Governance Lead |
| `pct_registrations_failing_dq` | Registrations failing DQ rules | Share of ALL registration records in the year (duplicates included) carrying at least one flag classified AFFECTS_COUNT in dq_flag_severity: duplicates, impossible or unparseable DOB, unmapped values. Missing values and normalized flags are not counted. Reported next to the headline numbers. | participation year | `RATIO` | rate | Flag Football Data Lead |

## Supporting metrics

| Metric | Name | Definition | Grain | Additivity | Unit | Owner |
|---|---|---|---|---|---|---|
| `registrations` | Valid registrations | Registration records that are not exact duplicates and whose season falls in the participation year (rule C2). Records with an impossible DOB count: the person is real, only the DOB is bad. | participation year | `ADDITIVE` | count | Flag Football Data Lead |
| `multi_country_participants` | Multi-country participants | Unique participants with valid registrations in two or more countries in the year (rule C6). The difference between the presence and attributed country views. | participation year | `NON_ADDITIVE` | count | Flag Football Data Lead |
| `censored_participants` | Censored participants (first data year) | Unique participants in the first year of data (2023), whose new / returning status cannot be known because earlier years are not in the data (rule C11). | participation year | `ADDITIVE_BY_ATTRIBUTION` | count | Flag Football Data Lead |
| `participants_attributed` | Participants (country-attributed) | Unique participants assigned to the country of their most recent registration in the year (rule C6). Sums exactly to the global unique participants. | participation year x country | `ADDITIVE` | count | Program Insights Lead |
| `participants_present` | Participants (country-presence) | Unique participants counted in every country they played in during the year (rule C6). Sums to MORE than the global count by the number of multi-country participants; never sum it for a global figure. | participation year x country | `NON_ADDITIVE` | count | Program Insights Lead |
| `participants` | Participants (segment) | Unique participants in a segment (country, age band, primary division, sex, youth flag) for the year. Additive within one grouping set; subtotal rows are labelled by grouping_id. | participation year x segment | `ADDITIVE` | count | Program Insights Lead |
| `youth_participants` | Youth participants | Unique participants aged 17 or under on December 31 of the participation year (rules C7, C10). | participation year | `ADDITIVE_BY_ATTRIBUTION` | count | Program Insights Lead |
| `identity_participants_low` | Unique participants, low bound | Unique participants if every PROBABLE pair is really one person (AUTO + PROBABLE + steward edges). Computed with the same connected-components macro as the point estimate, with no ground truth. | participation year | `NON_ADDITIVE` | count | Flag Football Data Lead |
| `identity_participants_point` | Unique participants, point estimate | Unique participants from the production edge set. Equals unique_participants. | participation year | `NON_ADDITIVE` | count | Flag Football Data Lead |
| `identity_participants_high` | Unique participants, high bound | Unique participants if every cluster with an open integrity issue is really several people (production edges minus the edges inside flagged clusters). | participation year | `NON_ADDITIVE` | count | Flag Football Data Lead |
| `participants_touched_by_review` | Participants touched by open review items | Unique participants in a cluster flagged for integrity, or with a record in an open probable pair, in the year. | participation year | `NON_ADDITIVE` | count | Flag Football Data Lead |
| `participants_open_integrity_issue` | Participants in clusters with an open integrity issue | Unique participants in clusters flagged by idr_cluster_integrity (rule C14). They are counted in unique_participants; this reports how many. | participation year | `NON_ADDITIVE` | count | Flag Football Data Lead |
