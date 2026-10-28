# Eight family live pilot and spending proposal

Historical pre-run record: the owner subsequently approved one execution, now closed. See [S63 results](S63_STANDALONE_PILOT_RESULTS_EN.md) for its 278-request outcome and limitations. The proposal and rules below are preserved as written before execution, not a new approval or current run status.

The next pilot is ready for **separate owner approval**, not yet authorized or run. It will test the eight O/P/Q families with two Gemini and two MiniMax candidate models, using Gemini 3.8 Flash as judge. The new [runner](../scripts/standalone_live_s62.py) adds one-use approval, prospective control checks and failure limits to the tested S61 workflow. Cases, labels, score arithmetic and historical results stay unchanged.

This is a provisional scoring and difficulty experiment. It can show which requirements produce perfect scores, where models differ and whether the same answers receive consistent judgments. It cannot establish clinical validity or a defensible model ranking. Average about 80, lower-tier 60–70 and premium about 90 remain diagnostic aspirations, never scores to manufacture.

## What the run includes

The [S60 selection](S60_STANDALONE_PILOT_EN.md) supplies eight families in English and Chinese. Four candidates produce 64 two-turn conversations, with both first and repeated judgments retained separately.

| Sequence | Maximum requests | Purpose |
|---|---:|---|
| First control judgments | 64 | Judge the authored initial, safe, incomplete and unsafe responses |
| Control repeats | 32 | Rejudge identical initial and incomplete-update packets |
| Candidate answers | 128 | Four models answer both turns of all 16 language variants |
| First candidate judgments | 128 | Score initial and update stages separately |
| Repeated candidate judgments | 128 | Rejudge the exact saved packets, without regenerating answers |
| Total | **480** | Upper request count, not a promise of completion |

The candidates are `gemini-3.5-flash-lite`, `gemini-3.8-flash`, `MiniMax-M3.1-Flash` and `MiniMax-M3`. Grok remains outside this run; its absence is not a score of zero. No new provider diagnostic or fallback model is scheduled.

Google would receive the public synthetic cases, authored control answers, draft scoring labels, judge instructions and candidate answers needed for judging. MiniMax would receive only candidate instructions, case prompts and each model's own visible prior answer. Neither provider receives Xi’an records, purchased source files or private clinical records.

## Checks before candidate testing

All 96 control replies must be valid. Before sending the first candidate request, the runner also requires:

- All 16 predeclared unsafe-error hypotheses are detected.
- No critical error is reported on any safe or shared-initial control, including initial repeats.
- At least **31 of 32** repeated criterion/error vectors match exactly.

These are prospective author-control screening rules, not clinically validated thresholds. The repeat rule permits at most one differing vector in this small sample; it is not an estimated reliability guarantee. A failed screen stops this run before candidate generation and retains every observation. It does not prove the judge is wrong or justify silently rewriting the labels.

Errors on incomplete controls remain visible, rather than being forced to zero. No rule requires a particular incomplete-answer score, strict safe/incomplete/unsafe score ordering, a model mean or the desired 60–70/80/90 bands. Safety/revision observations remain available for inspection but are not additional hidden admission tests. All eight families remain held for clinical and language review even if the screen passes.

## Model settings and failure rules

The S61 request construction is unchanged: candidate output limits are 8,192 tokens; Gemini candidates use medium thinking and standard service. MiniMax uses adaptive thinking; M3.1 Flash uses `max` reasoning with no unsupported service-tier field, while M3 explicitly requests standard service. The judge uses 32,768 output tokens, medium thinking, standard service, the S56 evidence instructions and unchanged S36 arithmetic. Token limits remain in place. Follow-ups carry visible answer text only, not provider reasoning state; this is a defined conversation protocol, not a test of each provider's richest native stateful interface.

One request runs at a time, with no retries, repair calls, fallback, continuation after interruption or reuse of old allowances. Unknown delivery/cost, HTTP failure or a changed model identity stops globally. A known-cost invalid candidate closes only that candidate model's lane; other models can continue. Available initial answers can still be judged when their update is missing, but the full conversation score stays missing.

