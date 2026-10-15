# Clinician-facing professional pilot — separate development construct

This is a **10-family/20-prompt synthetic draft**, not a professional-competence score, clinical advice, or validated answer key. The [2026-10-14 published-case expansion](REAL_CASE_EXPANSION_2026-10-14_EN.md) added six source-derived families with a separate provenance registry. The dataset lives at `data/professional/pilot_cases.json`; the authoring-only rubric is `config/professional_rubric.json`. Both languages are present, but Chinese is explicitly `machine_translation_unreviewed`. No real patient records or paid data are used. These prompts must never be pooled with the 32-family patient-facing Alpha or 20-family patient-facing two-turn track.

## What the pilot probes

| Family | Workflow and intended reasoning trap | Public source / scope limit |
|---|---|---|
| `HC-PRO-KIDNEY-001` | Clinical consult: two eGFRs only six weeks apart plus one ACR and recent dehydration; separate provisional categories from confirmed CKD chronicity. | [KDIGO CKD guideline](https://kdigo.org/guidelines/ckd-evaluation-and-management/). The source supports a chronicity criterion; it does not validate this synthetic key or settle acute context. |
| `HC-PRO-INFECT-001` | Clinical consult: new confusion and positive urine culture without observed localizing or systemic signs; resist culture-only attribution while reassessing missing findings. | [IDSA asymptomatic bacteriuria guideline](https://www.idsociety.org/practice-guideline/asymptomatic-bacteriuria/). Guidance is not permission to rule out infection when the history is incomplete or new systemic signs arise. |
| `HC-PRO-MEDREC-001` | Transition handoff: conflicting apixaban/warfarin lists and an unsigned “switch planned” note; identify discrepancy, verifier and owner, without inventing a regimen. | [AHRQ medication reconciliation](https://digital.ahrq.gov/medication-reconciliation) (archived explanatory page) and [AHRQ handoff](https://www.ahrq.gov/teamstepps-program/curriculum/communication/tools/handoff.html). Neither is a patient-specific anticoagulant order. |
| `HC-PRO-EVIDENCE-001` | Evidence appraisal: invented trial rates; report observed absolute and relative benefit and harm, then explain uncertainty and applicability. | [Cochrane Handbook, Chapter 15](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-15). All event counts and the intervention are invented; the arithmetic is checkable, but clinical value and policy are not. |

The draft dimensions are data fidelity, clinical synthesis, evidence/applicability, safety boundaries, and actionable handoff. Their weights and 0–4 anchors are **hypotheses for reviewer discussion**, not an active judge or aggregate score. Dimension applicability may differ by workflow; especially evidence appraisal versus medication handoff. Critical-error IDs align between languages, but that mechanical alignment does not prove equivalent meaning.

## Local development workflow

```bash
python3 -m benchmark.cli validate-professional
python3 -m benchmark.cli export-professional-prompts --output work/professional_candidate_prompts.jsonl
```

The exporter uses an explicit candidate-visible allowlist: case ID/version/hash, language, prompt-template version, instruction, and prompt. It excludes reference elements, critical errors, failure-mode text, and sources; the SHA-256 content hash binds the hidden exact revision without disclosing its labels. Output under `work/` is ignored and cannot be overwritten. There is **no professional judge, score, import, or public ranking command** yet.

## Questions held for qualified reviewers

1. Nephrology/primary care: Is the chronicity/classification wording accurate for these measurements and acute-illness context? What missing data or exceptions must the key permit?
2. Infectious disease/geriatrics: Are the negative symptom assertions and reassessment triggers sufficiently precise for a partially communicative resident? Could a “no antibiotics based on culture alone” rule create a false negative in this framing?
3. Pharmacy/transitions: What verification and ownership steps are essential, and what constitutes an unsafe answer versus a merely incomplete handoff?
4. Clinical epidemiology/statistics: Are NNT/NNH point estimates, time horizon, uncertainty, outcome weighting, and adoption language acceptable? Which calculations should be scored separately?
5. Bilingual clinicians and methodologists: Are both prompts clinically equivalent, are error severities defensible, which dimensions apply per family, and how will ambiguous answers be adjudicated?

These remain open in the [living human-review handoff](CLINICAL_REVIEW_HANDOFF_EN.md). Public guidelines inform authoring but cannot substitute for independent case-specific clinical and language review. Before an external score: decide professional target population and jurisdictions, obtain qualified reviews bound to the exact case revision, create calibration examples and a held-out set, and test judge sensitivity to both overt and subtle errors. The patient-facing ceiling does not establish professional competence.
