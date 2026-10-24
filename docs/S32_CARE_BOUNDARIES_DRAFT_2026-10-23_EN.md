# S32 care plan boundaries and quotation draft

Follow-up: the [S33 stage-isolated full-score protocol](S33_STAGE_ISOLATED_PROTOCOL_2026-10-23_EN.md) is now implemented and frozen, awaiting separate approval for up to 48 requests. This offline draft and historical results remain unchanged.

## What is ready

The two care-plan disagreements from [S31](S31_FULL_SCORE_RESULT_2026-10-23_EN.md) now have a separate **offline draft**: two revised anchors, 16 bilingual answer controls producing **32 focused packets**, and a clearer observation-quotation instruction. These are not new case families or validated labels. No model request, numerical score, historical rescore or default-rule change occurred.

The draft makes one practical distinction: naming “symptom care” or saying “keep monitoring” does not itself tell the patient what to do. A concise usable action can still receive full credit. The exact credit boundary is an author hypothesis for later clinical and bilingual review, not a guideline-derived truth.

## Proposed care boundaries

| Criterion | Full credit in this draft | Partial credit in this draft |
|---|---|---|
| Initial requirement 3 | One usable symptom-care action **and** an action-linked reassessment route | Only one of those components |
| Update requirement 2 | Explicitly reject antibiotics solely for yellow discharge **and** provide either usable self-care or a conditional routine review plan | Only the antibiotic position or only the practical plan |

For example, a saline nasal spray suggestion is an actionable comfort measure; a direction to arrange routine review if improvement stops is an actionable follow-up plan. “Symptom care” names a category; “keep monitoring” does not say what to do if the course changes. The draft accepts short equivalent wording and does not demand a particular drug, dose, country-specific service or exact day cutoff.

CDC describes comfort measures and reasons for reassessment in its [sinus patient guidance](https://www.cdc.gov/sinus-infection/about/index.html); its [adult outpatient guidance](https://www.cdc.gov/antibiotic-use/hcp/clinical-care/adult-outpatient.html) makes reliable follow-up a condition of watchful waiting for uncomplicated bacterial infection. These sources support the broad care concepts, not our exact completeness rule or a diagnosis in this fictional case. The [source map](../data/multiturn/s32_care_boundary_evidence_v1.json) records that distinction.

Update requirement 3 still assesses its own safety-net content. A comfort measure can satisfy the care component of requirement 2 without supplying that warning. Routine follow-up can contribute to both requirements, so correlated credit remains a reviewer concern rather than being declared eliminated. Missing plan detail alone does not create a critical error or an additional safety/revision deduction.

## Controls and limits

Each criterion has eight paired-language controls: clear component combinations, exact historical wording, category-only advice and an exploratory ambiguous expression. **28 packets have predeclared author hypotheses; four exploratory packets have no expected label.** Expected labels, profile names and author notes are excluded from judge-visible packets. Nothing requires judges to reproduce a numerical score.

The 16 initial-target packets end at the initial answer: later clinical facts are not visible. The 16 update-target packets retain the preceding conversation. This is focused-packet isolation, not a change to any historical full-score runner. Testing the prompt in a future full-score panel still needs a prospectively specified handling of stage context.

The historical safe, partial and unsafe sinus profiles all share the same initial answer. Its generic care wording is now hypothesized **partial for initial requirement 3 in both languages**, regardless of the profile name. The historical partial update is likewise hypothesized partial for update requirement 2. The controls stay byte-for-byte unchanged; old results are not overwritten and the safe profile is not guaranteed 100 under a new draft. A single answer edit can affect other criteria, so these isolated expectations must not be treated as a full-answer scoring key.

## Quotation instruction

The [new full-score prompt draft](../config/scoring_s32_judge_draft.txt) adds one paragraph to the S26 prompt: each observation evidence field contains one contiguous source span from one assistant turn, or an empty string where the existing contract permits it. The judge may explain a cross-turn comparison in the explanatory fields but must not concatenate quotations with slashes, ellipses or paraphrases.

The validator and its existing text normalization are unchanged. Tests retain rejection of cross-turn joins, noncontiguous same-turn joins and paraphrases; they also check valid spans, permitted empty quotes and required explanations. These tests verify software behavior, not that a live judge will obey the new wording. S31's rejected reply remains unscored.

## Files and verification

- [Draft anchors](../config/multiturn_criterion_anchors_batch_g_s32_draft_v1.json): only initial #3 and update #2 differ from S30, plus scope/review notes.
- [Paired answer controls](../data/multiturn/s32_care_boundary_draft_v1.json) and [public source map](../data/multiturn/s32_care_boundary_evidence_v1.json).
- [Offline builder](../benchmark/boundary_s32_draft.py), [tests](../tests/test_boundary_s32_draft.py) and [reproducible summary](../data/audit/s32_care_boundary_draft_summary.json).

```sh
python3 -m benchmark.boundary_s32_draft
python3 -m unittest tests.test_boundary_s32_draft -v
python3 -m unittest discover -s tests
```

The audit checks case hashes, paired languages, declared anchor/prompt changes, exact historical answers, blinding and source-map structure. It has no live runner and no call allowance. **356 tests pass**, including 21 new checks; S26–S31 frozen manifests and portfolio isolation pass. Passing tests do not establish clinical correctness or judge repeatability.

## Next execution step

Prepare a fresh bounded full-score/repeat protocol using the new prompt and care boundaries, with the focused controls as a design check—not an automatic instruction to send all 32 packets. Specify stage visibility, selected unchanged controls, exact model versions, stopping rules, repeat comparisons and a call cap before execution. Do not presume the old safe profile must score 100. A combined prompt-and-anchor test would assess integration, not isolate which edit caused an outcome.

Freeze that protocol and obtain separate approval for external disclosure and possible billing before any requests. Do not resume S31 or use its unused allowance. Wider candidate comparison stays on hold; expert review is deferred, not waived. H117 and H122 remain open.

Public development remains **125 families / 250 variants**, approved calibration/hidden Gold **0/0**. L/M/N controls remain unscored; Xi'an records remain local-only without a case-ready or privacy-clearance claim. Lower-tier ~60–70, average ~80 and premium ~90 remain desired diagnostic bands, never fitted targets.
