# Case-coverage expansion roadmap — updated 2026-10-14

The present Global Core Alpha has **32 bilingual families / 64 prompts**: seven triage families and five in each other category. [Batch A](LABEL_EXPANSION_2026-10-11_EN.md) and [batch B](LABEL_EXPANSION_BATCH_B_2026-10-11_EN.md) added 18 synthetic families beyond the original 12; two new low-acuity triage controls were added on 2026-10-12 without revising earlier rows. It is still a pipeline and authoring pilot, not a meaningful measure of complex clinical reasoning or expert-level knowledge. Counting the translated version as a second independent clinical scenario would overstate coverage. Cases remain single-turn patient-facing situations, even when a prompt describes a timeline.

The machine-readable [coverage audit](../benchmark/coverage.py) confirms this: 32/32 patient-facing and single-turn, with triage split 4 emergency / 1 timely nonemergency / 1 routine / 1 self-care. The new low-acuity cases test restraint from overtriage, but one family in each cell is thin coverage, not an estimate of performance. `coverage-audit` also counts author-assigned reasoning tags; these are **intended probes, not measured difficulty**. See the [progress log](PROJECT_PROGRESS_2026-10-11_EN.md).

A [separate scripted two-turn pilot](MULTITURN_PILOT_2026-10-11_EN.md), [batch C](MULTITURN_BATCH_C_2026-10-11_EN.md), [batch D](MULTITURN_BATCH_D_2026-10-12_EN.md), and [batch E](BATCH_E_100_FAMILIES_2026-10-14_EN.md) now contain **30 draft families / 60 conversations**. The new batch tests escalation from allergy, heat, clot, and eye symptoms, anticoagulated head injury reassessment, medication hazards, and interpretation of ANA/celiac tests. This track is synthetic, unreviewed, and outside the single-turn score; item count does not establish difficulty.

Across the three deliberately separate tracks there are now **100 distinct bilingual families** (32 Alpha + 30 two-turn + 38 professional), representing 200 language variants. These must not be pooled into one clinical score. The [batch E report](BATCH_E_100_FAMILIES_2026-10-14_EN.md) records the new constructs, provenance, review gates, and next non-clinical work.

## Separate capabilities before adding volume

1. **Patient-facing Global Core:** safe triage, clarification, medication boundaries, result explanation, privacy, and uncertainty without assuming a country's services. The **30-family first coverage milestone** has been exceeded; any further expansion toward 50 or 500 must follow coverage and review criteria, not a statistical sufficiency claim.
2. **Clinician-facing professional track:** the [original 10-family pilot](PROFESSIONAL_PILOT_2026-10-12_EN.md) plus [batch E](BATCH_E_100_FAMILIES_2026-10-14_EN.md) now hold **38 families / 76 prompts**: 24 care consultations, seven medication-reconciliation handoffs, and seven evidence appraisals. Twenty-two families are rewritten adaptations of distinct CC BY clinical case reports, with attribution and limitations recorded; the rest are synthetic evidence/guidance scenarios. Documentation and broader research synthesis remain gaps. A high patient-facing score must not imply expert clinical competence; professional scoring remains disabled.
3. **Jurisdiction packs:** local guidelines, drugs, referral pathways, screening schedules, and effective dates. These must not be smuggled into Global Core answers or scored as universally correct.

The [HealthBench study](https://arxiv.org/abs/2505.08775) used multi-turn conversations and case-specific physician-written rubrics to assess open-ended healthcare behavior. [HealthBench Professional](https://arxiv.org/abs/2604.27470) focused on clinician care consultation, documentation, and medical research, with physician authorship and adjudication. These are methodological examples, **not** evidence that this project's current cases or score are comparable to those benchmarks. [Official OpenAI evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices) also emphasizes task-representative coverage and human calibration over a raw item count.

## Priority coverage gaps

| Gap | What new draft families should probe | Required control |
|---|---|---|
| Sequential reasoning | New information arriving after an initial answer; whether the model revises a differential or urgency appropriately | Extend the case contract to multi-turn input and score the final response in context; clinician reviews each branch |
| Competing risks and multimorbidity | Conflicting symptoms, multiple chronic conditions, polypharmacy, contraindication uncertainty | Specialty-matched clinician/pharmacist reviews; no unsupported individualized dose rules |
| Longitudinal data | Synthetic lab trends, conflicting notes, missing units/reference ranges, critical-result handling | Laboratory-medicine review and explicit data provenance |
| Evidence and guideline appraisal | Conflicting, outdated, low-quality, or jurisdiction-specific sources; when to abstain or request local policy | Source date, applicability, and uncertainty must be scored separately from recall |
| Professional workflows | Care consult, handoff summary, documentation, literature synthesis | Separate clinician-facing construct, persona, and rubric; do not mix with patient-facing average |
| Robustness and equity | English/Chinese meaning equivalence, health literacy, accessibility, resource constraints, adversarial instructions | Bilingual clinical review and bias checks; no demographic stereotypes |

## Authoring sequence and release boundary

- Next non-clinical priority: audit mechanism-level duplication and source-to-label traceability across all 100 families, preserve source licenses, and construct a balanced hidden/calibration split before any model-ranking claim. Then run multi-model difficulty and judge-consistency diagnostics on development items. Real-case inspiration does not itself make an item expert-level or clinically approved.
- Prioritize eventual clinical and language review of all 32 Alpha, 30 multi-turn, and 38 professional families, starting with severity-3 rules and known high-priority issues in the original 12. Review is deferred by current project choice, not waived. Adding many cases with the same flaw increases rework.
- Draft a coverage matrix by user persona, workflow, acuity, difficulty, language, specialty, and jurisdiction. Select cases for distinct failure modes rather than paraphrase count.
- Pilot a small set of advanced families with public evidence and synthetic facts. AI may help draft and audit, but a qualified clinician must establish the clinical reference and error severity; a qualified bilingual reviewer must approve language equivalence.
- Require each advanced family to name a discriminating failure mode, a plausible but unsafe/partial answer, and the observable feature of a strong answer. Extra narrative length is not complexity. Sequential reasoning needs a controlled new turn; multimorbidity needs a genuine competing-risk decision under explicitly missing data.
- Keep development and judge-calibration cases separate from a hidden Gold Set. Meaning-changing edits require new versions and repeat review. Set sample-size and uncertainty targets with a statistician before publishing per-category comparisons.
- Do not publish a single “expert clinical reasoning” score that pools patient-facing and clinician-facing tasks. Report each track, category, language, critical-error rate, and uncertainty separately.
