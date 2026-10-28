# S65 — smaller judge requests and a fixed feasibility test

Updated October 28, 2026, America/New_York. **Offline preparation only: no paid calls, no new model scores and no changes to historical results.**

## What is finished

The judge can now receive each assistant answer once, split into lossless, numbered text chunks. It selects a continuous range by its first and last reference; the local validator retrieves the exact original text. The reference still contains all 256 hash bits, encoded more compactly. Packet, source, stage, ordering and required-evidence checks remain intact, as does S36 arithmetic.

The output schema no longer repeats the full list of possible references. This makes it smaller but shifts membership enforcement to our strict local validator. A schema-shaped answer with an invented ID is still rejected. Whether a model can reliably copy these IDs is **not yet measured**. A valid reference can still be irrelevant, too broad or clinically wrong; local source checks do not prove those things.

The [implementation](../scripts/evidence_refs_s65.py), [fixed preparation policy](../config/compact_feasibility_s65_v1.json), [code/input freeze](../config/compact_feasibility_s65_frozen_v1.json) and [offline rehearsal](../scripts/compact_feasibility_s65.py) are separate from S64 and the closed S62 run. Initial requests expose no future turn or update-observation instructions. The candidate never receives judge labels or reference answers.

| Previously problematic source packet | S64 full input, characters | S65 full input, characters | Reduction |
|---|---:|---:|---:|
| Event 223, Chinese initial | 33,372 | 11,994 | 64.06% |
| Event 232, Chinese update | 60,149 | 17,444 | 71.00% |
| Event 278, Chinese update | 34,113 | 12,458 | 63.48% |

These compare the same complete input/instructions/schema serialization, not an old packet alone against a new full request. The six actual provider request bodies range from 13,666 to 25,745 UTF-8 bytes. **Characters and bytes are not provider token counts.** No token-counting API or account access was used. Three smaller control inputs shrink by 16.57–18.50%.

The [public rehearsal record](../data/audit/s65_compact_feasibility_rehearsal.json) reports 16 captured fake requests: 12 structurally valid judge fixtures, six matching fixture vectors and four completed candidate fixtures. These are deliberately authored plumbing fixtures, not evidence of judge accuracy, MiniMax completion or an empirical gate pass. The source loader first independently replays the closed S62 journal, checks its exact hash and checks the three source-packet hashes; the journal remains unchanged. Public output contains hashes/counts, not saved answers, reasoning or judge text.

## The next empirical batch is fixed, not open-ended

This is the proposed scope; **it is not spending authorization**.

1. Gemini 3.8 Flash judges six saved packets once, then the same six again: **12 requests**. Three are the source packets behind failures 223/232/278. The controls are REASON-027 English safe update, REASON-024 English partial update and REASON-025 Chinese unsafe update. All three controls were previously format-valid. Selection covers the affected families, both languages and safe/partial/unsafe profiles, rather than selecting a desired score. No old rejected judgment is repaired or replaced.
2. MiniMax M3.1 Flash answers REASON-027 in English, initial then update; MiniMax M3 answers that family in Chinese, initial then update: **four requests**. Each revisits its previously affected language. Update history uses only that new run's visible initial answer, never old or reference answers. New MiniMax answers are not sent for additional scoring in this batch.
3. Both MiniMax models get a **32,768 completion-token limit**, adaptive thinking; Flash retains explicit maximum effort. This changes the cap, not the intended reasoning/history policy. Gemini keeps medium thinking and its 32,768 output limit. No unlimited output, retries, model substitution, new case selection or automatic broader run.

The MiniMax language assignment is deliberately diagnostic and confounded across models: it does **not** support comparing their quality or speed. The judge panel includes only one initial-stage packet and five update packets; it is not representative bilingual calibration.

## Rules decided before seeing new outputs

The small batch may advance to broader confirmation only if all the following hold:

- All **12/12** judge outputs pass identity, completion, schema, exact-reference and stage checks; all **6/6** repeated criterion-status/configured-error vectors match. Different valid evidence ranges are retained and inspected, not averaged.
- The unsafe control's configured error is identified in both repetitions; the safe and partial controls have no configured critical errors. These are provisional author hypotheses, not clinically certified controls. No target numerical score or ordering is imposed.
- All **4/4** MiniMax turns finish normally with usable visible text and reconciled usage. Length-limited or empty output remains a failed completion, not a clinical zero.
- No unresolved delivery or cost issue. Every nonnull evidence range and null exception receives a documented local preliminary relevance/overbreadth review, with no unresolved problem before advancing. This review must inspect the actual answer and requirement, not just confirm that the ID exists. It is not independent clinical adjudication and adds no extra paid judge request.

