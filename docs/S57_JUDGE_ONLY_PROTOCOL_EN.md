# Judge only panel protocol and bounded failure policy

**Execution completed:** the owner approved this exact scope and the run completed with 324 accepted calls and a $3.875174 token-cost estimate. See [S58 results](S58_JUDGE_PANEL_READOUT_EN.md). The preparation and approval-request statements below are historical; this approval is consumed and cannot authorize another run.

The runner is implemented for **one fresh experiment using the 144 saved answer stages**. It makes no candidate-generation calls. The next decision is approval for up to **324 Gemini 3.8 Flash judge requests** with a proposed **$5 recorded-spending stop threshold**, allowing a possible last-request overrun. **No new paid calls have been made.** The previous $20 approval is consumed and is not reused.

## Keep the project moving without accepting invalid scores

An isolated formatting error should not erase the opportunity to judge independent cases. This version changes the run's failure handling, not the validator or scoring rules:

| Event | Action |
|---|---|
| Invalid control judgment | Stop immediately |
| All 36 controls valid but the control gate fails | Stop before candidate judging |
| First or second known-cost formatting failure during candidate judging | Keep the reply rejected and its score missing; continue independent scheduled judgments |
| Third such failure, counted cumulatively across first and repeat passes | Stop the run |
| Repeat whose first judgment was rejected | Skip it; do not turn a repeat into a retry |
| Model mismatch, incomplete model output, unknown cost or transport failure | Stop immediately |
| Recorded spending reaches $5 | Stop before the next request; the last request can exceed the threshold |

Here, known-cost means the reported usage can be reconciled into the existing token-cost estimate, not that a final invoice has been confirmed. Every attempt, rejection, skip and unattempted row stays visible. A conversation missing either stage has no combined score, not a zero. No quote is inserted, no status is changed to make it pass, and there are no automatic retries or resumed runs. Format failures can be nonrandom, so surviving scores are not an unbiased sample of the whole panel.

This bounded continuation rule requires explicit acceptance with the new protocol. S55's rejected reply and stopped run remain untouched. The clearer S56 instructions, exact-span validation, case labels, criterion weights, error rules and pass threshold remain unchanged.

## Fixed scope and sequence

1. Run **36 fresh controls** under the new instructions. Require all six unsafe-error checks, six strict-order groups, at least eleven of twelve repeated control stage vectors, and six partial-repeat score differences within five points.
2. If the gate passes, make **144 first judgments**: both stages of 72 conversations across the existing nine families, both languages and four candidate versions.
3. Make up to **144 repeat judgments** using identical saved payloads. Keep first and repeat results separate; do not average away disagreement.

The candidate versions remain Gemini 3.5 Flash-Lite, Gemini 3.8 Flash, MiniMax M3.1 Flash and MiniMax M3. They are represented by their saved answers, not new calls. Grok is not called in this continuity panel. The judge settings remain a 32,768-token output maximum, medium thinking and unpinned provider sampling defaults.

All **72 cells** stay in the report. The eight `MEDSAFE-013` conversations remain review-held raw diagnostics. No pooled means, rankings or clinical-validation claims are permitted. S55 judgments and its successful control gate do not count as this run's results.

## Saved sources and private storage

The runner checks the frozen S54/S56 code, the pinned bank hash and the underlying sealed requests and raw replies before consuming approval. The bank contains 128 S54 candidate stages and 16 upstream stages, with case/model/language/history bindings. It has already been reverified locally; no candidate needs to answer again.

New journals belong in ignored `work/s57-runs/`; consumed approvals belong in ignored `work/s57-consumed-approvals/`. A fresh run identifier and exclusive writes prevent reopening. The request reservation is saved before connection, raw replies before interpretation, and API credentials are never serialized. An interrupted prefix can be inspected read-only but cannot be resumed. Public output contains typed per-case scores, statuses and hashes, not answer or judge-explanation text.

Only the agreed synthetic cases, saved answers, draft labels and judge instructions would be sent to Google. Xi'an records, purchased question text and private clinical records are excluded. The runner reads only the Gemini credential for this experiment.

## Price and approval

[Google's official pricing](https://ai.google.dev/gemini-api/docs/pricing) was checked on October 26, 2026: standard Gemini 3.8 Flash text pricing is $0.75 per million input tokens and $3.75 per million output tokens, including thinking, through December 31, 2026. Monitoring assumes no cache discount or batch price. The **$5 proposal is a stop threshold, not an invoice estimate, a completion guarantee or a verified account hard cap**.

The [plan](../config/judge_live_s57_v1.json), [frozen inputs](../config/judge_live_s57_frozen_v1.json) and [runner](../scripts/judge_live_s57.py) bind the scope, source, instructions, failure policy and budget. Admission requires current matching prices and a fresh owner approval for the exact protocol, including provider disclosure, paid calls, possible overrun, reporting limits and bounded format-failure continuation. Approval is single-use, expires within 24 hours and is consumed before credentials or network access. Stale prices require rechecking and a new freeze/approval binding, not reuse of old permission.

Safe inspection commands:

```sh
python3 -m scripts.judge_live_s57 snapshot
python3 -m scripts.judge_live_s57 verify-source
```

These commands do not call a provider. The `run` command requires a separate matching approval record; this document is not that approval.

## Completion and the next project step

This engineering batch ends with a tested, frozen runner and one approval decision. After the approved run, produce one case-level readout covering completion, technical failures, repeat disagreement and ceiling effects. If it stops early, retain the usable provisional diagnostics and explain the missing portion; do not automatically start another single-case diagnostic cycle.

The next development work is a distinct source-backed case batch and authoring catalog toward **at least 500 families**, using the panel readout to identify reasoning gaps rather than forcing scores into desired bands. This checkpoint adds no cases: registered development remains **125 families / 250 variants**, plus four standalone O/P families / eight variants. Approved calibration/Gold remain **0/0**. Expert review remains later, H142–H147 stay open, Xi'an stays local, and lower 60–70 / average around 80 / premium around 90 remain diagnostic aspirations, not targets to fit.

## Offline verification

The full offline suite passed **1,033 tests**, including **34 new S57 tests**. They cover a complete 324-request simulated journal and replay, isolated failures with missing scores, the third-failure stop, control failure, unknown cost, transport/interruption, spending overrun, approval consumption, tampering and private-text exclusion. Simulated results are plumbing checks, not measured model performance.

All 144 real saved answer stages were reverified. All 324 generated judge payloads match the prepared S56 request-set hash; the largest request is 27,444 bytes, below the existing request-size limit. The new freeze matches current files, and S26–S56 inputs and historical reports are unchanged. Checks of 287 local links in the changed documentation passed. No provider request or real approval record was created during these checks.
