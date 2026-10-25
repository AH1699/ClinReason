# Mixed panel policy and transport rehearsal with complete Batch O controls

The next panel now has an explicit draft judging/reporting policy and an integrated **mock-connection transport rehearsal**. Batch O has controls covering all twelve criterion positions. No provider calls, new model scores or registered families were added; this checkpoint does not complete scoring calibration.

## Prospective judging and reporting policy

[The policy](../config/mixed_policy_s53_v1.json) preserves the nine families, four Gemini/MiniMax candidate versions and all **72 conversations / 144 answer stages**. Sixteen saved stages remain imports. Candidate requests stay compatible with their original generation settings; no saved answer is regenerated or silently rebound to new labels.

The draft uses Gemini 3.8 Flash with S47's observation-completeness instructions/schema, a uniform 32,768 allowance and medium thinking for controls, first judgments and exact-payload repeats. Provider-default sampling remains unpinned. Arithmetic and labels are unchanged. This is a proposed continuity configuration, not a finding that the larger allowance fixes prior failures.

The inherited 36-record control gate remains unchanged: six unsafe-error detections, six strict ordering groups, at least eleven matching repeated stage vectors and six partial-score repeats within five points. It was not relaxed in response to S50. S50's separate failed gate remains failed; passing a future control run would not close the medication review issues.

The [reporting manifest](../scripts/mixed_policy_s53.py) retains eight `MEDSAFE-013` conversations but marks their results **raw diagnostics only, not comparable**. Their original criterion statuses and evidence stay visible; no disputed status is automatically overridden. Other cells may support provisional case-level diagnostics after the control gate. Missing scores remain missing, repeats remain separate, and the draft permits no pooled model mean, ranking, silent removal or reweighting. This is a reporting contract; no new numerical readout was generated.

## Transport integration tested without connecting to providers

[The integration](../scripts/mixed_transport_s53.py) connects the existing S46 capture implementation to S52's scheduler using built-in simulated connections. Every exchange reserves and saves its exact request before the simulated connection, saves response bytes before parsing, and binds the capture to the scheduler's event. Complete first and repeat requests can be reconstructed from the combined journal.

A valid-looking JSON body inside an HTTP 403 is **not** forwarded to the answer parser. Redirects, HTTP errors, connection/read timeouts, partial reads, response-size limits, encoding/length errors and deadline failures stop the integration. Those unforwarded attempts remain unresolved, not free or zero-scored. Complete 2xx bodies proceed to normal validation/accounting: unknown usage stops globally; a known-cost invalid response closes only its model lane. No path retries a failed job or resumes a stopped writer.

The tests also cover disk failures, interrupts, capture tampering, orphan entries, secret-header exclusion, threshold overrun and the full 452-request fixture sequence. Replay is read-only and checks both capture-to-scheduler bindings and S52's reconstructed state. All costs and replies in these tests are simulated.

Only the built-in fixture type is accepted. There is no external connection-factory argument, credential argument, live mode or live-run command. Current pricing has not been reverified and no fresh budget is authorized. A separately frozen, approval-consuming live entry point is still required before any provider call; old budgets and approvals cannot carry over.

## Batch O controls now cover all twelve positions

[The new component controls](../data/audit/batch_o_component_controls_s53.json) add **54 criterion-targeted records** for the ten positions left after S52. Combined with S52's eighteen records, the [materializer](../scripts/batch_o_components_s53.py) produces **72 targeted records sharing 58 unique blinded packets**. Reused baselines are deduplicated by exact packet hash. These are still only two case families, not 58 or 72 new cases.

Each contrast changes one response component relative to its declared baseline. One heart-failure treatment-direction group explicitly uses a neutral monitoring baseline so another sentence does not already list all three options. Initial-stage packets exclude the later user turn and answer. Author expectations, target identities and construction notes remain outside the judge packet. S52's packets are preserved exactly, and no additional requirement or anchor changes here.

There are **64 provisional author hypotheses and eight unlabelled exploratory records**. The eight records are four paired-language questions:

| Target | Unresolved interpretation |
|---|---|
| Heart failure, update 2 | Does grouped clinical/kidney monitoring adequately cover the electrolyte domain? |
| Nutrition, initial 2 | Does generic electrolyte monitoring cover the three named electrolytes? |
| Nutrition, update 1 | Does naming a possible metabolic complication already address the calorie-shortage inference? |
| Nutrition, update 2 | Can uncertainty elsewhere in the same answer satisfy the other-causes element? |

These are registered as H144 for later adjudication, alongside the still-open H142/H143 questions. The software verifies text construction and coverage, not medical correctness. No model has judged this new package, and no human-review issue is closed.

## Verification

The full offline suite passed **932 tests**, including 27 new S53 tests. All 27 S53 tests passed again after a final interruption-accounting correction: a reply already saved and accounted by the scheduler must not count as a second unresolved attempt if writing its bridge record fails. S51's readiness summary still recomputes exactly against the actual private saved bank. Historical freezes, the original Batch O files and S52's wording snapshot are unchanged. These are engineering checks, not clinical validation or new model scores; no provider calls were made.

## Next work and decision point

1. Prepare the approval-bound live entry point and a prospective run freeze, then refresh pricing and present a bounded budget. The existing proposal remains **128 generation + 36 controls + 144 first judgments + 144 repeats = 452 new requests**; none is authorized now. The reporting policy must be accepted with that future protocol.
2. Return case authoring to distinct public-report/Step-2-informed mechanisms, prioritizing the recorded low-acuity, competing-risk and longitudinal gaps. Batch O's structural control coverage is now complete; the eight unlabelled records are a bounded review queue, not a reason to keep inventing more variants indefinitely.
3. Keep expert/bilingual review for the later required validation gate. Registered coverage stays **125 families / 250 variants**, plus two standalone Batch O families, with approved calibration/Gold **0/0**. Xi'an stays local. The at-least-500-family target and diagnostic 60–70 / about 80 / about 90 aspirations remain unchanged; do not fit scores to them.

Offline commands:

```sh
python3 -m scripts.mixed_policy_s53
python3 -m scripts.batch_o_components_s53
python3 -m unittest tests.test_mixed_transport_s53 tests.test_batch_o_components_s53 -q
python3 -m scripts.mixed_transport_s53 replay /absolute/path/to/local/integration-journal
```

Replays require the unchanged source snapshot and remain read-only. Keys, imported answers and raw capture files stay in ignored local storage.
