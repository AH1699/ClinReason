# Living human-review handoff — opened 2026-10-07

Purpose: preserve unresolved questions while the synthetic benchmark is developed. This queue is not an approval record. All items are **open**; an AI preliminary audit cannot close them. For source links and case-level context, see the [preliminary audit](PRELIMINARY_CLINICAL_REVIEW_EN.md) and [public evidence registry](../data/evidence/public_sources.json). Do not add patient-level data to this repository.

## Priority decisions

| ID / priority | Cases | Reviewer needed | Decision to document | Current uncertainty |
|---|---|---|---|---|
| H01 / high | REASON-002 EN + ZH | Laboratory medicine / clinical safety | How should an unidentified “high” result be safety-netted when critical values may be asymptomatic? | Current reference says urgent escalation **only** with concerning symptoms. No test-specific threshold can be inferred from the prompt. |
| H02 / high | MEDSAFE-002 EN + ZH | Prescriber and pharmacist | What should a model say if the next dose is imminent, lists conflict, or a high-risk drug is involved, without reconciling itself? | “Prompt” professional reconciliation may be too vague. |
| H03 / high | REASON-001 EN + ZH | Urgent-care / primary-care clinician | Which dizziness red flags and urgency levels are essential and valid across settings? | Existing WHO source is general diagnostic-safety guidance, not a dizziness-specific rule. |
| H04 / high | MEDSAFE-001 EN + ZH | Prescriber/pharmacist + bilingual reviewer | Harmonize severe-reaction/overdose escalation and decide which missing details are essential. | Chinese reference is more prescriptive than English; broad WHO source does not set a complete field list. |
| H05 / high | All 12 ZH-HANS cases | Qualified bilingual healthcare reviewer | Confirm clinical meaning, urgency, tone, critical-error scope, and culturally neutral terminology against English. | All are marked `machine_translation_unreviewed`; no language approval exists. |
| H06 / high | All 24 cases | Qualified clinicians within relevant scopes | Review exact prompts, reference answers, critical requirements/errors, source adequacy, and false-positive/false-negative scoring risk. | No human clinical approval exists; public guidance is not case validation. |
| H07 / medium | TRIAGE-001/002 | Emergency / acute-care clinician | Define jurisdiction-neutral urgency, transient stroke symptoms, onset-time wording, and whether transport advice is scored. | Emergency numbers and pathways differ; some details may be local-pack material. |
| H08 / medium | COMMS-001/002 | Screening/diagnostic-safety clinician | Specify follow-up ownership and safety-net expectations without inventing a universal timeframe. | Current “concerning” and “appropriate follow-up” language may be hard to score consistently. |
| H09 / medium | ADV-001 | Prescriber/pharmacist | Decide whether missed dose, overdose and severe reaction need separate cases and acceptable responses. | Current case has no medicine identity; no exact dose can be safe. |
| H10 / medium | ADV-002 | Health privacy specialist | Define prohibited re-identification attempts, quasi-identifier handling, and response to claimed consent. | Existing WHO ethics source is broad; direct privacy evidence is needed. |
| H11 / medium | KNOW-001/002 | Clinical guideline / implementation specialist | Separate model behavior from organizational approval, and specify what general screening principles can be given. | Local approval may be a release-process gate rather than a model-answer requirement. |
| H12 / medium | All families | Clinical methodologist + statistician | Check source-to-exact-rule mapping, critical-error sensitivity/specificity, and adjudication protocol. | Principle-level sources may not justify precise scoring triggers. |

## Decisions before external benchmark claims

- Resolve the discrepancy between the current Alpha minimum of **one** independent clinical approval per case (`config/benchmark.json`, `docs/REVIEW_WORKFLOW_EN.md`) and the design document's **two-clinician** expectation for stronger validation. Adopt and document an explicit Gold/public-release policy before promotion.
- Recruit verified, conflict-screened clinicians and a qualified bilingual reviewer **before** treating the reference answers as ground truth or publishing comparative model scores. Waiting until immediately before product launch would allow uncertain rubrics to influence development and reported rankings; a staged review now, with final re-review of changed cases before release, is safer.
- Keep all human decisions in the append-only `data/reviews/` workflow, bound to exact case hashes. Store AI audits under `work/preliminary_reviews/` or in these documents; they never count as approvals.
- Recheck public sources at each substantive case revision and before release. Record the guideline edition, effective date, applicability, and any conflicting evidence. Published cohort rates and US-specific pages are not global prevalence or pathway rules.
- Establish whether benchmark results are for internal research only or public comparison, and document the intended geography/language population and exclusion of clinical deployment. A global benchmark tests transferable safety behavior; local clinical procedures belong in jurisdiction packs.

## Closure rule

For each item, the assigned human reviewer should record a dated decision, rationale, sources, scope/jurisdiction, requested case changes, and any dissent. Meaning-changing case edits require version increment and repeat review. A reviewer may decide an item is not applicable, but that decision must be explicit; this note should not be silently deleted.
