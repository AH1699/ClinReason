# Eight-family pilot: controls and provisional results

The separately approved [S62 execution](S62_STANDALONE_LIVE_PROTOCOL_EN.md) is now closed. It stopped at the third judge-format failure after **278 requests / $2.590216 monitored usage**, retaining **39 complete first-pass scores and six complete repeats**. The control gate passed, but the candidate panel and repeat study are incomplete. The October 27, 2026 owner approval and its unused allowance cannot be reused.

## Control result

| Predeclared check | Observed result |
|---|---:|
| Valid control replies | 96/96 |
| Predeclared unsafe behaviors detected | 16/16 |
| Safe/shared-initial controls with critical errors | 0 |
| Identical-packet repeat criterion/error vectors matching | 32/32 |

The author-control screen passed. All 32 repeated vectors matched, exceeding the predeclared minimum of 31. There were also no critical errors on the incomplete controls. The monitored cost through the 96 controls was **$0.955293**; this is an estimate from recorded usage, not an invoice or hard spending ceiling.

This result supports proceeding under the declared development protocol. It does not validate the clinical labels, prove score ordering, measure clinical false-pass rates or complete scoring calibration. Incomplete-answer scores were not forced into a target band.

## MiniMax output-limit events

Both MiniMax models returned successful answers before a later request ended with `finish_reason: length`. These were complete, usage-accounted provider responses, but not completed candidate answers. They closed the affected model's candidate lane under the predeclared policy; the Gemini lanes continued. No token limit was raised and no answer was retried.

| Request | Model and affected turn | Reported completion tokens | Reported reasoning tokens |
|---|---|---:|---:|
| 134 | M3.1 Flash, REASON-027 English update | 8,190 | 8,156 |
| 141 | M3, REASON-027 Chinese initial | 8,192 | 8,191 |

The candidate output setting was 8,192 tokens. The captured usage shows that almost all available completion tokens went to reasoning on these two requests. This is an output-budget limitation of the tested configuration, not evidence of an API outage or a clinically incorrect finished answer. Previously accepted MiniMax turns remain available for the declared judging steps; rejected/missing turns cannot earn a conversation score. Future cross-model work must review the candidate reasoning/output budget prospectively, without rewriting this run or assigning zero to missing results.

## Candidate answers available

Generation is complete. Each model was assigned 16 bilingual variants, each with two turns. The actual result is **83 accepted turns from 85 requests**, two incomplete replies and 43 planned turns skipped after lane closure. This leaves **41 complete conversations and one additional initial turn**, not a complete four-model panel.

| Candidate | Accepted turns / 32 planned | Complete conversations / 16 planned | Additional initial-only conversations |
|---|---:|---:|---:|
| Gemini 3.5 Flash-Lite | 32 | 16 | 0 |
| Gemini 3.8 Flash | 32 | 16 | 0 |
| MiniMax M3.1 Flash | 9 | 4 | 1 |
| MiniMax M3 | 10 | 5 | 0 |

The two MiniMax samples are incomplete prefixes, not representative substitutes for their planned panels. Availability is not a score or ranking. Spending through control screening and generation was **$1.362954**; judging is accounted separately in the final total.

## Closed execution and stop reason

The run made **278 requests: 273 accepted and five rejected**. The monitored usage estimate is **$2.590216**, with **zero unknown-cost attempts** and no unresolved reservation. It stopped on the third cumulative judge-format failure, not on the $20 spending threshold. No retry, repair request, fallback or resume was used.

| Phase | Planned maximum | Attempted | Accepted | Rejected |
|---|---:|---:|---:|---:|
| Controls, including repeats | 96 | 96 | 96 | 0 |
| Candidate generation | 128 | 85 | 83 | 2 |
| First candidate judgments | 128 | 83 | 81 | 2 |
| Repeated candidate judgments | 128 | 14 | 13 | 1 |
| Total | 480 | 278 | 273 | 5 |

Of the 202 planned jobs not called, 88 had already been marked skipped by dependency/lane rules and 114 remained unreached when the global stop occurred. The saved report's `unattempted_jobs` field means those 114 unreached jobs; it does not include the 88 separately reported skips.

All three judging failures were nonempty criterion quotations that failed the required contiguous-span check against the permitted saved answer. These are evidence-format failures, not clinical failure scores:

| Request | Phase and candidate answer | Affected evidence |
|---|---|---|
| 223 | First; REASON-027 Chinese initial, Gemini 3.8 Flash | Requirement 2 |
| 232 | First; REASON-024 Chinese update, Gemini 3.8 Flash | Requirement 2 |
| 278 | Repeat; REASON-025 Chinese update, MiniMax M3.1 Flash | Requirement 1; triggered the declared stop |

The same original replies remain rejected. No quote was silently corrected, and the two invalid first judgments did not authorize replacement judgments. Raw text stays in the ignored local journal; the [public result](../data/audit/s63_standalone_pilot_run.json) contains only structural outcomes, provisional scores and hashes.

