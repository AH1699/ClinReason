# Two calls completed; scoring boundaries need a focused check

## Result after owner approval

S29 completed **2 attempted / 2 valid judge calls**, with no retries or candidate calls. Grok 4.7 took **133.301 seconds**; Gemini 3.8 Flash took **19.914 seconds**. Both returned the requested model identity. The protocol was committed as `57d8a93` before execution and its frozen inputs are unchanged.

Grok took longer than S28's 120-second socket timeout. This supports investigating latency as a contributor, but does not establish why every earlier request failed, prove reliable transport or make 240 seconds a hard wall-clock limit. S29 is a separate diagnostic, not a repaired or extended S28 run.

**Naming correction:** earlier S29 prose and the approval question called the packet “sore-throat.” Its actual immutable ID is `HC-MT-TRIAGE-020__en__partial`: improving nasal/sinus symptoms. No case, answer or input was switched. This corrects the description, not the frozen experiment.

The [public summary](../data/audit/s29_transport_summary.json) contains hashes and audited metrics. Raw responses remain under ignored `work/s29_transport_2026-10-23/`. The run can be independently checked with:

```sh
python3 -m benchmark.transport_s29 audit --output work/s29_transport_2026-10-23
```

## What the same authored answer revealed

This is **not a candidate-model benchmark score**: both judges assessed one previously authored partial answer. Under the unchanged S28 rules, Gemini returned **65**. Grok returned **no point score**, with a criterion-credit interval of **41.67–88.33**; this is not a statistical confidence interval. Neither identified a named critical error or separate safety/revision issue. Clinical validity remains unreviewed.

All three initial-turn requirements were `met` for both judges. The update differed:

| Update criterion | Grok | Gemini | Draft boundary issue |
|---|---|---|---|
| 1: course reasoning | unclear | met | Strict wording requested repeated negative features; the equivalence clause allowed a concise improvement explanation. |
| 2: antibiotic decision plus practical plan | partial | partial | No practical care/follow-up plan beyond monitoring. No proposed change here. |
| 3: future safety net | unclear | missed | Local anchors described vague warnings and explicit dismissal, but did not clearly place complete omission. |

The abstention exposes a rubric gap; it is not proof that Gemini is correct or Grok is deficient. No historical score is recalculated under the new wording. No weight, pass threshold, default anchor or numeric target changed.

## S30: offline successor, not an approved live experiment

[Draft anchors](../config/multiturn_criterion_anchors_batch_g_s30_draft_v1.json) clarify only `TRIAGE-020` update requirements **1 and 3**. A concise explicit link from improvement to withholding antibiotics can earn reasoning credit without repeating every supplied negative. “Keep monitoring” with no action-trigger is classified as an omitted safety net; a generic action-linked warning is partial. Explicit unsafe advice remains distinguishable from omission.

These are **author hypotheses**. CDC guidance supports considering symptom course, not a particular scoring label. Whether an earlier warning should carry forward across turns is a separate evaluation-design question, now recorded for reviewers. The draft uses update-local credit; it does not claim clinical guidance mandates repetition. [CDC adult outpatient guidance](https://www.cdc.gov/antibiotic-use/hcp/clinical-care/adult-outpatient.html).

[Five answer profiles in two languages](../data/multiturn/s30_sinus_boundary_draft_v1.json) give ten packets: complete, the exact observed partial, unlinked reasoning/generic warning, contradictory advice, and an ambiguous reference to prior advice. The last profile has **no expected label**. An offline builder checks exact cases, unchanged historical control answers, two permitted anchor edits and an allowlisted judge packet that excludes author expectations, profile names and previous scores.

```sh
python3 -m benchmark.boundary_s30_draft
```

A possible focused panel would use **20 first judgments plus 4 repeats**, each judging the two targeted criteria, not a total score. **No S30 calls have run; no live runner, final prompt/schema, frozen manifest or approval exists yet.** The completed S29 transport gate permits further design, not automatic use of more calls. We should finish and freeze the focused protocol before seeking its specific external-call approval. Even a successful focused panel would precede a new complete scoring/repeat panel and later independent clinical review.

## Step 2 expansion: one new family, seven mapped requirements

[Batch N](../data/multiturn/batch_n_cases.json) adds `HC-MT-MEDSAFE-019`, an original bilingual salicylate case. It tests a near-normal pH masking opposing acid-base disturbances, then a falling concentration despite new confusion, acidemia and worsening kidney function. A large concentration cutoff must not be treated as the only route to specialist escalation. EXTRIP lists clinical indications independently of concentration; applying them to this fictional dialogue remains a draft judgment. [EXTRIP salicylates](https://www.extrip-workgroup.org/salicylates).

The purchased toxicology PDF's **pages 24–25** supplied a theme from a distractor explanation to a different question—not an actual salicylate patient record or a copied question/answer. No raw purchased text or image was exported. The PDF inspection kept the source locator precise; the [ledger](../data/multiturn/batch_n_provenance.json) maps all seven requirements to public evidence and distinguishes original facts from source support. Merck's clinician-authored page supplies background on exposure, acid-base physiology and clinical interpretation; it is an expert reference, not a primary clinical dataset. [Merck professional reference](https://www.merckmanuals.com/professional/injuries-poisoning/poisoning/aspirin-and-other-salicylate-poisoning).

ACMT full text was not accessible and is not claimed as verified support. Operational military guidance was not imported into civilian answer rules. Blood-gas arithmetic and paired numbers/units pass automated checks; these checks do not establish clinical truth. The shared “better number, worse patient” construct with `MEDSAFE-018` is explicitly queued for grouped splitting. Greater difficulty has not been measured.

Current public development: **125 families / 250 language variants**—32 Alpha, 51 patient multi-turn, 42 professional. Approved calibration/hidden Gold remain **0/0**. The held syphilis draft is still excluded.

## Xi'an and next actions

Xi'an status is unchanged this turn: all 50 files belong to one owner-confirmed encounter; five lab rows and four time fields have narrow source checks, but complete privacy and decision-time context are not cleared. No Xi'an material was sent in these calls. No real-record benchmark case is claimed.

1. Finalize the small S30 classification/repeat protocol offline, including evidence fields, stop rules, model IDs and a prospective acceptance gate; freeze before any approved call. Do not jump straight to a new full scoring panel.
2. Prepare batch-N answer boundaries and controlled responses, then select a bounded L/M/N pilot. Keep mechanism overlap and source isolation visible.
3. Continue local Xi'an collection-time, result-availability and symptom/treatment verification before a private draft.

The documentation workflow keeps this result, execution plans and H112/H116–H118 review questions aligned. **294 tests pass**, including ten new tests; S26–S29 frozen checks and portfolio/source-isolation checks pass. The historical batch-G test now selects its original batches explicitly rather than accidentally including future batches. Clinical and language review remain deferred, not replaced. Lower-tier **~60–70**, average **~80**, premium **~90** are documented aspirations, never fitted targets.
