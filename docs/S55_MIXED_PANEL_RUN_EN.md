# Nine family panel results and evidence contract stop

The approved run closed after **264 new requests**, with a **$1.990560 recorded cost estimate** against the $20 stop threshold. All four candidates completed generation, and the judge-control gate passed. A later judge reply failed the evidence-format contract, so the single judge lane closed. **The full benchmark and candidate-repeat pass did not finish.** No retry, resumed run or additional paid diagnostic was made.

## What completed

| Component | Result |
|---|---|
| Candidate answers | 128/128 new stages accepted, plus 16 verified imports: all 144 stages / 72 conversations present |
| Candidate versions | Gemini 3.5 Flash-Lite, Gemini 3.8 Flash, MiniMax M3.1 Flash and MiniMax M3; each supplied 32 new stages |
| Judge controls | 36/36 accepted; all six unsafe errors detected, all six strict ordering groups passed, all twelve repeated stage vectors matched, all six partial-repeat differences within five points |
| First candidate judgments | 100 attempted: 99 accepted and one rejected; 49 complete two-stage pairs plus one unpaired initial judgment |
| Remaining first judgments | 44 unattempted after the judge lane closed |
| Candidate-repeat judgments | 0/144 attempted; all skipped after lane closure |
| Total disposition | 263 accepted, one rejected, 188 skipped; zero unknown-cost attempts |

The 49 complete pairs include eight review-held medication conversations. The other 41 are provisional case-level diagnostics, **not repeat-tested model comparisons**. Every expected cell remains in the [read-only results](../data/audit/s55_mixed_panel_run.json); missing values are null, not zero. The internal terminal label `schedule_complete` means every scheduled row received a disposition, including skips—not that 452 calls or the full benchmark completed.

## Why the run stopped

Event 264 was Gemini 3.8 Flash judging the English update answer from Gemini 3.8 Flash on `HC-MT-REASON-020`. The provider returned **HTTP 200, completed output and the expected model identity**. This was not an API rejection, unknown-cost event or budget stop.

The judge marked update criterion 4 **met** with an empty `response_evidence`. Its anchor begins **“Do not ”**. The frozen S36 contract permits an empty quote for a met avoidance criterion only when its anchor starts exactly **“Does not ”** or **“Avoids ”**. The reply's rationale describes adherence to a negative constraint, but that does not satisfy the frozen quote requirement. The validator rejected the reply as written and the declared close-model-lane policy skipped the remaining 188 judge requests.

[The stop review](../data/audit/s55_stop_review.json) records the field, source hashes and accounting without publishing answer text or judge explanations. The rejected reply remains rejected. No quote was inserted, prefix broadened, score repaired or historical record rescored. This reveals a wording-sensitive evidence rule; it does not establish whether the clinical status should be met. H147 records the later semantic-review question.

## What the early scores show

These are first-pass diagnostics only. The run stopped before most conflict-case comparisons and before all candidate repeats.

| Family | Complete first-pass pairs | First-pass 100-point results |
|---|---:|---:|
| TRIAGE-019 | 8/8 | 8/8 |
| TRIAGE-020 | 8/8 | 0/8 |
| REASON-015 | 8/8 | 4/8 |
| REASON-014 | 8/8 | 8/8 |
| MEDSAFE-013 | 8/8 | Review-held; not comparable |
| MEDSAFE-014 | 8/8 | 6/8 |
| REASON-020 | 1/8 | 0/1 completed pair |
| REASON-022 | 0/8 | Missing |
| MEDSAFE-019 | 0/8 | Missing |

All IDs have the `HC-MT-` prefix. Two fully observed families still show a ceiling in this sample. The incomplete, ordered prefix cannot establish the whole panel's difficulty or the desired model score bands. No pooled model mean, median or ranking is reported. Do not lower scores, relabel model tiers or select replacements just to obtain lower-tier 60–70, average around 80 or premium around 90.

A simple read-only script found CJK characters in all 72 Chinese-variant answer stages. This checks only character presence, not language quality or clinical equivalence. Expert review remains deferred, not waived; approved calibration/Gold remain **0/0**.

## Budget and provenance

The owner approved the original scope and increased its stop threshold from $10 to $20. Before the first request, only the prospective budget and price-check timestamp changed; cases, prompts, scoring arithmetic, control thresholds and roster stayed frozen. The original $10 proposal remains in Git commit `e3c9b9207e12ae5033afb4fe54ad874ac57714b1`, with protocol hash `d2c2d41c860303122d278a024b7fd5ff1cd78168a79d2378ab2008783982d01a`.

- Execution protocol: `94c18ae8b8e3e025f8a20c0f0deeb77c9714c71777de2494734c8ecf753224e7`.
- Run: `255d7614-dfe4-4e2e-bf74-520f61d2d58f`.
- [Approved configuration](../config/mixed_live_s54_v1.json), [frozen inputs](../config/mixed_live_s54_frozen_v1.json), [runner](../scripts/mixed_live_s54.py), and [read-only reporter](../scripts/audit_mixed_live_s55.py).

The estimate includes the rejected request ($0.009708), but excludes historical charges for the 16 imported stages. It is **not an invoice or verified account hard cap**. Official prices were rechecked at 2026-10-26 01:57:35 UTC. The higher-rate monitoring convention for MiniMax M3's unverified `default` tier echo remains; no cache discount is assumed. [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [MiniMax pricing](https://platform.minimax.io/docs/pricing/overview).

Only agreed public synthetic material was sent to Google/MiniMax. No Grok calls, Xi'an records or purchased question text entered this run. Keys, raw replies and consumed approval remain in ignored private local storage. The unused portion of $20 does not authorize another experiment, retry or restart.

## Next work

1. Make evidence requirements explicit **per criterion** in a separate prospective prompt/schema version. First preserve existing quote-required semantics and test them offline; do not silently broaden the absence exception or repair this rejected reply.
2. Verify and bind all 144 saved candidate stages for a future judge-only protocol, so candidates need not answer again. Declare how new judgments relate to this incomplete run, retain missing/rejected records and obtain fresh bounded approval before any new provider call.
3. Keep the ceiling audit open and expand distinct source-backed cases, especially conflicting evidence and decision changes. Registered development remains **125 families / 250 variants**, with four standalone O/P families / eight variants outside this run and the default registry. The target remains at least 500 distinct families; Xi'an stays local.

S50's failed gate and historical S48/S49 results remain unchanged. H142–H147 stay open. Passing this control gate did not complete scoring calibration or clinical validation.

## Verification

The final full offline suite passed **977 tests**. All **15 new report/stop-regression tests** also passed separately, including a complete simulated 452-request journal, missing values, review holds, gate failure, unchanged arithmetic, tampering, unknown cost and the exact Do-not empty-quote rejection. The public report recomputes exactly from the sealed live journal; the reporter makes no provider calls and exports no answer or explanation text. Execution hashes, failed-capture hashes, reporter hashes and local documentation links were checked. Keys, raw replies and consumed approval remain excluded from Git.
