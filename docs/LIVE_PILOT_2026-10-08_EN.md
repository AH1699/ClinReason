# Grok → Gemini live integration pilot, 2026-10-08

This is a local, experimental systems check—not a validated clinical result or public model ranking. The case set contains 12 bilingual families / 24 synthetic draft prompts. Grok 4.7 answered as the candidate; Gemini 3.8 Flash supplied one provisional AI judgment per answer. The run ID is `run_a3300db71a1449d6`. Candidate answers and the SQLite run remain under ignored `work/` paths; no API keys or raw answers are in this document.

## What worked

- A one-case live Grok smoke test succeeded, followed by 24/24 full candidate answers. All answers passed exact case-ID/version/hash validation and were imported.
- A one-case live Gemini judge smoke test passed local structured-output and case-bound validation. The remaining 23 judgments were saved and the run scored at 24/24 coverage.
- Candidate calls used only the candidate instruction and prompt. Gemini saw the draft reference, rubric, requirements, critical errors, and anonymized candidate answer. Both providers were requested with `store: false`; neither was given search tools.
- Requested and returned IDs were `grok-4.7` and `gemini-3.8-flash`. These IDs are not proof of immutable model snapshots.

## Provisional output, not performance evidence

The single-judge report is labeled `experimental_unvalidated`. Mean gated score: **98.85/100**; numerical pass rate: **24/24**. English mean: 98.16 (12 cases); Simplified Chinese mean: 99.53 (12 cases). Category means ranged from 97.19 to 100.0, but each category has only four prompts / two bilingual families. The judge assigned 4/4 on 143 of 152 applicable dimension judgments and 3/4 on the other nine. It flagged no configured critical errors. This extreme ceiling pattern gives little evidence that the current rubric/cases/judge can discriminate expert-level performance or catch subtle safety failures.

The scoring engine initially reported zero human reviews required because a high-confidence single judge cleared its confidence threshold. That was misleading: the configured target is two independent judges. The scorer now adds `insufficient_independent_judges`, and this same run was recalculated locally with **24/24 requiring human review**. No additional API calls were made for that correction. This review flag does not itself complete clinical or language case review.

## What this does not establish

The Alpha cases and draft references have not passed qualified clinical or bilingual review. Gemini's judgment has not been calibrated against independent clinician ratings, and one AI judge cannot measure agreement. A high model-graded score or zero flagged critical errors is not evidence of clinical safety, global generalizability, or superiority to another model. Current cases are too few and too straightforward for an expert-level benchmark.

## Next quality step

Before more paid full runs, review a stratified sample of the answer–judgment pairs with qualified clinicians and bilingual reviewers; record where Gemini over- or under-scores. Then expand the development set with harder, source-linked differential reasoning, medication safety, triage ambiguity, and adversarial cases; calibrate multiple independent judges against human ratings; and keep a separate hidden Gold set. Do not publish these pilot scores as a ranking.
