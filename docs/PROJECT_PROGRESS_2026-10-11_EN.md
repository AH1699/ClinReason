# Project progress — 2026-10-11

This is an engineering and authoring status log, **not** a clinical quality claim. Qualified clinical and bilingual review is intentionally deferred, as requested; all Alpha cases remain drafts.

## The four non-clinical gaps addressed in this iteration

| Track | Implemented | Still open |
|---|---|---|
| Coverage and difficulty | `coverage-audit` now checks exact bilingual families, family splits, audience, interaction mode, triage acuity, and author-assigned reasoning/complexity tags. All 30 public families are explicitly development-only. | No observed difficulty/discrimination study. No genuine multi-turn or clinician-facing cases. Routine/self-care triage absent; some advanced tags have one family only. |
| Judge validity | Four synthetic EN good/unsafe contrast pairs target configured severity-3 errors. `judge-contrast-gemini` is an opt-in dry/live diagnostic and reports error detection separately from score ordering. | No live contrast run or clinician-adjudicated calibration set yet. These pairs are provisional and cannot validate the judge or replace independent reviewers. |
| Reporting | Reports now include family-level means, paired EN/ZH scores and gaps, complete-pair counts, and category means using family as the unit. Legacy prompt-level summaries remain for compatibility. | No justified uncertainty intervals or ranking: selected, unreviewed cases and uncalibrated judging cannot support inference. |
| Reproducibility | Candidate manifests now record prompt-input/instruction hashes, exact case revisions, actual `store: false` parameter, provider-default sampling, config/rubric hashes, returned model, time, and git state when invoked through the CLI. Removed false temperature/top-p/seed claims from config. | Provider aliases and default sampling limit replay. Raw provider payloads are not retained; failed full candidate runs are not resumable. Judge-prompt provenance and immutable provider snapshots need stronger handling. |

## Current evidence and interpretation

The configured set is 30 bilingual families (60 prompts), five per category. All 30 are patient-facing and single-turn; triage has four emergency and one timely nonemergency family. The 24-prompt live pilot used an earlier snapshot and a single uncalibrated Gemini judge; its high score is a **ceiling warning**, not proof that models find these cases easy. We need controlled weak/strong candidate responses and, later, qualified human ratings to establish discrimination. The contrast pairs check only obvious judge sensitivity, not model difficulty.

The [coverage roadmap](COVERAGE_ROADMAP_EN.md) remains valid. A timeline narrated in one prompt does not test adapting to new turns; a conflict described in one prompt does not establish expert-level clinical reasoning. The author tags are design hypotheses. Counts are not quality weights and must not be pooled into an “expert clinician” score.

## Next engineering sequence while case expansion continues

1. Build a **separate multi-turn case contract and runner** with explicit turn order, state changes, and scoring of the final response in context; add at least one deliberately controlled reversal pair. Do not squeeze turns into the existing single-string prompt field.
2. Draft a small, source-traceable advanced batch that fills routine/self-care triage and repeated probes of competing risks, longitudinal provenance, and evidence applicability. For every family, specify which plausible wrong answer it separates from a safe answer. Keep these in development and version meaning-bearing edits.
3. Run the four contrast pairs against the selected judge only after reviewing cost and output paths, then compare against known flawed and strong **candidate** answers. Record failures; do not tune only to these public pairs.
4. Define the future calibration and hidden Gold acquisition protocol, independent reviewer counts, and statistical analysis plan before public model comparisons. Public development cases cannot be relabeled hidden retroactively.

The [case authoring guide](CASE_AUTHORING_GUIDE_EN.md) and [human-review handoff](CLINICAL_REVIEW_HANDOFF_EN.md) remain the source of release gates. No clinician-facing or jurisdiction-specific score should be merged with Global Core.

## Multi-turn pilot addendum

The next engineering step has now been implemented as a **separate** four-family/eight-variant two-turn pilot, not a rewrite of the single-turn Alpha. Its contract, staged runner, content-bound judge packets, provisional gated rubric, and controlled judge contrasts are described in [the pilot report](MULTITURN_PILOT_2026-10-11_EN.md). The two-turn English and Chinese Grok→Gemini smoke runs completed; each received an unvalidated 100/100. The judge detected and penalized all four deliberately obvious unsafe English updates (4/4 error detection and ranking). These results establish workflow and obvious-error sensitivity only; the ceiling and expert-difficulty questions remain open. The next significant batch choice is nuanced patient-facing multi-turn expansion versus a separate clinician-facing track.

## Batch C addendum

The patient-facing expansion choice was implemented in a [separate batch C file and coverage note](MULTITURN_BATCH_C_2026-10-11_EN.md): 12 more bilingual draft families, bringing the multi-turn development track to 16 families / 32 conversations. The original four-case pilot and the 30-family/60-prompt single-turn Alpha are unchanged. The CLI now merges versioned multi-turn batch files and rejects duplicate family IDs. Five new English-only safe/partial/unsafe update triplets extend the judge diagnostic; a local fixture verifies the three-level scoring path. On 2026-10-12, the provisional Gemini judge ranked all five triplets as intended and detected all five overt unsafe errors; one matched Grok English/Chinese candidate conversation received provisional 100/100 in both languages. These are small unreviewed diagnostics, not validation or a difficulty estimate. Clinical review, language review, human calibration, and a held-out Gold set remain open.
