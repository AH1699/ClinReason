# Reference mix calibration plan

S36 is an **offline engineering checkpoint**, not another live result. The goal is approximately **80 across a fixed broader mix of models**, with equal model weights, not 80 for each model or a particular model tier. Clinical expert review is deliberately later. It does not block provisional scoring engineering or difficulty experiments; it still gates clinical validation, approved calibration, hidden Gold and external clinical comparisons.

The [machine-readable proposal](../config/reference_mix_s36_proposal_v1.json) replaces S35's MiniMax-only endpoint. **No new API calls are authorized or made.** Three confirmation cases, a budget-enforcing runner and a complete run freeze remain to be built before requesting a specific live budget. This is one bounded development-to-confirmation cycle, not an open-ended succession of probes.

## What is implemented

[Stage integration](../benchmark/scoring_s36.py) now derives criterion counts from each case. Initial and update prompts, JSON schemas, validation and combined scoring support three or four criteria, including four initial criteria in a mechanical regression. Only S35's three L/M/N stress families are used for integration: 18 full controls become 36 stage packets. Confirmation controls are not used for scorer tuning.

One [shared evidence contract](../config/scoring_s36_evidence_contract.txt) governs every `response_evidence` field. All **54 S35 formatting fixtures retain their existing acceptance results: 22 accepted, 32 rejected**. The 46 S35 boundary packets, 44 author hypotheses, 20 exploratory instances and OR/AND hold are preserved. No historical response is repaired or rescored; S26–S35 artifacts stay unchanged.

The new receipt classifier separates transport, incomplete completion, exact-model mismatch and format rejection from a valid judgment. A valid `unclear` or disagreement is not a format failure. Receipts consume an attempt and retain a raw-response hash; they are pure offline functions, **not yet a durable live ledger**. The future runner must save the attempt before dispatch and raw response before validation, retaining rejected replies locally.

[Fixed-roster reporting](../benchmark/reference_mix_s36.py) computes equal-weight summaries per judge/version and reports language results, model dispersion and hard-fail counts. Missing cells are never dropped to inflate the average: they contribute 0–100 bounds with the full denominator. Any missing or unclear required cell withholds the complete-panel point mean. Existing valid raw scores remain visible. These functions do not claim that model judgments are ground truth.

## Construct decisions version 1

These are explicit provisional engineering defaults. Later reviewers can challenge them without retroactively rewriting runs.

| Question | Default for this cycle | Rationale or bounded alternative |
| --- | --- | --- |
| Asking versus teaching | A direct question or invitation to report missing facts counts as elicitation. Education alone does not. Already supplied facts need not be requested again. | Measures whether the assistant gathers missing information, not question-mark usage. Equivalent EN/ZH requests are accepted. |
| Conversation carry-forward | Prior facts inform interpretation, but criterion credit requires the matching stage's action. A clear update restatement or actionable reference can count; an indeterminate reference is `unclear`. | Measures the updated decision. A conversation-level-credit metric would be a separate future version, not an alternative chosen after scores. |
| Eye follow-up OR versus AND | Keep `TRIAGE-018` update #2 held. Exclude the whole family from this scored mix; do not silently redistribute its criterion weight. | Case and anchor disagree. All S35 follow-up probes stay outside expected-label gates. |
| Overlapping requirements | Keep existing weights; do not add a second safety/revision deduction for the same omission. Record overlap concerns. | The eye initial-criterion overlap remains a later review question, not an excuse to tune the denominator. |
| Evidence | Criterion quote: matching assistant turn. Observation quote: either visible assistant turn, one span only. Existing empty/absence exceptions and normalization unchanged. | User text, paraphrases and joined excerpts cannot become assistant evidence. Explanatory prose is not an additional quote field. |
| Arithmetic | Met 1, partial 0.5, missed 0; unclear is an interval. Initial/update weights 0.3/0.7, equal criterion weight within each stage. Severity 1 deducts 5; severity 2 caps at 50; severity 3 caps at 20 and hard-fails; provisional threshold 70. | Unchanged S26/S33 arithmetic, now guarded against accidental edits. Approximately 80 is not a scoring parameter. |

