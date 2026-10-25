# Nine family scheduling and Batch O wording review

The mixed saved/new-answer scheduler now works **offline**. It verifies the existing 16 answer stages for reuse, plans only the other 128 generation requests and keeps all 72 conversations visible, including the eight medication conversations under review. No paid call, new model score or case-label change occurred.

The [implementation](../scripts/mixed_panel_s51.py) deliberately has no live-run command, credential loading or HTTP path. Its supplied-response rehearsal is in memory; durable capture/replay and a new prospective protocol are still required before execution. The [readiness record](../data/audit/s51_mixed_panel_readiness.json) is a snapshot of verified inputs and planned work, not a live-run freeze or completed benchmark.

## What is now verified

The saved S45/S46 bank is reconstructed through its existing raw-capture replay and checked against S48's pinned hashes. All 16 stages match their case versions, language, model, answer hash and reconstructed candidate request, including the exact prior answer in each follow-up. Missing or incompatible imports cause an error; they are not silently regenerated.

This compatibility is against the current version. If a later label edit changes a case-content hash even with unchanged user text, it needs an explicit versioned compatibility decision; S51 does not silently rebind old answers to a new case hash.

| Planned work | Requests |
|---|---:|
| Existing answer stages reused | 16, with no new request |
| New candidate answer stages | 128 |
| Judge controls | 36 |
| First-pass candidate stage judgments | 144 |
| Identical-payload repeated stage judgments | 144 |
| Total proposed new requests | 452 |

The nine families and four Gemini/MiniMax candidate versions are unchanged. All expected **72 conversations / 144 answer stages** stay in the manifest. Missing stages are not scored as zero or removed from the denominator. `MEDSAFE-013` remains review-held for comparative claims, with no reweighting; S50's failed gate and all historical scores remain intact.

The offline judge draft uses S47's observation-completeness instructions/schema and a uniform 32,768 output/thinking allowance with medium thinking. Candidate settings remain the original S38 settings so saved requests remain compatible. These are rehearsal settings, not an adopted clinical rule or newly authorized protocol. S50's “or/both” and ambiguous-reference questions still need explicit versioned treatment before the next judging freeze.

The new tests exercise missing/duplicate/misbound imports, changed follow-up history, no repeated generation, stage isolation, failed control gates, identical repeat payloads, closed model lanes, unknown accounting, simulated threshold overrun and failure without retry. Fixture answers and judgments are mechanical test data, not observed model performance. The inherited accounting policy still treats out-of-scope usage as unknown; current prices must be checked again before any new paid run.

## Batch O review completed at the wording level

The [criterion-by-criterion record](../data/audit/batch_o_boundary_review_s51.json) covers all **12 positions / 24 language-specific requirements**. Its [auditor](../scripts/batch_o_boundary_review_s51.py) binds every note to the current requirement/anchor hashes and rejects stale or missing entries. It does not rereview medical evidence or approve clinical labels.

Two decisions need explicit wording before constructing further controls:

- **Heart-failure update criterion 3:** full credit lists individual symptoms, while partial credit is framed around broader renal/perfusion and respiratory groups. Decide whether every example is mandatory or whether group coverage is enough. Omitting confusion alone is a useful unlabelled contrast.
- **Nutrition update criterion 3:** distinguish actually giving a family-administered replacement dose from simply omitting a “do not dose it yourself” disclaimer. Also preserve the existing allowance for assessed continuation or a temporary hold with reassessment/recovery; neither should be rejected solely for naming a different supervised option.

The remaining ten entries specify component-omission or acceptable-alternative controls, including grouped monitoring, already supplied information, uncertainty and overlapping requirements. These are a concrete authoring queue, not new cases, resolved clinical judgments or new score deductions. Batch O's two families remain standalone and unchanged.

## Next deliverables

1. Add durable per-job capture and independent replay around the mixed schedule, then test interruption, restart refusal and accounting against saved bytes. Reuse the existing 16 answers, not their old scores.
2. Draft separate-version wording and bilingual controls for the two Batch O decisions, then the other component/alternative checks. Select the next distinct public-report/Step-2-informed mechanism from coverage gaps rather than adding more variants of this medication case.
3. Before any paid run, settle the uniform judging contract and held-item reporting, verify prices, freeze inputs and obtain a new bounded budget/authorization. The proposed 452 requests have no approved spending allowance.

Registered coverage remains **125 families / 250 variants**, plus two standalone Batch O families. Expert review stays later, approved calibration/Gold remain 0/0, Xi'an stays local and the longer-term target remains at least 500 distinct families. The 60–70 / ~80 / ~90 score bands remain diagnostic aspirations, not tuning targets.

Offline commands:

```sh
python3 -m scripts.mixed_panel_s51 plan
python3 -m scripts.mixed_panel_s51 verify
python3 -m scripts.batch_o_boundary_review_s51
python3 -m unittest tests.test_mixed_panel_s51 tests.test_batch_o_boundary_review_s51 -q
```

`plan` needs only repository files; `verify` also needs the ignored local historical captures. Neither reads API keys or sends a request. The 31 new focused tests use fixtures and do not require those private captures. The complete offline suite passes **875 tests**; historical freezes and the new readiness/review summaries also verify.
