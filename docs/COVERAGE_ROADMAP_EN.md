# Case-coverage expansion roadmap — 2026-10-08

The present Global Core Alpha has **12 bilingual families / 24 prompts**: only two families in each of six categories. It is a pipeline and authoring pilot, not a meaningful measure of complex clinical reasoning or expert-level knowledge. Counting the translated version as a second independent clinical scenario would overstate coverage. Existing cases are mainly short, single-turn patient-facing safety situations.

## Separate capabilities before adding volume

1. **Patient-facing Global Core:** safe triage, clarification, medication boundaries, result explanation, privacy, and uncertainty without assuming a country's services. Expand this development set from 12 toward **30–50 distinct bilingual families** as a planning target, not a statistical sufficiency claim.
2. **Clinician-facing professional track:** care consultation, evidence interpretation, documentation/communication, and research synthesis. Author and review it separately; a high score on patient-facing safety must not imply expert clinical competence.
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

- First fix high-priority issues in the existing 12 families and obtain early expert feedback on the rubric. Adding many cases with the same flaw increases rework.
- Draft a coverage matrix by user persona, workflow, acuity, difficulty, language, specialty, and jurisdiction. Select cases for distinct failure modes rather than paraphrase count.
- Pilot a small set of advanced families with public evidence and synthetic facts. AI may help draft and audit, but a qualified clinician must establish the clinical reference and error severity; a qualified bilingual reviewer must approve language equivalence.
- Keep development and judge-calibration cases separate from a hidden Gold Set. Meaning-changing edits require new versions and repeat review. Set sample-size and uncertainty targets with a statistician before publishing per-category comparisons.
- Do not publish a single “expert clinical reasoning” score that pools patient-facing and clinician-facing tasks. Report each track, category, language, critical-error rate, and uncertainty separately.
