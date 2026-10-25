# S46: continue the same pilot without repeating requests

S45 obtained seven HTTP-successful candidate replies. Its accounting guard accepted six, then stopped on MiniMax M3's returned `service_tier: default`, although our request explicitly selected `standard`. The seventh response contains valid token counts, a normal completion and a visible answer. This was a local billing-compatibility stop, not an API-access failure. No judge requests had run.

S46 preserves the stopped S45 record and applies a separate, frozen compatibility amendment. It reuses all seven saved replies, including the seventh visible answer, with their original case, request and raw-response hashes. The first new job is original sequence 8: M3's English follow-up using its exact saved initial answer. Nothing already attempted is sent again.

## Scope and spending

- The combined pilot remains at most **68 requests**: 7 already attempted plus at most 61 new requests (9 candidate turns, 36 controls, 16 candidate judgments).
- The shared **$5 recorded-spending stop threshold** carries forward prior spending; it is not a new $5 allowance or a hard account cap. The last request can overrun it.
- A consumed-source file prevents a second continuation under a fresh run ID. No automatic retries, response repair, budget resets or Grok requests.
- All unrelated unknown-usage/charge conditions still stop further dispatch. An ordinary known-cost model failure closes that model's lane.

[MiniMax's API documentation](https://platform.minimax.io/docs/api-reference/text-chat-openai) describes the requested tiers, but does not establish that a returned `default` means standard billing. We therefore do **not** assert that equivalence. For this exact explicit-standard M3 request/returned-default combination, with validated short-context usage, monitoring uses the higher published priority rates and no cache discount: $0.45 per million input tokens and $1.80 per million output tokens ([pricing](https://platform.minimax.io/docs/pricing/overview), checked October 24, 2026).

The seventh reply has 402 input and 7,306 output tokens; its 6,819 reasoning tokens are already within that output count. The conservative estimate is $0.013332, added to the preceding $0.019296, for **$0.032628 carried forward**. This is a transparent monitoring estimate, not a verified service tier, invoice or hard upper bound. S45's historical unknown-cost record stays unchanged; S46 records the new assumption explicitly.

## Reproducibility and interpretation

The amendment lives outside frozen `benchmark/*.py`, in `scripts/independent_eval_s46.py`, `scripts/transport_s46.py` and `scripts/minimax_accounting_s46.py`. Its plan and source captures are hash-bound. Read-only replay recomputes usage, answers and scores from saved captures and cannot resume execution. Original S41/S43/S44/S45 records and their budgets remain separate.

The S45 four-model, one-family EN/ZH design, Gemini-only control gate and S36 scoring remain unchanged. Self-judging bias, unreviewed clinical/language labels and the tiny sample still preclude model rankings or claims of finished calibration. Desired score bands remain diagnostic aspirations, never fitting targets. Only public synthetic benchmark material is sent; Xi'an records, purchased files and secrets are excluded.

```sh
python3 -m scripts.independent_eval_s46 audit
python3 -m unittest tests.test_independent_eval_s46 -v
python3 -m scripts.independent_eval_s46 report --directory work/s46-runs/RUN_UUID
```

These are offline checks. Live execution requires the approved continuation command and a fresh run ID, and consumes the one continuation slot. Results will be documented separately; this specification does not claim the continuation has completed.