## What the scores tell us so far

There are **39/64 complete first-pass conversation scores**, ranging from **65 to 100**. Thirteen of those 39 scores are 100, and 26 are below 100. Thirty-six provisionally pass the draft threshold and three do not; none has a configured hard-fail error. These are observations against draft labels, not clinical correctness or safety estimates. All 64 cells remain review-held, including the 25 without a first conversation score.

| Family | Complete first scores / planned | First-score range | Perfect scores / completed |
|---|---:|---:|---:|
| REASON-025 | 8/8 | 88.33–100 | 1/8 |
| TRIAGE-024 | 8/8 | 76.67–100 | 6/8 |
| REASON-027 | 4/8 | 95–100 | 3/4 |
| REASON-024 | 3/8 | 65–88.33 | 0/3 |
| MEDSAFE-020 | 4/8 | 83.33–88.33 | 0/4 |
| MEDSAFE-021 | 4/8 | 65–100 | 1/4 |
| REASON-026 | 4/8 | 68.75–100 | 1/4 |
| TRIAGE-025 | 4/8 | 73.75–100 | 1/4 |

Model composition differs across these rows because both MiniMax lanes closed early. Do not interpret the ranges as comparable family difficulty estimates, rank models or calculate a representative four-model mean. The observed variation is useful for inspecting criteria; it does not establish the desired 60–70/~80/~90 model bands or justify changing labels to reach them.

Only **six complete repeat pairs** were obtained, all from REASON-025. All six point scores matched exactly, with no provisional-pass or independent-dimension-review change. All **13 available stage-level repeat vectors** matched, comprising the 12 stages in those six pairs plus one additional initial stage. The other seven families have no candidate repeats, so overall scoring repeatability remains unmeasured. First and repeat scores are not averaged.

The offline language screen checked all **83 accepted candidate turns**, found no obvious wrong-script flags and left 45 rejected/missing turns unchecked. This does not validate language quality or EN/ZH equivalence.

## What the readout preserves

The [read-only auditor](../scripts/audit_standalone_s63.py) first replays the captured responses under the unchanged frozen S62 implementation. It checks the journal before and after inspection and refuses to publish an active or interrupted prefix as a terminal result. It does not load credentials, contact a provider, repair a reply or resume a run.

The public summary retains all **64 expected conversations**, with first and repeat judgments separate. Missing results stay missing; unclear criteria remain intervals. Each cell retains its model, language, case revision, content hashes and review holds. Case-level score ranges, perfect-score counts, criterion/error vector changes and provisional pass changes are descriptive diagnostics, not model rankings or clinical performance estimates. Raw answer text, judge quotations, reasoning and approval text remain local.

The existing conservative language screen flags obvious English-script answers to Chinese prompts and the reverse. It checks accepted candidate turns only and reports its denominator. Short or mixed-language answers may escape this screen; an unflagged answer does not establish language quality or bilingual equivalence. The screen makes no score adjustment.

## Boundaries unchanged

The eight O/P/Q families remain draft and held for clinical and bilingual review. Public inventory remains **133 families / 266 variants**: 125 registered families plus eight standalone drafts. No new family or default-registry entry was created by this run; the target of 500 still needs 367 additional families. Approved calibration/Gold remain **0/0**.

Xi’an and purchased source records remain local and were not included in provider requests. No Grok request, retry, fallback or extra diagnostic is part of this execution. The lower-tier 60–70, average around 80 and premium around 90 aspirations remain diagnostic goals, never a curve to fit. The consumed approval does not authorize another experiment or reuse of unspent allowance.

## Verification and next work

The saved public result reproduces from the terminal journal with the frozen S62 protocol. The auditor checks raw captures through replay, stage/model/case bindings, spending and before/after journal hashes; it exports no raw answer or judge text. **1,171 offline regression tests passed**, including 19 S63 tests for missing/interval handling, repeat differences, text exclusion, tampering, active-prefix refusal and the language-screen denominator. These are engineering checks, not clinical validation.

From the project directory, the local operator can inspect the retained run without another provider call:

```sh
python3 -m scripts.audit_standalone_s63 --directory /absolute/project/path/work/s62-runs/RUN_UUID
```

Next work is offline first, not another automatic paid diagnostic:

1. Prototype source-bound evidence-span identifiers, so the judge selects an allowed saved-answer span rather than retyping a quotation. Preserve stage isolation, exact source hashes and rejection of unknown/wrong-turn references. Test the idea against the three rejected packets and valid controls; do not repair historical judgments or change clinical scoring labels. This is proposed work, not an implemented replacement.
2. Review MiniMax reasoning/output budgets for a separately versioned future protocol. Preserve the present settings and incomplete results; do not remove limits or automatically retry these calls.
3. Continue a separate source-backed expansion batch toward 500 families, with original bilingual cases, answer requirements and source-to-answer checks. Inspect recurring deductions and perfect-score concentration without treating them as proof of clinical difficulty or fitting scores. Expert review remains deferred, not waived.
