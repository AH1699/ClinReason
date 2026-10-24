# S35 Quotation instructions and candidate answer boundaries

## What is ready

This offline batch adds clearer evidence instructions, **46 bilingual test packets** and a checked shortlist of three harder reasoning families. It makes **zero API calls**, changes no historical score and leaves default scoring untouched. The previous [S33 control pass and S34 MiniMax stop](S33_S34_RESULTS_2026-10-23_EN.md) remain exactly as recorded.

The 46 packets are test inputs built from 23 authored response profiles, not 46 new cases. They cover 64 target-criterion instances: **44 author hypotheses and 20 exploratory instances without expected labels**. They do not establish clinical truth or model difficulty.

## Quotation instructions without weaker validation

New [initial](../config/scoring_s35_initial_judge_draft.txt) and [update](../config/scoring_s35_update_judge_draft.txt) prompt drafts add only one paragraph to their S33 counterparts: each criterion quote must be a single contiguous passage from the matching assistant turn. Inserted ellipses, joined passages and paraphrases remain invalid even when the separate pieces occur in the answer. A literal ellipsis already in the source passage is allowed.

**54 bilingual formatting checks** exercise the existing validator: 22 accepted inputs and 32 rejected inputs, all matching the declared contract. They cover literal passages, existing formatting normalization, literal versus inserted ellipses, slash joins, invented text, user text, wrong-turn text and empty quotes. Criterion evidence remains stage-local. Update safety/revision observations retain their existing ability to quote either visible assistant turn; required explanations still apply.

The validator and output schema are unchanged. These tests demonstrate software behavior, not that a judge will obey the new instruction. S34's rejected Gemini reply is neither repaired nor scored.

## What the new boundary controls test

The [draft labels](../config/multiturn_criterion_anchors_batch_g_s35_draft_v1.json) change only **three initial-stage anchors**: red-eye requirements 1/2 and sinus requirement 2. Other anchors, case wording, weights and critical errors are preserved. A [separate focused prompt](../config/s35_boundary_judge_draft.txt) is available for future classification experiments, but there is no live runner.

| Response pattern | Proposed interpretation, not a clinical rating |
|---|---|
| Direct question or explicit “please tell me whether…” | Same elicitation function; no question mark required |
| Explanation or warning without an invitation to answer | Relevant but incomplete history elicitation |
| “Contact lenses AND light sensitivity” | Does not independently establish each fact |
| Explicitly using a duration already supplied | Can avoid repeating the same question; unknown facts still need checking |
| Vague reference such as “clarify that pattern” | Exploratory; no fixed expected label |

Fourteen paired contrasts change only one declared text component in each language; the checks reject unrelated component edits. This isolates wording changes, **not necessarily one clinical effect**. Red-eye initial requirements 1/2 still overlap in their risk checks, so the draft is not promoted to default scoring.

Initial packets exclude later clinical facts. Update packets retain the earlier context, but author profile names, hypotheses, alternative interpretations and notes are never included in the judge input. These are newly authored controls, not edited MiniMax replies. No historical candidate answer is reclassified.

### A requirement and its anchor disagree

The existing red-eye update requirement asks for self-care **or** routine follow-up; its full-credit anchor asks for care **and** follow-up. This is a real internal mismatch, beyond ordinary judge disagreement.

All **14 follow-up packets** therefore retain null expectations. The old anchor is unchanged; competing OR/AND interpretations are recorded outside the judge packet. The examples distinguish care alone, follow-up alone, both, recurrence-only advice, generic recurrent bleeding, urgent red flags and vague review wording. Neither source evidence nor a future judge majority can silently settle the intended benchmark construct.

A later decision must align the requirement and anchor in a new version. Until then, this target cannot serve as a new expected-label advance gate; no earlier result is rescored. H125 records the mismatch, elicitation boundaries and duplicate-credit concern for later methods/clinical/bilingual review.

## Public evidence and its limits

The [evidence ledger](../data/multiturn/s35_candidate_boundary_evidence_v1.json) maps risk features and conditional routes to [NHS red-eye guidance](https://www.nhs.uk/symptoms/red-eye/), ordinary care and recurrence review to the [Moorfields leaflet](https://www.moorfields.nhs.uk/ae/patient-guides/subconjunctival-haemorrhage), and severity/course clues to [CDC adult outpatient guidance](https://www.cdc.gov/antibiotic-use/hcp/clinical-care/adult-outpatient.html).

These sources support clinical subject matter, not exact credit, elicitation grammar, OR-versus-AND requirements or bilingual equivalence. The Moorfields page displays a November 2021 review date; it is not treated as a newly validated standard. UK service names and US prescribing guidance are not converted into universal country-specific requirements. Expert review remains deferred, not waived.

## Harder families selected for the next design

The [shortlist](../data/audit/s35_harder_panel_shortlist.json) binds current case, answer-control and anchor files by hash. It selects existing public development drafts, not new or clinically approved cases.

| Family | Mechanism to test |
|---|---|
| L: `HC-MT-REASON-020` | Interpreting apparently reassuring joint-fluid findings when the clinical picture worsens |
| M: `HC-MT-REASON-022` | Recognizing a test limitation after new information about IgA deficiency |
| N: `HC-MT-MEDSAFE-019` | Reconciling a falling drug concentration with worsening clinical and laboratory findings |

These are intended to broaden reasoning demands; their actual difficulty is unmeasured. The N unsafe control changes several linked components, so it is not a single-criterion intervention. Shared initial judgments also make profile totals dependent.

A proposed two-language, two-judge control design would use **72 requests**: 12 shared initial judgments, 36 update judgments, 12 repeated initial judgments and 12 repeated partial updates. Gemini 3.8 Flash and Grok 4.7 are proposed from the prior configuration, without a current availability guarantee. A separate MiniMax M2.7 extension would use **36 requests**: 12 candidate turns and 24 stage judgments across six conversations. MiniMax remains a candidate; it is not excluded or made a judge.

**These are estimates, not approved allowances.** No new panel is frozen, and no live runner is implemented. Two selected families have four update requirements, whereas S33 and these additive S35 stage prompts still describe three; the broader protocol needs newly versioned prompts, schema and integration rather than a path substitution.

Next: verify selected source-to-answer mappings and contrast hypotheses, implement variable-criterion integration and stopping/repeat checks, then commit a frozen protocol and seek approval for its disclosure and call budget. The held red-eye OR/AND target stays out of that harder-family gate. The possible MiniMax extension remains a separate decision, not an automatic continuation.

## Verification and project status

The [offline audit](../benchmark/boundary_s35_draft.py) reproduces the [saved summary](../data/audit/s35_candidate_boundary_draft_summary.json). **420 tests pass, including 25 new tests.** They check packet isolation, historical bindings, the three-edit limit, held expectations, one-component contrasts, prompt deltas, quotation behavior, source mappings, shortlist hashes, budget arithmetic and zero-network/zero-scoring behavior. S26–S34 frozen checks and portfolio checks remain intact.

```sh
python3 -m benchmark.boundary_s35_draft
python3 -m unittest tests.test_boundary_s35_draft -v
python3 -m unittest discover -s tests
```

Public development remains **125 families / 250 variants**, approved calibration/hidden Gold **0/0**. Xi'an and purchased raw records remain local-only; this batch does not claim privacy clearance or add a real-record case. Lower-tier ~60–70, average ~80 and premium ~90 remain documented aspirations, never targets for fitting scores.
