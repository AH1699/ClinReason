# Two request transport diagnostic

Before another full scoring panel, S29 tests the exact English sore-throat partial packet whose Grok request stopped S28. This is a new diagnostic, not a retry, continuation or repair of S28. Its output cannot be pooled with earlier panels.

The frozen sequence is **Grok 4.7, then Gemini 3.8 Flash**, at most **two judge requests**, zero candidate calls and zero retries. The prospective socket timeout is **240 seconds**, compared with S28's 120 seconds. This is a diagnostic choice, not evidence of a fix or a hard wall-clock deadline. Prompt, case, answer, anchors, response schema, scoring arithmetic and provider sampling defaults remain exactly those of S28. Requested and returned model IDs must match.

Each attempt is recorded before sending; raw responses are saved before validation. Stop on the first transport, model identity or validation failure, with no repair/resume. The new observer saves only an allowlisted error category, HTTP status if available, elapsed time, delivery status and retry count. It never exports credentials, URLs, headers, bodies or free-form error messages. Failed delivery/billing may remain unknown. Local raw artifacts stay under ignored `work/`.

The file/packet manifest and tests must pass and be committed before live calls. Both valid responses permit **designing a separately frozen full scoring/repeat panel**, regardless of numeric scores. They do not establish reliability, repeatability, clinical calibration or achieved score bands. No larger live panel is authorized by this protocol itself. A failure instead leaves a specific transport/validation issue to investigate. Expert review remains deferred, not waived.

Run once with `python3 -m benchmark.transport_s29 run --output work/s29_transport_2026-10-23 --max-calls 2`; independently recheck with `python3 -m benchmark.transport_s29 audit --output work/s29_transport_2026-10-23`.
