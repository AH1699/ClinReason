# Batch E — 100-family development milestone (2026-10-14)

The configured project now has **100 distinct bilingual families**, not 200 independent clinical cases. The 200 English/Simplified Chinese variants are paired views of those 100 families. This is an *authoring and pipeline milestone*, not a calibrated benchmark, professional certification, or clinically approved answer key. The three tracks have separate tasks and must not be pooled into one score.

| Track | Before | Batch E | Total | What changed |
|---|---:|---:|---:|---|
| Single-turn patient-facing Alpha | 32 | 0 | 32 | Original IDs and scoring contract unchanged |
| Two-turn patient-facing | 20 | 10 | 30 | Five triage transitions, three medication hazards, two result-interpretation traps |
| Clinician-facing professional | 10 | 28 | 38 | Sixteen rewritten published-case consults, six medication handoffs, six evidence-appraisal tasks |

The new two-turn families are in [`data/multiturn/batch_e_cases.json`](../data/multiturn/batch_e_cases.json). They test: mild rash→airway symptoms; heat cramps→confusion while still sweating; anticoagulated head injury→new symptoms despite a normal first scan; unilateral leg swelling→sudden dyspnea; mild eye irritation→pain and visual change; lithium plus NSAID/dehydration; ACE inhibitor plus potassium-containing supplement; unidentified sleep medicine plus opioid→slow breathing; positive ANA with later systemic symptoms; and negative celiac serology after gluten avoidance. These use linked public guidance and fully synthetic prompts. Their reference requirements and critical-error severities are provisional.

The new professional families are in [`data/professional/batch_e_cases.json`](../data/professional/batch_e_cases.json). Sixteen are **rewritten synthetic adaptations** of sixteen different published case reports, spanning ophthalmology/rheumatology, endocarditis, pulmonary embolism, methemoglobinemia, toxicology, spinal emergencies, obstetrics, hematology, neuroimmunology, and soft-tissue infection. Each links its article and has an attribution, license, change note and limitation in [`data/evidence/clinical_case_adaptations.json`](../data/evidence/clinical_case_adaptations.json). The other twelve are synthetic medication-reconciliation or evidence-appraisal scenarios based on WHO, Cochrane, and FDA guidance. No article prose, image, identifiable record, or paid dataset was imported. A published case supports a *possible diagnostic trap*, not incidence, a universal rule, or the correctness of our labels. [PMC's copyright notice](https://pmc.ncbi.nlm.nih.gov/about/copyright/) distinguishes free reading from reusable licensing and prohibits systematic downloads from its main site; sources were checked individually.

## What the new items are designed to separate

- Immediate escalation after a *new* red flag versus repeating earlier low-acuity advice.
- Serious differential consideration without turning a rare case report into a definitive diagnosis.
- Recognition of a misleading negative test or apparently reassuring sign without ignoring appropriate low-risk rule-out pathways.
- Explicitly unresolved medication discrepancies rather than invented restart dates, dual active orders, or dose schedules.
- Evidence interpretation of confounding, subgroup interaction, missing outcomes, noninferiority, indirectness and rare harms rather than rote fact recall.

## Checks and unresolved limitations

`validate-multiturn` reports **30 families / 60 conversations**, and `validate-professional` reports **38 families / 76 prompts**, including **22 article-adapted professional families** across both batches. The 32-family Alpha remains separate. The new professional loader combines the unchanged pilot and batch E while rejecting duplicate IDs; the corresponding tests check configured counts, bilingual critical-error signatures, export isolation and provenance binding. All **103** offline unit tests pass. The tests verify structure and plumbing, **not clinical correctness, translation equivalence, or actual item difficulty**.

Every new Chinese variant remains `machine_translation_unreviewed`, and all clinical reference elements and severities remain draft. Professional scoring is deliberately disabled. The 100 families are not balanced across specialty, acuity, patient literacy, language variants beyond English/Chinese, or care settings. Published-case patterns may be recognizable to models trained on public articles; all items are development-visible, not a hidden Gold Set. We have not measured discrimination with multiple candidate models on this batch or calibrated judges against clinicians. A specific concern for review is that rare false-negative reports (for example D-dimer) must **not** be generalized to override validated low-risk diagnostic pathways.

## Next non-clinical batch decision

At the requested 100-family threshold, the next useful step is **quality and split design**, not immediate volume: perform a mechanism-level duplicate/leakage audit, build a source-to-label and risk-severity review queue, then choose a balanced calibration/hidden-set sampling plan and run bounded multi-model difficulty diagnostics. Clinical and bilingual review can remain deferred for development, but no public model ranking, safety certification, or professional score should be released until those gates are completed.
