# S45: save answers first, score independently

The owner approved proceeding without waiting for xAI. S45 is a new development pilot. The stopped S41 experiment and consumed S43/S44 diagnostics remain historical records; their unused calls and budgets are not reused. The xAI support investigation is no longer a prerequisite for engineering or case development.

## What changes

Candidate models answer the selected case in English and Chinese before any judge controls run. Each accepted answer is saved immediately with its model, case version/content hash, request hash and raw-response hash. The second turn uses that model's exact saved first answer. Candidate requests contain no reference answers, scoring labels or future-turn information.

Once generation ends, `answer-bank.json` seals the accepted answers. Each judge has its own control checks and scoring lane. A known-cost technical failure closes that model's lane; other lanes can continue. A failed control gate leaves that judge's scores pending and preserves all candidate answers. Unknown charges, an interruption or the shared spending threshold stop all further paid dispatch. No request is automatically retried, repaired or silently replaced. A provider failure is not a clinical zero.

A later judge-only run can pin the bank hash and re-use those exact answers. It sends no candidate requests. Import revalidates the original saved requests, raw replies, model identities, case bindings and bank contents. It keeps the original panel denominator even if some answers are missing. Read-only replay can also recover a fully captured answer after a local result-file write interruption; it never resumes network execution.

The implementation is in `scripts/independent_eval_s45.py`. All existing top-level `benchmark/*.py`, S36 arithmetic and S41/S43/S44 frozen inputs remain unchanged. This avoids changing the meaning of earlier measurements.

## First pilot, fixed before new answers

| Item | Scope |
|---|---|
| Family | `HC-MT-MEDSAFE-013`, an existing conditional medication-safety case |
| Languages | English and Simplified Chinese |
| Candidates | Gemini 3.5 Flash-Lite, Gemini 3.8 Flash, MiniMax M3.1 Flash, MiniMax M3 |
| Judge | Gemini 3.8 Flash; Grok remains deferred |
| Candidate requests | 4 models × 2 languages × 2 turns = 16 |
| Judge controls | 36 on the existing L/M/N authored controls |
| Candidate scoring requests | Up to 16 stage judgments, after the judge's control gate passes |
| Maximum | 68 requests; serial; zero automatic retries |
| Spending | $5 recorded-spending stop threshold; the last request can overrun it |

The $5 threshold is a smaller new pilot scope under the owner's accepted stop-threshold policy, not a verified hard cap or an account setting. Gemini/MiniMax amounts are conservative undiscounted token estimates, not invoices. Rates were checked against [Google pricing](https://ai.google.dev/gemini-api/docs/pricing) and [MiniMax pricing](https://platform.minimax.io/docs/pricing/overview) on October 24, 2026. An unknown charge stops this pilot; historical unknown charges remain separately unresolved.

The selected family tests whether medication exposure changes interpretation of apparently reassuring glucose. This is a workflow sample chosen before answers, not a representative sample of clinical competence. Generation uses the existing S38 payload settings, including output limits of 8192; S44 did not establish that removing limits fixes xAI access. Exact IDs are fixed in the plan, not taken from local default model names.

Only public synthetic cases, authored controls, visible model answers and scoring labels go to the selected providers. Xi'an records, purchased source files, confirmation cases, local secrets and raw reasoning are excluded from benchmark prompts. Provider storage settings retain their existing limitations; local `store=false` is not a promise of zero provider retention.

## Separate control gate and interpretation

The new per-judge gate requires all 36 valid records, all 6 expected unsafe errors, all 6 safe > partial > unsafe orderings, at least 11/12 identical repeat stage vectors, and all 6 partial-score repeats within 5 points. It is declared prospectively and does **not** claim that the original two-judge, 72-record S38 gate passed. These checks test engineering consistency against author hypotheses, not clinical correctness.

Scores use unchanged S36 criterion credit, 30%/70% stage weights and critical-error caps. Every expected model/family/language cell remains in the denominator. Missing cells yield an interval and no complete point mean. Judges are reported separately. Gemini judging Gemini answers introduces self-preference risk; the pilot cannot establish a model ranking, bilingual clinical validity or complete calibration.

The desired lower-tier 60–70, roster average around 80, and premium around 90 remain diagnostic aspirations. We do not alter weights, scores or the chosen panel to force those bands. A one-family, four-model pilot cannot establish the six-model roster average.

## Local operation

```sh
python3 -m scripts.independent_eval_s45 plan
python3 -m scripts.independent_eval_s45 audit
python3 -m unittest tests.test_independent_eval_s45 -v
python3 -m scripts.independent_eval_s45 report --directory work/s45-runs/RUN_UUID
```

These commands do not read API keys or make requests. The explicit `run` command additionally requires a new run UUID and an authorization note recording actual user approval. It loads only the keys needed for the selected providers, keeps them in memory and writes private captures under ignored `work/s45-runs/`. A run directory cannot be reused. The note records operator authorization; it is not a cryptographic consent system and cannot by itself authorize another run under a different UUID.

For a later judge-only plan, set `generate_candidates=false`, pin `source_bank.run_directory` and `source_bank.sha256`, preserve the original candidate/family/language panel, select the judge and declare its new request allowance. Freeze that plan separately before dispatch. Its controls still run independently; old receipts are never resumed.

## Next decision

After this workflow sample, inspect any missing records, control failures, ceiling scores and actual criterion deductions. If the workflow and control gate pass, prepare the existing nine-family balanced development panel with repeat judgments. Do not jump to a public leaderboard. Continue the separate harder Batch O drafts and private Xi'an evidence timeline; neither changes the frozen pilot inputs. Professional clinical and bilingual review remain deferred until the later agreed stage.

Live results will be recorded separately after execution; the specification above does not claim the pilot has completed.
