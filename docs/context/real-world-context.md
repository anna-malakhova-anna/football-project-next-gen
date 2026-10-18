# Real-world context

> The project's data is **synthetic**. This page lists the public facts that shaped the synthetic design, with their sources. **Nothing else about NFL FLAG, RCX Sports, any club, vendor or league is a fact here:** every other statement the project makes about those systems is an **assumption** and is labelled as one where it is made. Nothing on this page, or anywhere in the project, is a finding that any organization is or is not compliant with any law.

## Facts used (as stated in the sources)

1. **Structure.** NFL FLAG is run by RCX Sports under licence from the NFL. Every league is independently owned and operated, and registration is handled by each league's operators. RCX offers *preferred* registration systems and its Matrix league software; these are recommended, not mandated, which is a structural reason for heterogeneous, inconsistent data. Scale: 830,000+ participants in 2,000+ locally operated leagues.
2. **Intake channels are multiplying.** Pop Warner associations began launching NFL FLAG leagues in spring 2026. RCX partnered with National PAL, which has 300+ chapters.
3. **Club networks.** Some clubs run their own networks; for example, the Colts run a 10-league NFL FLAG-sanctioned network in Indiana and Kentucky with RCX.
4. **Privacy notice.** The NFL FLAG privacy notice states that data collected under it is jointly owned with the "NFL Entities" (which include the clubs) and shared with them. It also says parent emails given for parental consent are not used for marketing without a separate opt-in.
5. **COPPA.** The amended FTC COPPA Rule has been fully in force since 22 April 2026. Disclosing under-13 data to third parties requires separate parental consent unless the disclosure is integral to the service; advertising and data-broker disclosures are not integral. The rule also requires a written retention policy and prohibits indefinite retention.

## Open question for the privacy lead (not resolved by this project)

Is a club a "third party" for the purposes of the COPPA rule, given the joint ownership described in the privacy notice? The build does not decide it. Where it matters, the design treats club-facing data as aggregate only and keeps parental consent for club marketing a separate, explicit purpose.

## How the facts map to the synthetic design

| Fact | Where it shows up in the project | Status |
|---|---|---|
| Independent, heterogeneous leagues | `US_LEAGUE` is the analogue of the fragmented domestic network; Phase 5 makes the fragmentation explicit at the organization level (latent quality profiles, organizations that send no file, free-text divisions) | Design choice, synthetic |
| Several intake channels | Six channel feeds (`matrix_export`, `vendor_reg_a`, `vendor_reg_b`, `pop_warner_feed`, `pal_chapter_csv`, `school_program`) | **Assumption:** the feed shapes are invented for the demonstration, not descriptions of real systems |
| Club networks | 32 "club markets" made of ZIP3 groups, with shared markets | **Assumption:** a project approximation, not any club's territory (ADR-016) |
| Parent email is not a marketing opt-in | Purpose limitation in the consent model; a consent email never counts as `CLUB_MARKETING` (ADR-019) | Design constraint |
| Retention policy required, no indefinite retention | The age-out job and the retention-versus-deletion experiment (ADR-017) | **Assumption:** every period (age-out age, grace, record cap) is a configurable placeholder; the actual period is an open question |

## Participation context for goal G2 and the LA 2028 Games (Phase 6) <!-- Anna to verify -->

These facts frame the business goals on the Data product tab. They are stated as the sources state them, and nothing else is added. **Anna to verify every line below before the tab is published.**

- High school football participation declined for years before the pandemic (its tenth drop in eleven years) and has risen in three of the last four years. It is **not** presented here as a current crisis. Source: Athletic Business, reporting NFHS figures, 18 September 2025.
- Girls' high school flag football reached 68,847 participants in 2024-25, up 388% since the first post-pandemic survey. It is sanctioned in 16 states, and 22 other states run independent or pilot programs. Sources: Athletic Business (above) and NFHS.
- Safety concerns are one reason families may choose flag football. This project treats that as a stated reason, not a measured decline.
- Flag football was approved by the IOC Session as one of five additional sports for the Los Angeles 2028 Games (relevant to goal G1). <!-- Anna to verify -->

Sources (these four lines, added in Phase 6):
- https://www.athleticbusiness.com/operations/governing-bodies/article/15755722/high-school-football-continues-to-rebound-from-prepandemic-decline
- https://nfhs.org/stories/high-school-football-continues-to-rebound-from-pre-pandemic-decline
- https://www.olympics.com/ioc/news/ioc-session-approves-la28-s-proposal-for-five-additional-sports

## Sources

- https://nflflag.com/policy
- https://nflflag.com/faq
- https://youthsportsbusinessreport.com/brand-velocity-group-acquires-rcx-sports-the-operator-behind-nfl-flag-and-jr-nba/
- https://youthsportsbusinessreport.com/rcx-sports-and-national-pal-partner-to-expand-nfl-flag-access-nationwide/
- https://playfootball.nfl.com/discover/news-and-features/nfl-flag-pop-warner-and-rcx-announce-nationwide-partnership-to-expand-access-and-pathways-in-youth-football
- https://www.colts.com/news/colts-flag-football-leagues-registration-open-spring-season-2025-nfl
- https://www.finnegan.com/en/insights/articles/coppas-amended-rule-is-now-in-full-effect-what-operators-need-to-know.html
- https://www.finnegan.com/en/insights/articles/the-ftcs-updated-coppa-rule-redefining-childrens-digital-privacy-protection.html
