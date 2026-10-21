# S13 preregistered scoring-separation probes — 2026-10-20

**State: frozen author hypothesis, not run or judged.** The [S13 packet](../data/multiturn/scoring_coherence_probes_s13_v1.json) and [offline validator](../benchmark/scoring_probe_prereg.py) define eight synthetic, EN/ZH, two-turn answers for the unchanged `HC-MT-TRIAGE-020` public development family. The packet SHA-256 is `5b46e84939eab73d90551f3f254485d14fcab0183c508c1a1547d6368eb316b9`. There are no new cases, candidate responses, scores, clinical approvals or model calls. Current public development remains **112 families / 224 variants**; approved calibration and hidden Gold remain **0/0**.

This family was chosen because its update asks whether an improving short course with residual yellow discharge requires antibiotics. The existing [provisional anchors](../config/multiturn_criterion_anchors_batch_g_v1.json) separately name (1) interpreting the changed course, (2) a proportional no-antibiotic plan, and (3) future warning signs. [CDC outpatient guidance](https://www.cdc.gov/antibiotic-use/hcp/clinical-care/adult-outpatient.html) describes severe, persistent and double-worsening patterns for adult acute bacterial rhinosinusitis; [NHS acute-sinusitis pathway](https://www.nhsbsa.nhs.uk/sites/default/files/2025-06/PF%20Clinical%20Pathways%20v.2.5%20with%20red%20flag_cks_cancer_and_gateway_stocktake%20%282%29.pdf) lists orbital/vision complications and severe frontal headache among red flags. These are public contextual sources, not case-level clinical approval or a global disposition rule. The source-to-exact-anchor and EN/ZH equivalence questions remain H66/H70/H75.

## Frozen answer design

The first-turn answer and case text are identical across variants within each language. The baseline update has four fixed segments: course interpretation, no-antibiotic answer, symptom-care/routine-review plan, and warning for new eye/vision or severe-headache features. Each contrast makes **one segment-level edit only**, enforced by the renderer and tests:

| Variant | Only update edit | Author's provisional update-status hypothesis | Intended dimension question |
|---|---|---|---|
| `baseline` | None | `met/met/met` | Reference for within-language comparison; not a Gold answer. |
| `plan_omission` | Drop the practical symptom-care/routine-review segment. | `met/partial/met` | Does requirements fall without a safety or revision deduction for the same omission? |
| `safety_net_omission` | Drop the new eye/vision/severe-headache warning; routine persistence/worsening follow-up remains. | `met/met/partial` | Is this a partial safety-net loss, and if safety and revision both fall, are they distinct judgments? |
| `revision_failure` | Replace only the course interpretation with wording that acknowledges improvement but fails to use it in the antibiotic reasoning. | `partial/met/met` | Does revision fall while immediate action and later warning remain intact? |

These are **construct-isolation attempts, not proven isolated clinical changes**. An omitted plan may affect safety, and an omitted warning may legitimately affect revision. A judge may disagree with any author status. If so, retain the disagreement; do not silently relabel or revise the packet after outcomes are known.

## Locked prospective readout; no fit to desired score bands

The future judge-only experiment is capped at **16 calls**: four answers × two languages × the frozen Gemini/Grok judges, with zero candidate calls. Before any live call, implement an opt-in runner that checks the eight packet hashes, exact model and instruction hashes, fresh output directory and hard call cap; stop on a malformed or unknown-delivery result rather than silently retrying or mixing protocols. Save each judgment, dimension score, criterion status, critical-error ID, review request and pass flag separately. Do not average the two judges into a clinical truth.

For each judge/language, report the three variant-minus-baseline changes in each 0–4 rating and in raw/gated scores, targeted criterion-status changes, critical-error detection, and pass-boundary flips. Apply [S12's read-only coherence questions](S12_SCORING_COHERENCE_DIAGNOSTIC_2026-10-20_EN.md) descriptively, including overlap of safety and revision penalties. Compare EN/ZH patterns only as authored counterparts, not translation-equivalent stimuli. There is **no required numeric score or ordering**, and the owner's desired lower/mid/premium ~60–70/~80/~90 bands are not fitting targets. If status judgments or dimensions diverge, document the exact answer span and add it to H75 before proposing a new versioned scoring contract. Clinical/bilingual reviewers may later reject the author hypotheses; no public ranking or calibration claim follows from this probe.

To reproduce the current *offline-only* manifest: `python3 -m benchmark.scoring_probe_prereg`. It outputs the packet hash and eight packet/answer hashes, without keys, model calls, or scores. Four focused tests plus the project suite validate the frozen edits and reject changed case/protocol/initial-turn bindings.
