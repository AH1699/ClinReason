# Standalone pilot workflow and simulated execution

The eight-family pilot now has a working **offline scheduler, durable request capture and replay, and case-level reporting**. A complete rehearsal processes all 480 proposed requests and produces 64 first-pass and 64 repeat conversation records. Its replies and token counts are fabricated test inputs, not measurements of Gemini or MiniMax. No provider connection, API charge or new clinical score occurred.

The [public rehearsal summary](../data/audit/s61_standalone_rehearsal.json) contains counts and a protocol hash only. Cases, labels, references and the S60 input manifest remain unchanged. See [the case selection and call breakdown](S60_STANDALONE_PILOT_EN.md) for the eight-family scope.

## What now works

The scheduler follows the selected 480-job sequence: 64 first control judgments, 32 control repeats, 128 candidate turns, 128 first judgments and 128 repeats. It retains both Gemini and both MiniMax candidate versions. Requests use the previous visible-text generation settings and S56 judge instructions; historical prices are used only to exercise simulated accounting, not to quote a future run.

Each follow-up is bound to the same candidate model, conversation, case revision and initial-answer/request hashes. Provider reasoning is not inserted into later conversation history. Candidates see no scoring labels or future question. Initial judges see only the initial question/answer and initial criteria; update judges see the conversation to that point but only update criteria. Q's fourth update criterion is preserved.

The writer saves a reservation and exact request before invoking a built-in fake connection. The existing capture code saves received bytes before parsing, accepts only complete successful HTTP responses for decoding and keeps accounting separate from response validity. The fixture interface accepts no credential or caller-supplied connection factory. It cannot dispatch to a real provider.

Repeats must use identical request bytes. Input-file hashes are rechecked before each simulated exchange; changing a bound file poisons the writer before another reservation. The writer cannot retry, reopen a journal or resume after an interrupted write.

## Failure handling and replay

| Situation | Behavior in this rehearsal |
|---|---|
| HTTP rejection, redirect, incomplete body, timeout or unknown usage | Stop globally; preserve the attempt and unknown cost, never a clinical zero |
| Known-cost invalid candidate answer | Close only that candidate model's lane; retain other models and all planned report cells |
| Known-cost invalid judge reply | Stop without repairing or retrying the reply |
| Simulated spending reaches the selected test threshold | Stop after accounting for that request; the final request may overrun the threshold |
| Missing update answer | Keep the available initial answer and its stage judgment; leave the conversation score missing |
| Interrupted file write | Poison the writer; read-only replay can inspect the prefix but never authorize continuation |

Replay reconstructs requests, dependencies, accepted answers, judgments, accounting and stop decisions from the saved capture. It checks request/raw/result/report bindings and rejects changed files, linked artifacts, sequence gaps or events after a stop. A complete capture with a missing result can be reinterpreted for inspection without counting it twice or writing a repair. An unconfirmed reservation stays unresolved. Replay is an independent reading of the journal, not an independent clinical scorer.

The CLI rehearsal uses a fresh temporary directory and removes it afterward. Persistent rehearsal journals used programmatically belong in ignored `work/` or a temporary directory. It refuses to write journals into public data folders.

## How to interpret the report

All 64 conversation cells stay present, including missing and review-held ones. Each has separate initial/update findings, first-pass and repeat results, uncertainty intervals and provisional pass flags. The report lists repeat score/pass changes; it never averages them away. If an answer is missing or a judgment invalid, the absent conversation score remains null, not zero.

Controls retain every stage's observed criterion statuses, errors and independent-observation flags. The report exposes missed unsafe-error hypotheses, unexpected errors on other profiles and repeat changes. It does not overwrite observations with author expectations or demand a score reduction for every removed sentence.

**The rehearsal's admission check is technical only:** all 96 control replies must be structurally valid before candidate jobs proceed. Semantic discrepancies remain visible, but the live clinical-control gate has not been selected. Therefore, successful simulation does not authorize a paid pilot or establish that the judge is clinically reliable. The future live gate must be stated prospectively, not chosen after seeing new model scores. Historical S58 gates and results stay unchanged.

S36 arithmetic remains unchanged. Numeric fixture outputs exist only to test calculation and reporting; the public summary contains no point scores, raw responses or judge rationales. There is no model mean or ranking. Lower-tier 60–70, average about 80 and premium about 90 remain diagnostic aspirations, not fitted targets.

## Local commands and next step

```sh
python3 -m scripts.standalone_rehearsal_s61 simulate --summary
python3 -m scripts.standalone_rehearsal_s61 replay /absolute/private/journal/path --summary
python3 -m unittest tests.test_standalone_rehearsal_s61 tests.test_standalone_pilot_s60 -q
```

The second command reads an existing S61 journal only; it does not resume it. The [engine](../scripts/standalone_engine_s61.py), [capture/replay integration](../scripts/standalone_rehearsal_s61.py) and [offline policy](../config/standalone_rehearsal_s61_v1.json) are separate from frozen historical runners. No live or approval command exists.

Next, prepare a separately versioned, approval-consuming live entry point and prospective protocol: specify control-quality and technical-failure gates, freeze model settings, verify current availability/prices and propose a bounded budget for fresh export/spending approval. Old allowances do not carry forward. Continue distinct source-backed case authoring in separate batches rather than reopening single-case diagnostics.

Inventory remains **133 public draft families / 266 variants**: 125/250 registered and eight/16 standalone, with 367 additional families needed to reach 500. This checkpoint adds no family. Expert clinical/bilingual review remains deferred but required; approved calibration/Gold are 0/0 and Xi’an stays local.

The 33 new integration tests and 18 S60 checks pass together: **51 targeted tests**. The full offline regression suite also passes: **1,119 tests**. They cover full execution/replay, variable criteria, same-model history, repeat changes, uncertainty, lane closure, missing stages, HTTP/format/accounting failures, threshold overrun, interruption, input drift and tampering. These results establish software behavior under supplied fixtures, not clinical accuracy.
