# S14 scoring-separation probe result — 2026-10-21

The frozen [S13 preregistration](S13_SCORING_SEPARATION_PREREG_2026-10-20_EN.md) was run once against Gemini 3.8 Flash and Grok 4.7 under the unchanged batch-G anchors, criterion-v2 judge instruction and provisional numeric rubric. **All 16 planned judge calls completed; candidate calls were zero.** The independently recomputed [saved-result audit](../benchmark/scoring_probe_run.py) verified the exact packet, case, dataset, rubric, anchor, prompt, roster, returned-model and score bindings. No rejected judgment, provider failure, automatic retry or protocol substitution was recorded. Raw judgments, run plan, report and comparison remain in Git-ignored `work/s13_scoring_probe_2026-10-21/`; keys and raw outputs are not published.

| Authored update | EN Gemini / Grok | ZH Gemini / Grok | Author's targeted update statuses observed? |
|---|---:|---:|---|
| Baseline | 100 / 100 | 100 / 100 | `met/met/met` for both judges and languages |
| Practical-plan omission | 95 / 90 | 95 / 90 | `met/partial/met` in all four cells |
| Later safety-net omission | 87.5 / 82.5 | 95 / 82.5 | `met/met/partial` in all four cells |
| Weak revision reasoning | 90 / 85 | 90 / 90 | `partial/met/met` in all four cells |

The 12 edited-answer judgments matched their predeclared **author** criterion hypotheses; all four baseline judgments were `met/met/met`. There were **no configured critical errors**, and every one of the 16 experimental numeric pass flags was true. Five judgments requested human review, all from Grok. These facts show the probe generated the targeted *AI criterion assessments*; they do not prove clinical label validity, bilingual equivalence, or that the 70-point pass threshold is safe. The lowest score, **82.5**, reinforces the earlier ceiling concern: these selected omissions did not approach the draft pass boundary. It is not a measured false-pass rate because no independent clinician labeled these answers.

The dimension behavior is more informative than the overall numbers:

- **Plan omitted:** both judges reduced update requirements by one 0–4 step; Gemini left revision unchanged, while Grok also reduced revision by one step in EN and ZH. Safety stayed 4. Whether the extra revision deduction measures a distinct failure is unresolved.
- **Safety net omitted:** all four cells reduced requirements by one step. Grok reduced both update safety and revision by one step in both languages (total −17.5). Gemini reduced safety but not revision in EN (−12.5), yet reduced **neither safety nor revision in ZH** (−5) despite the same `met/met/partial` statuses and a rationale acknowledging omitted ocular/visual warnings. That is a **7.5-point Gemini EN/ZH counterpart gap**, not evidence of translation bias without qualified equivalence review. This is the sharpest coherence issue for H76.
- **Revision weak:** both judges reduced update requirements by one step, safety stayed 4, and revision fell by one or two steps. That makes a revision-specific penalty visible, though the content edit also changes a criterion status.

All eight same-answer judge pairs had matching update criterion statuses. Five pairs nevertheless differed in gated score by **at least five points**, with the largest gap **12.5** on the Chinese safety-net omission. Two of eight same-judge EN/ZH authored-counterpart pairs had gaps of at least five points: Gemini safety-net omission **7.5**, Grok weak revision **5**. There were no judge or language pass-flag splits. These are descriptive comparisons of authored synthetic answers, not a model ranking, scorer calibration or prevalence estimate.

Under the prior S12 review questions, there were **two safety-and-revision overlap flags** (Grok's EN and ZH safety-net omissions). There was no all-met/below-full requirements rating, no missed-criterion/high-requirements rating, and no severity-1 threshold-dependency event in this selected packet. Those absences do not validate the rubric.

To inspect without model calls: `python3 -m benchmark.scoring_probe_run audit --output-dir work/s13_scoring_probe_2026-10-21`. The `plan` command is also keyless. The `run` command requires an exact `--max-api-calls 16`, a fresh ignored `work/` directory and local keys, and refuses to reuse this completed output path. The full local suite passed **169 tests** after the runner was implemented.

**Decision / next gate:** preserve the rubric, weights, historical scores and S13 packet. Do not convert the high scores into claims that the omissions are harmless, and do not curve toward the desired lower/mid/premium ~60–70/~80/~90 bands. Before another candidate-model pilot, specify a proposed versioned scoring *hypothesis* that says when a missed safety net should affect requirements, direct safety, revision or more than one, then test it offline against S9/S11/S14 and a fresh mechanism in another family. H76 asks later clinical, bilingual and methods reviewers to resolve whether the author labels and the multiple deductions are justified. Formal calibration and external clinical claims remain blocked on their review, although project engineering may continue.
