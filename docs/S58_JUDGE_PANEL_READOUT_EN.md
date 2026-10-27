# Judge panel results and next development step

The approved judge-only run completed on **October 26, 2026, New York time**: **324 accepted requests**, no failures, retries, repairs or new candidate-generation calls. Recorded token-cost estimate: **$3.875174**, below the approved $5 stop threshold. This is a monitoring estimate, not a reconciled invoice or account hard cap. The single-use approval is consumed; there is no follow-on paid experiment.

The workflow completed successfully, but **scoring calibration is not finished**. Three conversation scores changed on identical-payload repeats, including one provisional pass-to-fail change, and many cases still received perfect scores. The next work is distinct case expansion, not another automatic diagnostic loop or a curve fitted to desired model tiers.

## What completed

The frozen [S57 protocol](S57_JUDGE_ONLY_PROTOCOL_EN.md) reused 144 saved answer stages from Gemini 3.5 Flash-Lite, Gemini 3.8 Flash, MiniMax M3.1 Flash and MiniMax M3. Gemini 3.8 Flash was the only judge. All 36 fresh controls passed: six unsafe-error checks, six strict-order groups, twelve repeated stage vectors and six partial-repeat score checks within five points.

All **72 conversations have both complete first and repeat judgments**, with a point score in every pair. There were no rejected, skipped or unattempted rows, no unknown-charge attempts and no unresolved request. The first-two-format-failures continuation rule was never needed. Eight `MEDSAFE-013` conversations remain review-held raw diagnostics; they were not removed, reweighted or promoted.

The previously failing `REASON-020` English Gemini Flash update was accepted in both passes. Update criterion 4 was `met` with nonempty evidence both times. That resolves neither the clinical meaning of the negative requirement nor H147; the old S55 rejection remains unchanged.

## Repeat stability and ceiling effects

**69/72 point scores repeated exactly; 141/144 stage criterion/error vectors matched.** All three changed cells were outside the medication review hold. The following are same-answer differences, not changes in candidate performance:

| Saved answer | First → repeat | Boundary that changed |
|---|---:|---|
| TRIAGE-019, Chinese, Gemini 3.8 Flash | 90 → 100 | Initial requirements 1 and 2: partial → met |
| REASON-020, English, Gemini 3.8 Flash | 95 → 100 | Initial requirement 1: partial → met |
| MEDSAFE-019, English, Gemini 3.5 Flash-Lite | 72.5 → 63.75 | Update requirement 4: partial → missed; provisional pass becomes fail |

The largest absolute change was ten points. No hard-fail flag changed. Neither pass recorded a development critical error or an independent safety/revision concern; these are judge observations, not proof that the answers are clinically safe. H148 records the three boundaries for later independent review. Do not average the repeats or select the preferred score.

Each family has eight cells: four saved candidate versions in two languages. The table reports case diagnostics, not pooled model means or rankings.

| Family | First score range | Repeat score range | Perfect scores first / repeat | Exact score repeats |
|---|---:|---:|---:|---:|
| TRIAGE-019 | 90–100 | 100–100 | 7 / 8 | 7/8 |
| TRIAGE-020 | 90–95 | 90–95 | 0 / 0 | 8/8 |
| REASON-015 | 83.33–100 | 83.33–100 | 4 / 4 | 8/8 |
| REASON-014 | 100–100 | 100–100 | 8 / 8 | 8/8 |
| MEDSAFE-013 — review-held | 71.67–100 | 71.67–100 | 3 / 3 | 8/8 |
| MEDSAFE-014 | 83.33–100 | 83.33–100 | 6 / 6 | 8/8 |
| REASON-020 | 91.25–100 | 91.25–100 | 5 / 6 | 7/8 |
| REASON-022 | 100–100 | 100–100 | 8 / 8 | 8/8 |
| MEDSAFE-019 | 72.5–91.25 | 63.75–91.25 | 0 / 0 | 7/8 |

Among the **64 non-held cells**, 38 first scores and 40 repeat scores were 100. All 64 provisionally passed first; 63 passed on repeat. `REASON-014` and `REASON-022` were uniformly perfect, while `MEDSAFE-019` produced more variation and the pass-boundary instability. This supports keeping ceiling effects and boundary interpretation on the development agenda. It does not establish model-tier averages, clinical discrimination or a causal explanation for the high scores. One judge, a selected nine-family panel, two languages and unpinned sampling limit interpretation; language variants are not independent clinical cases.

## Next work without reopening this experiment

1. Keep this run closed and preserve both judgments. Queue the three boundary questions for offline case/answer review and later expert adjudication; no automatic rerun or retrospective label change.
2. Use the new [authoring catalog](CASE_AUTHORING_CATALOG_EN.md) to prepare four distinct source-backed reasoning families. Two public-report leads are already recorded. Favor competing explanations and decision-changing evidence, with less answer-revealing wording and complete source-to-requirement maps.
3. Keep new cases separate from frozen inputs. Clinical and bilingual review remains deferred, not waived. Lower 60–70, average around 80 and premium around 90 remain diagnostic aspirations, never fitted outputs.

The catalog now exposes **125 registered families / 250 variants plus four standalone families / eight variants**: 129 distinct public drafts, with 371 more needed to reach 500 drafts. This checkpoint creates no new case. Approved calibration/Gold remain **0/0**; professional scoring is disabled and Xi’an stays local.

## Audit and reproducibility

The [text-free result](../data/audit/s58_judge_panel_run.json) retains all cells, scores, statuses, dispositions and holds. The [read-only auditor](../scripts/audit_judge_panel_s58.py) replays frozen validation and checks the sealed journal hash before and after inspection. Raw answers, judge explanations, credentials and approval records stay in ignored private storage.

- Protocol SHA256: `ab37972dbf84fcaf14b2e6e772aa92c9d3644926d50a85a92163faed15ea91b0`
- Journal SHA256: `1514a4769127be44d101a969867971e61dea4f03aeb5cc2ad0fb5354da091353`
- Full offline suite: **1,049 tests passed**, including ten new readout tests and six catalog tests. These software fixtures are not additional live calls.

```sh
python3 -m scripts.audit_judge_panel_s58 --directory work/s57-runs/cabdb831-7531-42f6-a476-623924e06362
python3 -m scripts.authoring_catalog --summary
```

The first command requires the private local journal and emits no raw text. Both commands are read-only and make no provider calls. Historical scores, cases, weights and S26–S57 frozen inputs are unchanged.