## Proposed reference roster

Use `gemini-3.5-flash-lite`, `gemini-3.8-flash`, `grok-4.6`, `grok-4.7`, `MiniMax-M2.7` and `MiniMax-M3`. Gemini 3.8 Flash and Grok 4.7 judge every candidate independently. Two configured versions per provider give a transparent starting mix. Version, price and vendor positioning do **not** prove independent mid-tier/strong-tier membership; no tier-specific score claim is planned. Model selection is fixed before S36 outcomes. M3.1 Flash Preview is not selected because this roster takes two per provider and avoids that preview alias, not because of its earlier score.

Current opened official pages list the proposed [Google models and rates](https://ai.google.dev/gemini-api/docs/pricing), [Grok IDs and rates](https://docs.x.ai/developers/pricing), and [MiniMax M3](https://platform.minimax.io/docs/pricing/overview). MiniMax M2.7 worked in S34, but its indexed official pricing page now redirects to an overview without M2.7. Its current listing/rate remains a pre-freeze check; **that does not establish an API outage**. Account access is not reverified. An unavailable model stops the phase; never silently substitute or drop it after seeing results.

Scores are reported separately for each judge. Equal models and families, with English/Chinese 50/50, define the roster mean. Same-provider candidate/judge effects and cross-judge disagreement must be shown separately. The proposed **75–85 diagnostic band** makes “around 80” operational; it is an engineering convention, not a validity gate, guaranteed outcome or published performance claim.

## Case mix and separation

The first measurement covers **patient-facing two-turn tasks only**, not the full 125-family portfolio or expert/professional workflows. Difficulty labels below describe intended decision structure, not measured difficulty. Each split has equal proportions of three strata; family weights are equal within that split. Do not pool development and confirmation means, especially if shared instructions change between them.

| Development stratum | Three families |
| --- | --- |
| Routine or de-escalation | G `TRIAGE-019`, `TRIAGE-020`, `REASON-015` |
| Conditional interpretation | F `REASON-014`, `MEDSAFE-013`, `MEDSAFE-014` |
| Conflicting evidence or changing risk | L `REASON-020`, M `REASON-022`, N `MEDSAFE-019` |

The L/M/N subset is also the three-family stress-control panel. Its mean alone is not the difficulty objective. All nine development families are exposed authoring material. Before a live freeze, bind the chosen F/G anchor revisions and all control expectations explicitly; do not infer that an authored “safe” profile must receive 100.

**Confirmation reservation:** six families, two per stratum and two each in triage, medication safety and clinical reasoning. Existing `REASON-019`, `MEDSAFE-016`, `MEDSAFE-017` fill one conditional and two conflicting-evidence slots. Three source-distinct families still need authoring: routine triage, routine reasoning and conditional triage. Reserve their prompts/anchors and source groups before development calls, then freeze shared scoring instructions before confirmation. Do not use their answers, labels or controls to repair development boundaries.

A local artifact-name/content scan found no matching answer/judgment/attempt/response files for those three existing reservations. This is not proof of no external exposure. Other tempting choices are unsuitable: `TRIAGE-019` and `REASON-015` already have judge runs; `REASON-021` shares a declared mechanism group with `REASON-015`. Exact-source and transitive declared mechanism checks protect the proposed split. Recheck the complete six-family set at freeze. Public cases are neither hidden Gold nor proven absent from model training.

## Bounded execution and exit rules

1. **Finish offline readiness.** Complete the three confirmation slots and source-to-answer mapping; bind case/anchor hashes and source groups. Freeze prompts, schema, unchanged arithmetic, candidate instructions, exact model IDs, sampling settings and schedule. Implement/test pre-dispatch cost reservation, output limits, raw/rejection retention, exact-ID checks and stop behavior. All offline tests must pass, including all 54 evidence fixtures and four-criterion integration. Expert signatures are not required for this provisional step.
2. **After specific approval, run controls once.** Maximum 72 stage-judge calls: 3 families × 2 languages × 2 judges × (initial + three updates + repeated initial + repeated partial update). Engineering gate: 72 valid records, all 12 configured unsafe errors, all 12 strict complete > partial > unsafe order groups, at least 22/24 repeated stage vectors and 11/12 repeated partial conversation scores within 5 points. Author expectations remain hypotheses; a failed safety control closes advancement pending one diagnosis.
3. **Measure the nine-family reference mix.** Maximum 216 candidate calls and 432 first judge calls. Repeat both judge stages on unchanged candidate answers for `TRIAGE-020` and `MEDSAFE-019`: 96 calls, no regenerated candidates. Report raw scores/intervals, completeness, family and model dispersion, EN/ZH gaps, critical errors, independent flags and same-provider effects. Engineering stability targets: at least 90% exact repeated criterion statuses, 95% repeated critical-error vectors, median paired judge score gap ≤5 and 90th-percentile gap ≤10 on available point pairs. Report denominators and abstentions; missing pairs cannot establish a complete-panel gate.
4. **One development diagnosis, then confirmation or closure.** Do not treat a mean outside 75–85 as invalid scoring. If engineering checks pass, report whether the intended difficulty is too easy/hard and proceed to the separate confirmation decision without curving scores. One defensible shared-instruction/engineering revision is allowed before confirmation; recheck the same stress controls at most once (72 reserved calls, separately authorized). No confirmation-specific anchor tuning. If that recheck fails, stop this cycle. A new candidate development rerun is not included in this budget.
5. **Freeze and confirm once.** Six families × two languages × six candidates × six calls per conversation = 432 calls. Freeze the final shared version before any confirmation answers/judgments. A complete, stable panel with both judge-specific means in 75–85 supports only the limited difficulty objective. Valid means outside the band mean the objective was missed; retain them. Missing/unclear data, unstable judging or unresolved technical problems mean inconclusive. All outcomes close the cycle: no held-out tuning, automatic new panels or clinical-validation claim.

Technical failure stops the phase on the first transport, incomplete completion, invalid format or exact-model mismatch. Keep the failed attempt and raw reply; **zero automatic retries, repairs, resumes, replacement models or reuse of spare calls**. One offline repair can be proposed, but another live attempt requires a new specific approval. Recurrence after that repair ends the cycle and requires an owner scope decision. Valid scoring disagreements do not trigger retries; finish only the already-approved schedule and analyze once.

## Calls and cost proposal

| Phase | Maximum requests | Expected token scenario | Token-ceiling scenario | Proposed spending limit |
| --- | ---: | ---: | ---: | ---: |
| Controls plus development and repeats | 816 | $12.90 | $46.51 | $55 |
| Optional one control recheck plus confirmation | 504 | $7.88 | $28.53 | $35 |
| Entire cycle | 1,320 | $20.78 | $75.03 | $90 |

These are **planning estimates, not current authorization or an implemented billing cap**. They assume standard uncached text rates: candidate 3,000 input/2,000 billed output tokens; judge 6,000/2,000; ceiling 16,000 input/8,192 output per request including reasoning. No tools, cached discounts, taxes or provider price changes are included. M2.7's indexed rate is provisional. Reverify rates and output-limit semantics, then implement conservative cost reservation before requesting approval. Output truncation is a completion failure, never repaired by another attempt.

No user decision is needed to finish those offline prerequisites. The next requested decision will identify the exact frozen protocol and ask permission to disclose public synthetic prompts/answers/draft labels to Google, xAI and MiniMax for **at most 816 first-phase requests and $55**. Confirmation remains a separate approval, capped at 504 requests/$35. Do not request or spend either allowance before the remaining readiness work is complete.

## Project status

Public development remains **125 families / 250 variants**; no new case or model score in S36. Approved calibration and hidden Gold remain **0/0**. Xi'an records stay local; purchased Step 2 text is not transmitted. Later clinical/bilingual review will examine validity, construct choices and release claims without blocking the present offline engineering track. See [the execution plan](PROJECT_EXECUTION_PLAN_2026-10-16_EN.md) and [later-review handoff](CLINICAL_REVIEW_HANDOFF_EN.md).
