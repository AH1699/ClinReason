# One supplemental judgment with a larger output allowance

The user approved one new Gemini 3.8 Flash request to judge the saved MiniMax M3 Chinese update that S48 could not finish. This is a separate experiment, not a retry inside S48 or permission to restart the benchmark. The earlier [proposal](../config/judge_cap_followup_proposal.json) is superseded by this implemented protocol.

## Exactly what changes

Reconstruct S48 request 52 from its verified saved answer bank. Change only `generation_config.max_output_tokens` from 8,192 to 32,768. Retain model, medium thinking, case, candidate answer, reference labels, instructions, schema and all other parameters. No new candidate answer, Grok call, private clinical record or purchased asset is sent.

The [configuration](../config/judge_cap_s49_v1.json) binds the original and supplemental request hashes, source directory hash and prior protocol. The [freeze](../config/judge_cap_s49_frozen_v1.json) binds configuration, runner and tests to the unchanged S48 dependency chain. Original payload SHA-256: `b3607e1d1c8996f369d6557dc1d617d6c5ba123ad1be6edbec69cf3741c8e6e3`. Supplemental payload: `4fb122219b8b0626da513368275b291c8bc444273bf1e4a1b0c7ec92e1366a83`.

Google documents that output limits include thinking and can truncate visible output. The model's documented output limit is 65,536, so 32,768 is within that limit. This motivates the diagnostic but does not prove the earlier failure's cause. [Thinking documentation](https://ai.google.dev/gemini-api/docs/thinking/) · [Model specification](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)

## Cost and stop rules

One attempted request maximum, zero automatic retries, fresh private UUID directory and a one-use protocol lock. Authorization records the user's approval before dispatch. The $0.25 policy is a recorded-spending stop threshold with possible last-request overrun, **not a guaranteed ceiling**. Account limits are not assumed. Missing usage remains unknown, not zero. A rejection, interruption or exhausted allowance cannot authorize another call.

Save raw response and accounting locally before validation. Keep strict model, completion, JSON, exact-quotation and required-field checks. Do not repair rejected output. Replay must independently reconstruct accounting and accepted judgment from raw bytes. Credentials stay in memory; raw prose, reasoning and `.env.local` stay outside Git.

## How to report the result

If accepted, combine the new update judgment with the previously validated S48 initial judgment using unchanged 30/70 stage weighting and score arithmetic. Report it as a **mixed-cap supplemental conversation score**: initial 8,192, update 32,768. Do not fill S48's missing cell, compute a new eight-cell panel mean, claim a causal truncation fix or promote this result to clinical validation. Any semantic concern is a separate review flag, not a retrospective score correction.

The accompanying medication-wording contrasts are offline drafts only. No boundary-test API calls, changed reference labels, new case families or broader nine-family run are authorized by this approval. Expert clinical/bilingual review remains later. The 60–70 / ~80 / ~90 aspirations do not determine labels or penalties.
