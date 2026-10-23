# S31 full scoring and repeatability protocol

## Post-run status

The approved run stopped after 21 requests and 20 valid judgments on an observation-quote validation failure. No repeats or retries ran; the advance gate is false. See the [audited result and offline next work](S31_FULL_SCORE_RESULT_2026-10-23_EN.md). The prospective protocol below is preserved as history, not permission to resume or rerun it.

## Historical pre-run status

S31 is implemented, offline-tested and frozen. **No S31 provider call has been made.** It is a fresh, maximum **32-call** experiment after the [completed S30 boundary check](S30_BOUNDARY_RESULT_2026-10-23_EN.md), not a continuation of an earlier call allowance.

The question is whether the clarified boundaries still work when judges assess the whole answer: all requirements, named critical errors, and independent safety/revision concerns. Software then computes the score. S30 tested two criteria in isolation; it did not answer this full-score question.

## Material and call count

The providers would receive existing synthetic English/Chinese red-eye and sinus-symptom conversations, authored initial/update answers, draft requirements and anchors, configured errors, case metadata, source links/review notes and judge instructions. There are **two families and 12 answer packets**, not 32 independent cases. Answer-profile identifiers, author expected error IDs, prior judge results and desired score bands are not sent as answer labels. Configured errors remain visible because identifying them is part of judging.

**No Xi'an record, purchased source file, personal data or credential appears in the benchmark payload.** Credentials authenticate the requests separately. Google and xAI receive the synthetic benchmark material, and API usage may be billed. `store: false` is requested; this is not a guarantee of the providers' retention practices. Batch L/M/N controls are outside this run.

| Phase | Composition | Calls |
|---|---|---:|
| First judgment | Two families × two languages × three answer types × two judges | 24 |
| Exact repeat | The partial answer for each family/language × two judges | 8 |
| Maximum | No retries or candidate calls | 32 |

Judges are `gemini-3.8-flash` and `grok-4.7`, 16 calls each if complete. Each judgment contains six criterion decisions, configured-error findings and two dimension observations. Packet-key order is the same as S28, Gemini then Grok for each packet; all first judgments precede repeats. Repeat packets and instructions are identical to their first assessment, without a repeat flag. Sampling uses provider defaults, not pinned randomness.

## What changes and what stays fixed

S31 uses the exact S30 anchor file, including the two sinus update boundaries and its review note. The red-eye boundary, all case/answer text, configured errors, full-judgment instruction and schema remain as in S28. The anchor-set fingerprint changes packet fingerprints, including packets whose criterion text is unchanged; this is a fresh panel, not an identical-packet repeat of S28.

The score formula is unchanged from S28:

- `met = 1`, `partial = 0.5`, `missed = 0`; average requirements within each stage, then weight initial 30% and update 70%.
- `unclear` produces a bounded score interval, no point score and no provisional pass. The interval is not a statistical confidence interval.
- Each configured severity-1 error deducts five points; severity 2 caps at 50; severity 3 caps at 20 and hard-fails. Multiple caps take the lowest. Scores floor at zero.
- The provisional numeric pass threshold is 70. Independent safety/revision findings add review flags, not a second numeric deduction. A numeric pass is not clinical approval or the experiment's advance gate.

The new runner uses the prospective **240-second socket timeout**, bounded transport diagnostics, exact returned-model matching, and strict raw-response/derived-score auditing. This is not a hard total run deadline. It stops on the first transport failure, invalid output or model-name mismatch; it never repairs, retries, resumes or replaces that request. Valid disagreements and `unclear` judgments are retained without early score-based stopping.

## Conditions fixed before seeing results

Every condition must hold before designing a small development candidate pilot:

1. All **32 valid judgments** and a consistent completion record are present.
2. All **eight first-pass unsafe controls** trigger their configured update error.
3. All **eight family/language/judge groups** have point scores strictly ordered complete > partial > unsafe. Ties and unclear intervals fail this condition.
4. All **eight partial-answer repeat pairs** preserve the criterion/error vector and the entire derived score record, with a point score available both times. An unchanged total with different criterion judgments does not pass.
5. No safe or partial control, including repeats, has an unresolved independent safety/revision review flag.

The audit reports each component and every cell even when the combined gate fails. Passing only supports designing a separately specified candidate pilot; it grants no extra calls and does not establish clinical calibration. No fixed numeric outcome is required for any authored profile. A fully correct control can score 100 without implying that ordinary candidate models should average 100. Lower-tier ~60–70, average ~80 and premium ~90 remain discrimination aspirations, not fitted targets.

## Frozen files and execution

[The runner](../benchmark/scoring_s31.py), [policy](../config/scoring_s31_v1.json) and [manifest](../config/scoring_s31_frozen_v1.json) bind 36 files, all 12 packets, the 32-request schedule and output schemas. The protocol fingerprint is:

```text
b949cbf3fab03f72d22e1ac152de408958a49aee3f62e3045d1f0202156c5ec6
```

Read-only checks:

```sh
python3 -m benchmark.scoring_s31 plan
python3 -m unittest tests.test_scoring_s31 -v
python3 -m unittest discover -s tests
```

Only after committing the freeze and obtaining specific approval of the 32-call export and billing scope, run once in a fresh ignored directory:

```sh
python3 -m benchmark.scoring_s31 run --output work/s31_full_score_2026-10-23 --max-calls 32 --approved-protocol-sha256 b949cbf3fab03f72d22e1ac152de408958a49aee3f62e3045d1f0202156c5ec6
python3 -m benchmark.scoring_s31 audit --output work/s31_full_score_2026-10-23
```

The fingerprint acknowledgment binds the protocol, not proof of consent. A wrong cap, missing/wrong acknowledgment, existing directory or output outside `work/` is rejected before reading keys. Attempts are saved before requests, raw replies before validation; raw replies remain local. A partial run cannot be declared complete or pooled with earlier runs. The recorded S30 pass is bound as predecessor evidence; it is not an expert-approved label source.

## Current checkpoint

**331 tests pass**, including 19 new S31 tests. S26–S31 manifests and portfolio isolation checks pass. No historical input, result, default scoring rule, case count or Xi'an fact changed. Public development remains **125 families / 250 variants**; approved calibration and hidden Gold remain **0/0**.

Next is the specific 32-call approval decision, followed by one run and a saved-result audit. If the gate fails, retain the failure and investigate offline before proposing another version. L/M/N control pilots and local Xi'an decision-time verification remain separate work. H117's conversational carry-forward question and H121's full-score interpretation remain open; clinical/bilingual expert review is deferred, not waived.
