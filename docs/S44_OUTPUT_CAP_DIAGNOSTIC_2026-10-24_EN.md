# Omitting the output cap did not resolve the Grok rejection

Date: 2026-10-24, New York time

The owner approved one additional paid diagnostic without first setting an account spending limit. The request omitted **only `max_output_tokens`** from the failed Grok judge request. It returned **HTTP 403 with the identical 81-byte error body in 0.201 seconds**. Removing the explicit 8,192-token cap did not resolve this failure; the rejecting component and rule remain unknown.

## Exact comparison

| Setting | Previous S43 clinical request | This S44 request |
| --- | --- | --- |
| Model and endpoint | `grok-4.7`, `/v1/responses` | Unchanged |
| Case, authored answer, labels and output schema | Frozen English initial `HC-MT-MEDSAFE-019` judge request | Unchanged |
| Reasoning and sampling | High, temperature 0.7, top_p 0.95 | Unchanged |
| `max_output_tokens` | 8192 | Omitted |
| HTTP result | 403 in 0.555 seconds | 403 in 0.201 seconds |
| Response body | `permission-denied` and refusal message | Identical bytes |

The response was observed at **10:10:26 p.m. New York time on October 24**, or **02:10:26 UTC on October 25**. No model-answer envelope or usage was returned. **This attempt's charge is unknown, not zero.** A request ID and filtered tracing headers are retained privately.

Omitting the parameter delegates output length to the provider; it does not establish unlimited generation. The [xAI guide consulted for this experiment](https://docs.x.ai/developers/model-capabilities/text/best-practices) documents a 128,000-token default and describes a reached output cap as truncation. The experiment's direct finding is narrower: omission did not fix the observed rejection. It does not prove that every token-related implementation bug is impossible.

## Scope and safeguards

The fresh authorization allowed exactly one request, no automatic retries and no benchmark restart. It retained the $1 recorded-spending stop policy with possible last-request overrun. **That policy cannot cap the cost of this single in-flight request**, and the owner explicitly reported that no account limit had been set. The authorization was consumed before reading the key; it cannot be reused.

Only the same public synthetic case and judge material was sent. No Xi'an records or purchased raw clinical files were transmitted. The endpoint and verified-TLS behavior stayed unchanged; neither the prompt nor schema was rewritten. No diagnostic result was added to benchmark scores.

[`scripts/grok_output_cap_s44.py`](../scripts/grok_output_cap_s44.py) uses the existing private transport and trace capture, with a one-attempt allowance. The frozen protocol is `2fa59faf91de3c19a9cc14f0e4974cdd4bdf4d0618d2e77cb1cd1e790c9e4650`; the modified payload SHA-256 is `fd81f302f2e4fe0828d2d63005b7099e0635d9a9c080ff4b827ec0aa39ff4856`. Restoring only `max_output_tokens: 8192` reproduces the original request object exactly.

Private artifacts are in `work/s44-runs/e6ebacfb-161c-4574-baff-2bfd679ad5cb/`. A read-only post-run audit checked the one-attempt count, sole payload change, original error bytes, response status, authorization consumption, unknown accounting and file permissions. The [public summary](../data/audit/s44_output_cap_summary.json) omits keys, raw clinical text and private tracing IDs. All 13 new offline tests passed before dispatch; historical frozen runner and scoring files were not modified.

## Next step and project status

The full offline suite passes **709 tests**, including the 13 new S44 tests. This verifies software behavior, not clinical validity or the provider's internal reason for rejecting the request.

Use the updated, unsent `work/s43-investigation/xai-support-note.md` to ask xAI to trace the failure and explain its cause, console visibility and charge. The note now includes both capped and parameter-omitted failures. No support message or account change has been made. This result does not justify removing output caps across the benchmark or sending further retries; any new experiment needs its own scope and approval.

There are no new candidate calls, scores or cases. The original first phase remains at nine valid controls and zero candidate calls, including zero MiniMax calls. S43's known diagnostic charge remains $0.004932 plus one unknown attempt; S44 adds one further unknown-charge attempt. The original phase's $0.066317 monitored amount and its own unknown-charge attempt remain separate. The approximately 80-point fixed-roster mean objective is unchanged, with no score fitting. Development stays at **125 families / 250 variants**, plus **three reserved new confirmation families / six variants**; approved calibration/Gold remain **0 / 0**. Expert review stays later.