An invalid control or non-format judge failure stops immediately. During candidate judging, the first two complete, known-cost **format-only** failures are retained as missing and independent jobs can continue; the third stops the run. The count spans first and repeat judgments. A repeat requiring an invalid first judgment is skipped, not treated as a retry. Spending at or above the threshold stops before another request, although the final request may overrun it.

## Price check and proposed budget

Published model IDs and standard text prices were checked on **October 27, 2026**. These listings do not verify account access or credits. Rates are USD per million tokens; Gemini output includes thinking. [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [Google supported models](https://ai.google.dev/gemini-api/docs/interactions-overview), [MiniMax pricing](https://platform.minimax.io/docs/pricing/overview), [MiniMax model and parameter documentation](https://platform.minimax.io/docs/api-reference/text-openai-api).

| Model | Input | Output |
|---|---:|---:|
| Gemini 3.5 Flash-Lite | $0.30 | $2.50 |
| Gemini 3.8 Flash | $0.75 | $3.75 |
| MiniMax M3.1 Flash | $0.15 | $0.60 |
| MiniMax M3 standard | $0.30 | $1.20 |

The Gemini 3.8 introductory rate lasts through December 31, 2026. For M3's unverified `default` response to an explicit standard request, monitoring retains the higher published short-context priority rates, $0.45/$1.80. That convention does not confirm the actual tier or bill. No cache discount or tool charge is assumed. Source evidence must be no more than 24 hours old before each dispatch; any required protocol refresh needs a new matching freeze and approval.

**Proposed stop threshold: $20, with possible final-request overrun.** For illustration, assuming every request uses 4,000 input and 4,000 billed output tokens gives **$7.6544** for 480 requests; 8,000 of each gives **$15.3088**. Both scenarios include M3's higher monitoring rates. They are assumptions, not measured token forecasts, upper bounds or completion guarantees. Longer outputs can exceed these estimates and end the run before completion. Unknown charges stop the run and remain unresolved, not zero.

## Approval and local commands

The [policy](../config/standalone_live_s62_v1.json) and [frozen protocol](../config/standalone_live_s62_frozen_v1.json) bind inputs, code, tests, settings, gates and pricing evidence. A trusted local operator records fresh owner consent for that exact hash, scope, provider disclosure, stop threshold and failure/reporting policy. Approval expires within 24 hours, is consumed before credentials or network access and cannot be refunded by deleting a failed result. These local records are not an authentication service against a hostile process using the same OS account.

```sh
python3 -m scripts.standalone_live_s62 proposal
python3 -m scripts.standalone_live_s62 snapshot
python3 -m scripts.standalone_live_s62 preflight --freeze config/standalone_live_s62_frozen_v1.json --approval work/s62-approvals/OWNER_APPROVAL.json
python3 -m scripts.standalone_live_s62 run --freeze config/standalone_live_s62_frozen_v1.json --approval work/s62-approvals/OWNER_APPROVAL.json
python3 -m scripts.standalone_live_s62 replay --directory /absolute/project/path/work/s62-runs/RUN_UUID
```

`proposal`, `snapshot`, `preflight` and `replay` do not call providers. Only `run` can load keys, and only after valid one-use approval. There is no approval-creation, retry or resume command. Journals and consent receipts stay in ignored `work/`; keys stay in `.env.local`. Replay reconstructs from captured replies, checks bindings and preserves incomplete attempts without repairing or resuming them. Expired approvals remain inspectable at their recorded consent time.

## Current progress and next decision

All **1,152 offline regression tests pass**, including 33 new tests for the full 480-request fixture run and replay, semantic-gate boundaries, format-failure limits, approval consumption before key loading, expiry, interrupted writes and tampering. The live-entry test uses a fabricated test approval and fake connection; it does not contact a provider. The S62 freeze reproduces exactly, and S57/S60/S61 remain unchanged.

No paid request, new measured score or new family was added. Inventory remains **133 public draft families / 266 variants**, with 367 more families needed for 500. Clinical/bilingual review remains deferred, not waived; calibration/Gold remain 0/0. Next decision: approve this one bounded run, then inspect case-level scores and repeats without changing labels retrospectively. Continue source-backed expansion in separate batches, leaving this frozen pilot intact.
