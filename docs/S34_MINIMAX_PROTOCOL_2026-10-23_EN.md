# S34 MiniMax workflow diagnostic alongside S33

**Post-run status:** All eight MiniMax answer calls succeeded. S34 stopped at request 21 on Gemini's nonliteral criterion quote, leaving 12 valid judge stages and six derived records; it was not resumed. See the [separate S33/S34 outcomes](S33_S34_RESULTS_2026-10-23_EN.md). The pre-run protocol below is unchanged.

## Authorized scope and interpretation

The owner approved proceeding with S33 and explicitly requested MiniMax in this test run. S33 keeps its frozen **48-call judge-control protocol**. S34 adds a separately bounded **24-call MiniMax workflow diagnostic** on the same two synthetic families in English and Chinese, for a combined ceiling of **72 requests**. This is a request ceiling, not a currency cap.

S34 uses **MiniMax `MiniMax-M2.7`** as the candidate, with **Gemini `gemini-3.8-flash`** and **Grok `grok-4.7`** as judges. This choice continues the earlier working MiniMax candidate configuration; it is not a current availability claim or a quality-tier assignment. A failed or changed model response stops the run rather than selecting another model automatically.

This is a user-requested integration check, not the wider comparative candidate pilot contemplated by S33's advance gate. The two runs have separate outputs, counts and stopping rules; a failure in one does not authorize retries or change the other. S34 can establish that candidate generation, blinded judging and score calculation work together, but `comparison_ready` and `calibration_complete` remain false even if all calls complete. Its results cannot repair a failed S33 control gate or establish a model ranking.

## What is sent and how much

For each of red-eye `TRIAGE-018` and sinus `TRIAGE-020`, run the exact existing English and Chinese user turns. Each of the four conversations uses:

1. Two MiniMax calls, with the second question supplied only after the first answer is saved and validated.
2. Two initial-stage judge calls, one per judge, seeing only the first user/assistant pair and initial labels.
3. Two update-stage judge calls, one per judge, seeing the full conversation but only update labels and the existing safety/revision observations.

That is **8 candidate calls + 16 judge calls = 24 maximum**, with no repeats. Up to eight case-wise conversation/judge scores can be derived; there are only four candidate conversations, not eight independent cases.

MiniMax receives the bilingual candidate instruction, synthetic user messages and its own preceding answer. It receives no reference answer, criterion label, authored profile or target score. The runner adds no candidate identity to the judge packet; Google/xAI receive the synthetic dialogue with MiniMax answer text, applicable draft labels and judge instruction. No Xi'an records or purchased source files are included. MiniMax's existing API request exposes no storage-disable setting; no zero-retention assurance is made. Google/xAI judge requests retain their existing `store: false` setting, which is not a general guarantee about provider retention.

MiniMax requests preserve `reasoning_split: true` and the 8,192 completion-token ceiling. Only answer `content` is passed forward; separate reasoning is not judged or sent in later requests. Embedded `<think>` content, truncation, empty output, a non-success provider status, malformed response or unexpected returned model is rejected. Raw local replies may include separate reasoning and stay in ignored `work/`.

## Frozen mechanics

The [policy](../config/minimax_s34_v1.json), [manifest](../config/minimax_s34_frozen_v1.json), [runner/audit](../benchmark/minimax_s34.py) and [tests](../tests/test_minimax_s34.py) bind the source cases, adapter, candidate instruction and exact S33 scoring dependencies. Protocol fingerprint:

```text
b74231a5ddfa9d07853456ef615693ac8a609cc809dc0af69a6bb9d3052e982a
```

Candidate answers do not exist before generation, so their future judge packets cannot have pre-run content hashes. Instead, each request's actual input is hashed before sending. The read-only audit reconstructs those inputs from frozen user turns and validated saved MiniMax answer text, replays the adapter locally against saved raw responses, and recomputes scores from matching initial/update judgments. It rejects edited replies, broken source links, altered request hashes and missing stages.

The exact S33 prompts, anchors, evidence validation and numerical rules are reused without modification. There is **no expected MiniMax score**, no requirement to reach 80 and no automatic application of the authored-control hypotheses to MiniMax's own answers. Unclear criteria produce intervals without a point score or pass flag. Report each judge separately, including all disagreements and missing results; no average ranking is planned.

The schedule is fixed by case, then candidate initial/update, initial Gemini/Grok, update Gemini/Grok. Timeout is 240 seconds per request, with unpinned provider-default sampling and zero retries. Stop this diagnostic at the first transport or validation failure; preserve attempted delivery uncertainty and the saved prefix. No fallback, repair, resume, replacement or mixing with earlier MiniMax runs.

## Offline verification and next action

Twelve new tests cover prompt-only candidate exposure, stage isolation, reasoning exclusion, request caps/acknowledgments, transport and validation stops, model identity, dynamic input hashes, raw-response replay, uncertainty and complete mocked workflow. The [S33 protocol](S33_STAGE_ISOLATED_PROTOCOL_2026-10-23_EN.md) and its 48-call limit are unchanged. No MiniMax call had occurred when this protocol was prepared; S33 had already begun with owner approval, and its results will be reported separately.

```sh
python3 -m benchmark.minimax_s34 plan
python3 -m unittest tests.test_minimax_s34 -v
```

After committing this pre-run protocol, execute S34 once in a fresh ignored directory with `--max-calls 24` and the exact approved protocol fingerprint, then audit both runs and update the result notes. The CLI acknowledgment binds scope but is not a substitute for the owner's request and approval.

H124 adds candidate exposure, reasoning exclusion, provider retention, four-conversation limitations and interpretation alongside an unfinished control-calibration experiment. Clinical/bilingual review remains deferred, not waived. Public development stays **125 families / 250 variants**, approved calibration/hidden Gold **0/0**; no cases, historical scores or default rules change here.
