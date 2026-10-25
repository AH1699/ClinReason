# Judge explanation completeness test

The previous pilot saved all candidate answers but stopped because Gemini left three mandatory explanation fields blank. This small test asks whether clearer field descriptions and a final checklist can produce complete judgments without changing how answers earn credit. It does not generate new candidate answers or restart the larger benchmark.

## Eight requests on existing authored answers

Use Gemini 3.8 Flash on `HC-MT-REASON-020`, the family whose safe English update failed. Send the existing strong, partial and unsafe update answers in English and Chinese, then repeat the two strong-answer packets byte for byte: **eight requests total**. Two accepted initial judgments from the previous pilot are checked against their saved raw responses and exact initial packets, then reused locally to calculate authored-control conversation scores. They are not included in the judge prompts.

Only the update instruction checklist and four observation-field descriptions change. Case text, answers, anchors, S36 arithmetic and validation, model, sampling and the 8192-token output cap stay fixed. No malformed output is repaired, and a failed request is not retried. The two repeats are predeclared measurements after successful first passes, not recovery attempts.

The new run stops at **$1 in recorded spending**, with possible last-request overrun; this is not an account hard cap. It also stops immediately on any invalid response, unknown charge or interruption. One consumed-protocol record prevents starting it again under another run ID. No unused authorization or budget from earlier runs is reused. [Google's standard pricing](https://ai.google.dev/gemini-api/docs/pricing), checked October 25, 2026, remains $0.75 input and $3.75 output per million tokens for this model; monitoring estimates are not invoices.

Only public synthetic controls and draft labels go to Gemini. No Grok calls, candidate answer text, private Xi'an records, purchased source files or credentials are included in the new prompts. Raw captures stay under ignored `work/s47-runs/`.

## What counts as passing this diagnostic

All conditions are fixed before the new responses:

- All eight update judgments pass the unchanged validator, including mandatory explanations and exact evidence rules.
- Both unsafe answers trigger the configured critical error.
- Strong > partial > unsafe conversation scores in both languages, using the same imported initial judgment within each language.
- Both strong-answer repeats retain identical criterion statuses, critical-error lists, observation decisions and scores.
- All four strong-answer judgments report no distinct safety or revision failure. Filling a required field must not become a reason to invent a failure.

These are checks against author hypotheses, not clinical ground truth. Success on one family does not establish the full 36-record judge gate, candidate scores or clinical calibration. There is no concurrent old-prompt control arm, so a successful run would not isolate a causal effect of the checklist versus field descriptions or model variation. Desired score bands are not acceptance criteria.

## Local verification and next decision

The implementation and frozen inputs are `scripts/judge_observation_s47.py` and `config/judge_observation_s47_*`. All historical frozen files remain unchanged. The documentation stays in this repository's existing bilingual format.

```sh
python3 -m scripts.judge_observation_s47 audit
python3 -m unittest tests.test_judge_observation_s47 -v
python3 -m scripts.judge_observation_s47 report --directory work/s47-runs/RUN_UUID
```

These commands are read-only/offline. The explicit live command additionally consumes the approved eight-request scope. If the diagnostic passes, prepare a separate 52-request judge-only plan: 36 full controls, then 16 stage judgments of the saved four-model candidate answers. That next plan needs its own freeze and authorization; it is not automatically launched here. If this diagnostic fails, retain the exact failing field or boundary and investigate without changing historical scores.
