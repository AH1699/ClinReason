# Grok failure investigation and limited diagnostic

Date: 2026-10-24, New York time

The owner reports no error entry in the xAI Console for the [stopped first phase](S42_FIRST_PHASE_STOP_2026-10-24_EN.md). The saved HTTP 403 remains valid evidence of a failed request, but **its origin is unresolved**. It is not evidence that the clinical answer was wrong or that the account ran out of credit.

## What the existing evidence establishes

Four Grok requests succeeded before the rejection. Their response files were saved around **11:05–11:06 a.m. New York time on October 24**, or **15:05–15:06 UTC**. These are local file-save times, not a provider log guarantee. Matching these successful calls in the owner's console would help confirm the account and time window; whether they appear remains unanswered.

The rejected request completed in **0.413 seconds**, compared with **7.691–14.534 seconds** for the successful Grok calls. This is consistent with an early rejection, but does not identify the rejecting component. The original capture saved the 81-byte error body, not response headers, a tracing ID or the TLS peer. Those observations cannot be reconstructed afterward.

A new credential-free TLS handshake to `api.x.ai` succeeded with certificate and hostname verification enabled. The certificate covered `*.x.ai` and was issued by Google Trust Services. No standard proxy or custom CA environment variables were present in the current process. The frozen runner uses a direct standard-library HTTPS connection, with no configured proxy tunnel. These checks describe the current setup; they cannot prove the route taken by the old failed request or exclude every intermediary.

[xAI's error guide](https://docs.x.ai/developers/debugging) lists permission or key/team blocking causes for 403. It does not establish the cause here or guarantee that every such response appears in a console error view. No provider support message, key rotation or account change has been made.

## Two paid calls proposed for separate approval

The diagnostic is prepared but **not yet authorized or executed**. It will use the existing local Grok credential and the same verified-TLS endpoint, with no alternate route or payload repair.

1. Send a neutral `grok-4.7` request asking for `DIAGNOSTIC_OK`.
2. Only if the first response is valid and its charge is known and below the threshold, send the **unchanged** rejected public synthetic case/judge request.

The allowance is at most **two requests**, no automatic retries, and a **$1 recorded-spending stop threshold**, not a hard ceiling. A final request can exceed it. Failure, unknown cost, expired authorization or threshold crossing stops execution. A fresh, explicit approval receipt is consumed once before credentials are read. The original benchmark approval remains consumed; unused slots and budget are not reusable.

The second request contains `HC-MT-MEDSAFE-019` in English, its initial authored control answer, draft labels and judge instructions. It contains no Xi'an records or purchased raw clinical files. Both requests may be billed by xAI. Diagnostic judgments will not become benchmark scores.

## How to interpret the result

| Observation | Supported next step |
| --- | --- |
| Neutral request fails | Stop. Use the captured status and safe correlation metadata to investigate access or transport. Do not send the clinical request. |
| Neutral succeeds and original fails | Investigate a request-dependent failure. The requests also differ in size and structured-output requirements, so this does not isolate clinical content as the cause. |
| Both succeed | The original failure did not recur in this diagnostic. Its cause remains unresolved; do not claim the full benchmark is fixed. |
| Usage or delivery becomes uncertain | Stop and reconcile the private capture. Do not assume the call was free or automatically resend it. |

## Implementation and private records

[`scripts/grok_trace_s43.py`](../scripts/grok_trace_s43.py) wraps the existing transport without editing frozen benchmark modules. It records connection/send times, verified TLS observations and a short allowlist of response headers when present. The allowlist includes possible request/correlation IDs, `cf-ray`, server/date and content metadata; their presence is not guaranteed. Authentication headers, cookies, redirects, arbitrary headers, control characters, oversized values and values containing the credential are excluded.

Run artifacts belong only in Git-ignored `work/s43-runs/`; approval receipts and consumed markers belong in `work/s43-authorizations/`. Raw responses, tracing IDs and TLS peer details stay private. Reports preserve known charges separately from unknown or missing accounting records.

The frozen diagnostic protocol is `077b4c39d6b39348c709857bb3ecfc1aafeea8f99f112e6764a3621c435c14d9`. The unchanged second payload has SHA-256 `4308985e8ec686f97acc7ad2d2281d230fb9015d3cfb62ff330510252f8bf64d`. Running the command below checks the freeze only; it does not load keys or make model calls:

```sh
python3 -m scripts.grok_trace_s43
```

## Project status

Verification: **696 offline tests pass**, including 22 new tests for diagnostic capture, header filtering, unchanged payloads, stop conditions, approval scope/expiry/reuse, private permissions and credential-load failures. Offline fixtures are explicitly marked as simulated. The S41 protocol still matches its original hash.

No new paid requests, candidate scores or case changes have been made in this investigation. The stopped phase still has nine accepted control judgments, zero candidate calls and **$0.066317 recorded spending plus one unknown-charge attempt**. MiniMax was not reached. The approximately 80-point fixed-roster mean is still a diagnostic objective, not a forced score target. Development remains **125 families / 250 variants**, with **three new confirmation families / six variants** separately reserved. Approved calibration and hidden Gold remain **0 / 0**. Expert review stays later; S26–S41 freezes remain unchanged.