Keep all results even when a rule fails. Known-cost invalid judge output closes the judge lane, but the independent MiniMax diagnostic can continue. Known-cost invalid MiniMax output closes only that model's remaining turns. Unknown delivery/cost, integrity failure or the shared spending threshold stops everything. Failed/missing observations are never converted to zero or silently replaced. There is no automatic retry or resume.

## Spending and provider checks

Proposed shared **$3 recorded-spending stop threshold**, with possible overrun from the last request—not a hard ceiling. At the documented rates, assuming at most 16,000 input tokens and 32,768 billable output tokens on every request, the planning envelope is approximately **$1.80**, using the higher M3 monitoring rate where its response tier is unverified. This is an assumption-based estimate, not a measured token count, provider invoice or guaranteed maximum.

Official documentation was checked at 2026-10-28 03:56:48 UTC. Refresh it within 24 hours of any future dispatch. [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) lists standard Flash 3.8 at $0.75 input / $3.75 output per million through December 2026. [MiniMax pricing](https://platform.minimax.io/docs/pricing/overview) lists Flash at $0.15/$0.60 and short-context M3 standard at $0.30/$1.20; M3 priority is $0.45/$1.80. No cache discount or tool allowance is assumed.

[Gemini's schema guide](https://ai.google.dev/gemini-api/docs/structured-output) supports the simple object/array/nullable structure used here and warns that large enumerations can cause complexity failures; local validation remains necessary. The [Interactions reference](https://ai.google.dev/api/interactions-api) documents the model and configuration fields. This is a documentation check, **not** evidence that the exact new schema has been accepted live. [MiniMax's parameter reference](https://platform.minimax.io/docs/api-reference/text-openai-api) supports the chosen completion-limit/thinking fields; Flash omits unsupported service-tier configuration. Both retain separated visible answer text.

The current accounting adapter accepts only observed input usage of at most 16,000 tokens. Larger usage is out of scope and stops globally as unknown/unreconciled cost; smaller byte size does not certify that limit beforehand. The 65,536-byte request ceiling is a separate local size guard. Do not reuse the old input-token assumption as a proven cost bound. Historical S62's consumed $20 permission is not reusable.

## What remains before a paid run

The policy and offline captured transport rehearsal are finished. **S65 intentionally has no live entry point.** The remaining implementation is a separately frozen live adapter: bind these exact inputs/settings, fresh pricing and single-use human approval; persist reservations, raw captures and accounting before validation; reconstruct/replay the new reference format; preserve crash/unknown-cost stops; export only sanitized results. Candidate update payload hashes must bind the newly obtained initial answer—the public fixture update hashes cannot authorize real answers.

After that adapter's tests pass, request fresh approval for the exact 16-request scope and $3 stop policy. Do not ask the owner to approve an unimplemented runner or dispatch on the strength of this document alone. Reusing a frozen packet as diagnostic source data does not authorize uploading private Xi'an/purchased records, which remain excluded.

The development finish line is still conditional on **two empirical batches**: this feasibility batch and a predeclared broader bilingual/multi-family confirmation if it passes. Clinical calibration is a different, later gate requiring independent ratings and held-out evaluation. The owner's lower/mid/premium aspirations of roughly **60–70 / 80 / 90** remain difficulty diagnostics; no score curve, changed arithmetic or post-result label fitting has been introduced.

Case inventory is unchanged: **135 public draft families / 270 variants**, 365 families short of the 500-family draft goal; approved calibration/Gold **0/0**. Batch R and further source-backed authoring remain separate from this fixed test. H147/H148/H153/H154 remain open; [H155](CLINICAL_REVIEW_HANDOFF_EN.md) adds reference relevance, mixed-clause chunks and clinical qualifiers for later independent review.

Verification: **1,221 full-suite tests passed** in 703.260 seconds. After removing an obsolete initial-stage “only” instruction that conflicted with the new binding fields, all 30 S65 tests were rerun successfully, and the freeze/rehearsal were regenerated. Separate mechanical checks on all 96 saved control packets and three failed source packets preserve the complete transcript and exact current-stage text. All 1,414 checked local Markdown links resolve. Historical source/journal and S41/S57/S60/S61/S62 freezes are preserved. No API keys, Xi'an records, purchased assets or raw replies belong in the public checkpoint.
