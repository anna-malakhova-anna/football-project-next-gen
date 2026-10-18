# Reference design: how the products feed each other

An original diagram of this project's own flow. Output ports are the share schemas; the gates are where age and consent rules are applied.

```mermaid
flowchart LR
  subgraph Sources
    S1[League registrations]
    S2[Federation returns]
    S3[Fan engagement]
  end
  subgraph Restricted zones
    ID[(identity and household zone)]
    LK[(linkage zone)]
  end
  S1 --> DP1[DP1 Intake]
  S2 --> DP1
  DP1 --> DP2[DP2 Participant and household master]
  DP2 --- ID
  DP2 --> DP3[DP3 Global insights]
  DP2 --> DP4[DP4 US growth and club markets]
  DP2 --> DP5[DP5 Flag-to-fan conversion]
  S3 --> DP5
  DP5 --- LK
  DP1 -. fix lists and the data standard .-> S1
  DP3 --> P3{{share_exec}}
  DP4 --> P4{{share_club}}
  DP5 --> P5{{share_privacy and club aggregates}}
  DP2 --> P2{{share_ops}}
  AG[[age gate: age tier and jurisdiction]] --- DP5
  CG[[consent gate: guardian permission, never inherited by the child]] --- DP5
  DP1 --> P1{{aggregate ops port}}
```

Reading it
- **Arrows between products are dependencies.** DP3, DP4 and DP5 all depend on DP2; DP2 depends on DP1.
- **Dotted line:** DP1 gives something back to the supplier, the fix list and the data standard. That is why a volunteer league has a reason to send the data.
- **Restricted zones** (identity, household, linkage) are never an output port. Only aggregates leave them, through the share schemas.
- **The age gate and the consent gate sit in front of DP5** and anything that activates a household (section 4 of the handover, ADR-022). Analytics on linked households is allowed under the project's household linkage policy (ADR-009); activation is allowed only with the guardian's permission for the purpose.
