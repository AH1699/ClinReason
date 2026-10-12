# Alpha label expansion — 2026-10-11

At the end of this first batch, the configured Global Core Alpha contained **18 bilingual families / 36 prompts**, three families per category. The original 24 prompt rows remained at their original IDs, versions, and content hashes; the six new families were `-003` in each category. The later [batch B](LABEL_EXPANSION_BATCH_B_2026-10-11_EN.md) brought the current total to 30 families / 60 prompts. This is a development-set expansion, not a validated benchmark or an expert-clinical track. One English/Chinese pair is one underlying clinical scenario, not two independent scenarios.

[`family_labels.json`](../data/alpha/family_labels.json) adds a machine-readable, family-level multi-axis classification to **all 18** families: one primary competency, reusable reasoning operations, anticipated failure modes, and complexity factors. It does not change scoring weights or silently modify the original 24 cases. These analytic labels are author hypotheses, not clinician-approved ground truth. Case-specific `critical_requirements` and `critical_errors` remain the provisional scoring criteria.

| New family | Distinct challenge | Key human-review question |
|---|---|---|
| TRIAGE-003 | New infection danger signs override yesterday's reassurance. | Confirm emergency language and severity-3 delay rule across care settings. |
| MEDSAFE-003 | Possible bleeding on an anticoagulant plus unknown over-the-counter drug and an unsafe dosing request. | Pharmacist/acute-care review of urgency, dose boundary, and false-positive error triggers. |
| COMMS-003 | Abnormal cancer screening, distress, and absent follow-up ownership. | Screening specialist to specify acceptable follow-up wording without inventing a universal deadline. |
| REASON-003 | Two longitudinal numbers with missing test identity, units, ranges, and lab comparability. | Laboratory-medicine review of escalation when asymptomatic; avoid teaching that every numeric change is a kidney diagnosis. |
| KNOW-003 | Two guideline excerpts from different dates and risk populations. | Guideline specialist to assess source-fit, currency, and local applicability as distinct criteria. |
| ADV-003 | Malicious instructions embedded in a pasted portal note while a real follow-up task remains. | Security reviewer to assess the trust-boundary construct; clinical reviewer to check the safety obligation. A true indirect-injection test needs an external-content channel, not only a quoted user prompt. |

## Limits and next authoring batch

At this snapshot there were only three families per category, mostly single-turn patient-facing text, and no clinician-facing professional tasks. The new prompts were more detailed, but difficulty labels were **hypotheses**, not measured item difficulty. A capable model or generous judge may still score near the ceiling. The later 30-family set passed offline pipeline tests; answer diversity, judge disagreements, and early specialty/bilingual review of the highest-risk rules still need examination. Add multi-turn and structured longitudinal case contracts before claiming to test those constructs; a single prompt that narrates yesterday and today is not a true multi-turn evaluation. External data options and licensing caveats are in [the source inventory](PUBLIC_DATASET_SOURCES_EN.md).
