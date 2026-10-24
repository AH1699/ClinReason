# S39 response capture and usage accounting

The response-capture component now preserves complete or partial HTTP bodies before parsing, and accounts for provider-reported usage separately from clinical scores. **557 tests pass, including 42 new tests**, covering the full 816-step first-phase and 504-step confirmation-with-recheck workflows with fake HTTP connections. No credentials were loaded, provider calls made, account settings changed, cases added or model scores measured.

## What is implemented

[The capture component](../benchmark/transport_s39.py) writes the attempt and exact request body before opening the injected connection. It saves response chunks locally before interpreting JSON. HTTP errors, redirects, malformed JSON, missing usage, wrong model IDs, incomplete answers and interruptions stop the run without retry. An interrupted response retains the bytes actually received; it does not imply that the provider stopped generating or billing.

Requests use fixed provider hosts and paths. There is no redirect following, automatic retry, environment/key loader or enabled production connector. Test requests use a fixed dummy credential. Files are created with owner-only permissions in fresh directories; request headers and exception text are excluded from metadata. Full bodies remain private and may contain provider reasoning, while only visible answer text enters scoring. A response-byte limit retains a marked prefix on overflow; the between-read deadline is not a server-side cancellation guarantee.

Tests connect this component to the unchanged S38 schedule and validation logic. The first-phase control gate, stage isolation, all six candidate models, two judges and separate repeat results remain intact. The production entry point still rejects every live-run request; actual HTTPS wiring and approval admission are unfinished.

## How costs are recorded

[The accounting module](../benchmark/usage_s39.py) keeps three categories separate:

| Record | Treatment |
|---|---|
| Grok provider-reported charge | Keep the exact integer `cost_in_usd_ticks`; do not rebuild the charge from possibly different token-count conventions |
| Gemini or MiniMax token estimate | Apply the frozen short-context standard price to reconciled counters; do not invent cache discounts or call this an invoice |
| Missing, invalid or unsupported usage | Mark cost unknown, retain raw evidence and stop; never treat it as free |

[xAI documents](https://docs.x.ai/developers/cost-tracking) that one dollar equals 10 billion billing ticks and that the per-request figure includes applicable discounts and token/tool charges. This is an after-the-request observation, not a limit on the next request. Tool use remains excluded from this benchmark protocol.

[Gemini Interactions](https://ai.google.dev/api/interactions-api) reports answer and thought tokens separately. The estimate includes both and rejects an unreconciled total. [MiniMax](https://platform.minimax.io/docs/api-reference/text-chat-openai) reports prompt, completion and total counts; the completion aggregate is used once, without adding reasoning a second time. These estimates ignore cache reductions and cannot settle an account invoice.

Valid usage is retained even when later answer validation fails. Transport failures and model-identity mismatches retain unknown normalized costs and raw evidence where available. Reports show separate charge and estimate subtotals plus the number of unknown attempts; they do not claim a complete cross-provider invoice. None of this proves a prospective spending ceiling.

## Next decision and implementation

The unresolved spending choice is whether a hard ceiling is required or whether the owner would accept an observed-spend stop threshold. A hard ceiling needs verified request bounds or suitable provider-side controls. A threshold can stop subsequent calls, but the last in-flight request can overshoot, and a failed response can leave its charge unknown. The previous $55 first-phase / $35 confirmation figures remain proposals, not enforced caps. No such choice or paid-run approval is assumed here.

After that policy is settled, wire the real HTTPS connector to the exact schedule, verify account/model eligibility within the approved call scope, finalize effective generation settings, and freeze phase-specific export, attempt and billing authorization. Keep approval for confirmation separate. A new live run needs explicit authorization; a generic continuation or the MiniMax roster choice does not supply it.

The six-model roster remains Gemini 3.5 Flash-Lite / 3.8 Flash, Grok 4.6 / 4.7, and MiniMax M3.1 Flash / M3. Scoring is unchanged; ~80 remains the fixed-roster mean objective, not forced normalization. Development remains 125 families / 250 variants, plus three separately reserved new families / six variants. Approved calibration/hidden Gold remain zero. Expert review stays later; H129 joins the open handoff items. Xi'an, purchased assets and keys stay local.

Reproduce the snapshot audit with `python3 -m benchmark.transport_s39` and the regression suite with `python3 -m unittest discover -s tests -q`. [Policy and evidence](../config/transport_s39_v1.json), [frozen snapshot](../config/transport_s39_frozen_v1.json), [audit summary](../data/audit/s39_capture_summary.json). S26–S38 frozen artifacts remain unchanged.
