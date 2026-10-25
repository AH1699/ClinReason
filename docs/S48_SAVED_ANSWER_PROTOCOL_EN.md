# Scoring the saved Gemini and MiniMax answers

This experiment checks the complete independent judge control set, then scores the 16 answer stages already saved from four candidate models. It generates no new candidate answers and does not wait for xAI. The owner approved the proposed 52-request, $2 stop-threshold plan with “go ahead.”

## What runs

Gemini 3.8 Flash is the only called model. The first 36 requests judge existing bilingual authored controls for `REASON-020`, `REASON-022` and `MEDSAFE-019`, including repeats. All IDs have the `HC-MT-` prefix.

Only if the complete control gate passes do the remaining 16 requests score the saved initial and update answers for `MEDSAFE-013`. Four models × two languages give eight expected conversation records: Gemini 3.5 Flash Lite, Gemini 3.8 Flash, MiniMax M3.1 Flash and MiniMax M3. Missing or uncertain scores remain visible, not zero and not dropped from the denominator.

The source is the sealed S46 answer bank, verified against saved requests and raw provider responses before import. No prior judge result is imported. The new instructions retain the [S47 explanation clarification](S47_JUDGE_COMPLETENESS_PROTOCOL_EN.md); cases, authored answers, anchors, validator and S36 numerical rules remain unchanged. Initial-stage packets still exclude later facts. Candidate identity and authored control-profile names are not sent in the scoring packet.

## Fixed checks and stopping rules

The control gate requires all 36 valid judgments, all six unsafe errors, strict strong > partial > unsafe ordering in all six language/family groups, at least 11 of 12 identical repeated criterion/error vectors, and all six partial-score repeats within five points. These are the existing independent-workflow requirements, not newly relaxed conditions. Observation flags are retained separately and add no numeric penalty; the S47 overlap inconsistency remains H139 for later review.

The run stops on the first transport, response-validation, model-identity or unknown-accounting failure, on control-gate failure, or when recorded spending reaches **$2**. The final request may exceed that threshold; it is not a hard ceiling. There are no retries, resumes, automatic expansions or reused earlier allowances. A one-use protocol lock prevents a fresh UUID from silently resetting the allowance.

Requests retain the existing 8,192 output-token cap, medium thinking setting and standard service tier. Token-based monitoring uses $0.75 input / $3.75 output including thinking per million tokens, verified on October 25, 2026 against [Google's published pricing](https://ai.google.dev/gemini-api/docs/pricing). Monitoring is not an invoice, and an unknown charge remains unknown.

## Evidence retained and interpretation

Private append-only capture saves each attempted request before network dispatch, then its raw response, usage, acceptance result and context hash. Read-only reconstruction must match the final report. Public summaries contain counts, scores and flags; keys, raw response prose and reasoning stay out of Git. Only existing public synthetic benchmark material goes to Google; no Xi'an or purchased records are included.

The result is a provisional one-family workflow measurement, not a ranking, finished calibration or evidence that the average model scores around 80. Gemini self-judging, unreviewed labels, one case family and no candidate-answer scoring repeats limit interpretation. The lower 60–70 / average ~80 / premium ~90 aspirations stay unfitted. Expert clinical and bilingual review remains deferred, not waived.

After completion, inspect criterion-level deductions and any uncertainty intervals before building the separately proposed [nine-family panel](NEXT_DEVELOPMENT_PANEL_EN.md). A failed run preserves its evidence and does not authorize another paid attempt.

Implementation: [runner](../scripts/judge_saved_bank_s48.py), [tests](../tests/test_judge_saved_bank_s48.py), [plan](../config/judge_saved_bank_s48_v1.json), [freeze](../config/judge_saved_bank_s48_frozen_v1.json). The earlier [proposal](../config/judge_saved_bank_next_proposal.json) remains the historical pre-implementation record.
