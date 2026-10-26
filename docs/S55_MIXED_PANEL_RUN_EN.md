# Nine family panel execution and diagnostics

The owner approved the S54 panel and raised its recorded-spending stop threshold from $10 to **$20**. The run is in progress. It has not yet produced a complete result or passed its control gate. This is one execution of the agreed scope, not permission to restart failed requests or spend the unused allowance on another experiment.

## Approved scope

The four candidates remain Gemini 3.5 Flash-Lite, Gemini 3.8 Flash, MiniMax M3.1 Flash and MiniMax M3; Gemini 3.8 Flash is the judge. Nine fixed families, two languages and two turns give **72 conversations / 144 answer stages**. Sixteen verified medication-case stages are imported; the maximum new work is **128 candidate requests, 36 controls, 144 first judgments and 144 repeats: 452 requests**.

Google and MiniMax receive the agreed public synthetic cases, candidate answers, reference requirements and judge instructions. Xi'an records, purchased question text and credentials are not part of the benchmark material. Raw replies and the single-use approval stay in ignored local `work/`; `.env.local` stays excluded from Git. Grok is not called.

The $20 amount is a **recorded token-cost stop threshold**, not an invoice or verified account hard cap. The last request may exceed it. Unknown cost/delivery stops dispatch; a known-cost invalid reply closes its model lane. There are no retries or resumption. The run generates candidates before checking the judge; a failed control gate can therefore leave saved answers without new scores.

Official prices were rechecked at **2026-10-26 01:57:35 UTC** and still match the estimator. The existing higher-rate monitoring convention for MiniMax M3's unverified `default` tier echo is retained; cache discounts are not assumed. [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [MiniMax pricing](https://platform.minimax.io/docs/pricing/overview).

## Version and audit trail

Only the prospective S54 budget and price-check timestamp changed before dispatch. Cases, prompts, scoring arithmetic, control thresholds, candidate roster and reporting policy did not. The earlier $10 proposal remains in Git commit `e3c9b9207e12ae5033afb4fe54ad874ac57714b1`; its original protocol hash was `d2c2d41c860303122d278a024b7fd5ff1cd78168a79d2378ab2008783982d01a`.

- Execution protocol: `94c18ae8b8e3e025f8a20c0f0deeb77c9714c71777de2494734c8ecf753224e7`.
- Run: `255d7614-dfe4-4e2e-bf74-520f61d2d58f`.
- [Approved configuration](../config/mixed_live_s54_v1.json) and [frozen inputs](../config/mixed_live_s54_frozen_v1.json).
- [S54 live runner](../scripts/mixed_live_s54.py) and [S55 read-only diagnostic report](../scripts/audit_mixed_live_s55.py).

The S55 reporter makes no provider requests and does not alter the live protocol. It first verifies the terminal journal through S54 replay, reconstructs matching state and applies the existing S36 scorer. It exports status fields and case-level diagnostics, not answer text or judge explanations. Active/interrupted prefixes must use S54 read-only replay instead of being presented as final reports.

## What the results may support

The fixed control gate must pass before candidate scoring. First and repeat judgments remain separate; absent or unresolved values never become zero. All 72 cells remain visible. Eight `MEDSAFE-013` conversations stay review-held raw diagnostics. There are **no pooled model means or rankings**. Case-level scores remain provisional and do not establish clinical validity.

The requested lower-tier 60–70, average around 80 and premium around 90 bands remain diagnostic aspirations, not targets used to change labels or rescale scores. Expert review is deferred, not waived. S50's failed gate and historical S48/S49 results remain unchanged.

The registered portfolio remains **125 families / 250 variants**, with four standalone O/P families / eight variants outside this run and the default registry. Approved calibration/Gold remain **0/0**. After this execution, inspect coverage, control failures and repeat stability before choosing another paid batch. Continue distinct source-backed case authoring toward at least 500 families without changing historical inputs; keep Xi'an local.

## Verification

The approved $20 configuration passed all **30 S54/Batch P focused tests** before dispatch. The full existing regression suite passed **962 tests**. The new read-only reporter separately passed **11 offline tests**, including a complete 452-request simulated journal, missing values, review holds, gate failure, unchanged arithmetic, unknown cost, tampering and absence of credential/network access. These are engineering checks, not expert clinical review.
