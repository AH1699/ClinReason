# A bounded test of medication scoring boundaries

The focused judge runner is implemented and frozen for **28 authored packets judged twice, at most 56 Gemini 3.8 Flash requests**. No live request has been made. This is the next scoring task in the execution plan, not a new benchmark direction. It checks whether the judge applies the existing medication requirements consistently before broader model comparison.

## Scope and fixed inputs

Use the [S49 English/Chinese drafts](S49_MEDICATION_BOUNDARIES_EN.md) on `HC-MT-MEDSAFE-013`. They target only initial criterion 2 or update criterion 3. Sixteen packets have provisional author hypotheses; twelve remain unlabelled. The [runner](../scripts/medication_boundary_s50.py) does not change their wording, existing anchors, score arithmetic, previous results or dataset counts.

The [freeze](../config/medication_boundary_s50_frozen_v1.json) binds packets, request order, prompt, schema-generating code, tests and the historical dependency chain. Protocol SHA-256: `f994eae382aa615718a77f9f1ac5c5d3f0ef6bbdd68031cff7dd054494d3949f`. [Configuration](../config/medication_boundary_s50_v1.json) and [judge instruction](../config/medication_boundary_s50_judge.txt) are available for inspection.

Each packet is judged on its own. The outgoing request contains no profile name, author expectation, previous judgment or candidate-model identity. Initial judgments cannot see later turns; update judgments see context but must cite their current answer. Requests are ordered by packet hash, first all 28 initial judgments, then the exact same 28 request bodies as repeats. There is no conversation memory between calls.

All calls use a 32,768 combined output/thinking allowance and medium thinking. Other sampling settings remain provider defaults, not pinned deterministic behavior. Gemini is the sole judge for this continuity experiment; Grok access remains a separate unresolved issue, not a clinical zero. No candidate answers are generated, no private or purchased material is sent, and no numeric benchmark score is produced.

## What a valid judgment contains

Exactly one classification: `met`, `partial`, `missed` or `unclear`, the targeted requirement index, a current-stage evidence quote and a concise rationale. Quotes must be a contiguous span under the existing normalization rules. `met` and `partial` require nonempty evidence; an absence-based `missed` or `unclear` may have an empty quote. An unresolved anchor boundary should remain `unclear`, not be invented away.

The runner rejects wrong models, incomplete replies, duplicate JSON keys, extra or missing fields, wrong requirement indexes and invalid quotations. Raw replies and usage are saved before acceptance. A valid disagreement is retained and the fixed schedule continues; it is never a reason for repair, retry or early selection of favorable results.

## Predeclared analysis

| Measure | Fixed denominator | Interpretation |
|---|---:|---|
| Accepted judgments | 56 | Technical completion, not clinical correctness |
| First-pass agreement with author hypotheses | 16 | Agreement with provisional developer expectations |
| Exploratory first-pass classifications | 12 | Describe interpretations; no expected “correct” status |
| Exact status repeatability | 28 pairs | Same classification; does not prove identical rationale |
| One-component contrasts | 22 pairs per pass | Keep both statuses visible, including missing cells |
| English/Chinese comparisons | 14 pairs per pass | Descriptive language differences, not adjudicated equivalence |

The narrow author-boundary gate requires all 56 judgments, 16/16 author matches and 28/28 status repeats, with all twelve exploratory packets retained outside the agreement denominator. Missing results never reduce the expected denominator. Exploratory results cannot become labels merely because a model repeats them. No accuracy against clinical gold, model ranking, full-score calibration or adoption permission follows from passing.

## Spending and approval

Proposed policy: **$3.00 recorded-spending stop threshold, with possible final-request overrun**, not a guaranteed ceiling or a forecast of cost. Fresh approval must cover up to 56 billed Google requests containing these public synthetic cases, authored answers, labels and judge instructions. The previous one-call S49 approval is consumed and cannot be reused.

A fresh private run directory, protocol-specific one-use lock and authorization receipt precede dispatch. Stop at the first transport/validation failure, unknown charge, spending threshold or request limit. No automatic retry, resume or reuse of unused allowance. Known estimated spending and unknown-charge attempts stay separate. Replay reconstructs accounting and classifications from captured bytes; no failed output is repaired.

Offline verification commands:

```sh
python3 -m scripts.medication_boundary_s50 audit
python3 -m unittest tests.test_medication_boundary_s50 -q
```

These commands do not load credentials or contact providers. The 29 new tests use fake transport; their passing does not predict actual judge agreement. The full offline suite passes 844 tests. Historical freezes and the 125-family portfolio remain intact; the two standalone Batch O drafts also pass their structural audit.

## Exit decision and return to the main plan

Run this prospective experiment at most once under its authorization, then publish one evidence-based disposition. If the narrow gate passes, carry that evidence into the nine-family panel's design while keeping unlabelled boundaries open. If it fails, identify the affected requirement or technical fault and propose a specific versioned remedy or exclusion from comparative claims. Do not silently adjust labels, keep calling until results agree, or start a new experiment without an explicit decision and new authorization.

Neither outcome blocks offline case authoring or implementation of the nine-family mixed saved/new-answer scheduler. Resume the next case-expansion task by examining Batch O's acceptable alternatives and bundled requirements, then selecting new public-report/Step-2-informed decision mechanisms. Expert review remains later; approximately 60–70 / 80 / 90 are difficulty diagnostics, not fitting targets. See the [current milestones](PROJECT_EXECUTION_PLAN_2026-10-16_EN.md).
