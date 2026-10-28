# S66 — fixed feasibility run ready for fresh approval

Updated October 28, 2026, America/New_York. **Engineering readiness only: no paid requests, new model scores or clinical validation.**

## What is now finished

The separate [live adapter](../scripts/compact_live_s66.py), [execution policy](../config/compact_live_s66_v1.json) and [freeze](../config/compact_live_s66_frozen_v1.json) implement the unchanged [S65 feasibility plan](S65_COMPACT_FEASIBILITY_EN.md). S65 remains the historical preparation record; the old S62 run and all its failures/scores stay untouched.

The adapter requires fresh, single-use human approval tied to the exact frozen code, inputs, prices and request scope. It records consumption before reading a key or connecting, checks approval again before each request, and refuses reuse, retries, resume or substituted inputs. Keys stay in ignored local configuration. Consent records and raw captures stay in private ignored `work/` directories, never in the public report.

Every request is reserved before transport. The raw reply and accounting are saved before judging whether the answer is usable. Read-only replay rebuilds the decision from the raw reply rather than trusting a saved accepted result. Interrupted delivery remains unsettled/unknown; replay does not reconnect or repair an answer. Known-cost judge failure closes judging; known-cost candidate failure closes that candidate's remaining turns. Unknown cost/delivery, integrity failure or the shared spending threshold stops the run.

An offline test found that sorting JSON object keys while saving a packet changed the embedded request string on replay. The input snapshot now preserves original field order and binds that serialized form. This preserves S65's frozen provider payloads; it does not change prompts, labels or arithmetic.

These local approval records are operator attestations of human consent, not cryptographic proof of consent or protection against a hostile operating-system user. Capture hashes detect inconsistencies under the trusted-local-operator model; they do not authenticate a provider independently.

## Exact next request scope

| Work | Model | Maximum requests |
|---|---|---:|
| Judge the same six frozen packets, then repeat all six | Gemini 3.8 Flash | 12 |
| New English REASON-027 initial answer and follow-up | MiniMax M3.1 Flash | 2 |
| New Chinese REASON-027 initial answer and follow-up | MiniMax M3 | 2 |

The six judge packets are three saved failure-source packets (223/232/278) and the predeclared safe, partial and unsafe controls. Candidate follow-ups receive only their own new visible initial answer. No private Xi'an records or purchased source documents are sent; only the fixed synthetic benchmark material, saved synthetic-case answers, draft labels and instructions are in scope. The new MiniMax answers are not additionally judged in this batch. Grok remains excluded from this diagnostic; it is not assigned a zero.

Both providers keep a **32,768 output/completion-token limit**. There is one request in flight, no retry or automatic larger run, and a separate 65,536-byte request limit. MiniMax Flash retains adaptive thinking/maximum effort; M3 retains adaptive thinking/standard service tier; Gemini retains medium thinking. The fixed assignments are diagnostic, not a fair comparison between MiniMax versions.

## Spending decision to approve

**At most 16 requests, with a shared $3 recorded-spending stop threshold and possible overrun from the final request. This is not a hard ceiling.** Unknown cost stops further dispatch rather than being recorded as free. The planning envelope of about $1.80 assumes every request stays within the documented 16,000-input/32,768-output-token accounting scope; neither input bytes nor this estimate proves a billing maximum. Usage estimates are not invoices. Observed input beyond 16,000 tokens is out of scope and stops as unreconciled cost.

Official [Gemini prices](https://ai.google.dev/gemini-api/docs/pricing), [Interactions fields](https://ai.google.dev/api/interactions-api), [MiniMax prices](https://platform.minimax.io/docs/pricing/overview) and [MiniMax parameters](https://platform.minimax.io/docs/api-reference/text-openai-api) were rechecked at **2026-10-28 04:27:45 UTC**. Prices/settings are unchanged from S65. This was public documentation verification, not account, invoice or live-compatibility verification. Dispatch requires evidence no more than 24 hours old and unexpired approval. Refresh/re-freeze before seeking consent if that window expires; never rewrite a protocol after its paid run to keep it executable.

The consumed S62 $20 approval cannot be reused. S66 has **no human approval recorded** at this checkpoint. The owner's instruction to finish the adapter was not treated as permission to spend.

## Verification and interpretation

All **35 S66 tests passed** with fake transport. Coverage includes single-use receipts, credentials read only after admission/reservation, expiration before the next request, dispatch-time checks during replay, source/payload tampering, input order, no retries, unknown usage, HTTP failures, candidate length failures, lane isolation, threshold overrun and interrupted writes. Live-path tests use fabricated test-only attestations and mocked connections; they make no real provider request and do not authorize one.

The separate [public offline audit](../data/audit/s66_compact_live_rehearsal.json) uses the actual verified six source packets and captures/replays all 16 **fake** replies: 12 judge fixtures, six matching fixture repeat vectors and four candidate fixtures. Its simulated token estimate is $0.027810, not spending and not a prediction of the real run. Source identity and the old journal remain bound to S65. Public output contains only hashes, counts, status and synthetic accounting—not raw answers, reasoning or approval evidence.

Even a technical gate pass leaves `overall_feasibility_passed` false. Every actual evidence reference and allowed null must still be inspected locally for relevance, excessive breadth and omitted qualifications before advancement. Structural source matching does not establish clinical meaning. [H155 and the clinical review handoff](CLINICAL_REVIEW_HANDOFF_EN.md) remain open; this local preliminary review is not independent clinical sign-off.

Full regression verification: **1,256 tests passed in 745.608 seconds**, including the 35 S66 tests. All 1,481 checked local Markdown links resolve. The public audit was independently reproduced, all 70 bound public files are checked, historical freezes match and the original source journal hash is unchanged. The 16 public changed files contain no detected credential patterns or private asset paths. Keys, raw journals, approval evidence and purchased assets remain excluded from Git.

## How far from finishing scoring calibration?

The next work is empirical, not another planned adapter build: **(1) this bounded feasibility run and local evidence review; (2) if it passes, a separately predeclared broader bilingual/multi-family confirmation.** Two batches are a conditional development estimate, not a promise that calibration will be finished. A failure is recorded and classified before deciding a specific repair; do not loop automatically or relabel results to pass.

Clinical calibration still needs independent ratings and held-out evaluation later. The desired lower/mid/premium bands of **60–70 / around 80 / around 90** remain difficulty diagnostics, never a forced score curve. S36 arithmetic, historical results and draft labels are unchanged.

Inventory remains **135 public draft families / 270 language variants**, with 365 families still needed for the 500-family draft target; approved calibration/Gold remains **0/0**. No cases were added in this engineering checkpoint. Case authoring can continue separately without changing this frozen diagnostic. Xi'an stays local; expert review remains deferred, not waived.

## Local entry points

`python3 -m scripts.compact_live_s66 proposal` shows the scope without requesting credentials. `replay --directory <private-journal>` reads saved results without networking. `rehearse --source-directory <closed-S62-journal> --directory <fresh-private-directory>` performs fake transport only.

Only after explicit owner approval, record the actual consent and exact protocol hash in a private, ignored `work/s66-approvals/<approval-id>.json` file. Use `preflight --approval <that-file>` to validate it; the separate `run --approval <that-file> --source-directory <closed-S62-journal>` entry point consumes it once. Approval requires canonical approval/run UUIDs, approval/expiry timestamps (at most 24 hours), the approving operator and consent evidence, plus explicit acceptance of paid calls, provider disclosure, last-request overrun, no retry/resume, failure gates and provisional reporting. No command creates approval automatically. Do not copy a unit-test attestation into a live run.
