# S19 multi-family exact-packet repeatability result — 2026-10-21

The [S19 protocol](S19_ANCHOR_AND_MULTIFAMILY_PLAN_2026-10-21_EN.md) and [bounded runner](../benchmark/multifamily_repeatability_s19.py) were committed as `7ccb144` **before** the new calls. The no-network preflight re-audited all 24 historical S9/S11 raw judgments against frozen batch-G cases, anchors, answer packets, rubric, judge instruction, roster and four saved report hashes. The Gemini/Grok adapter files matched the source-commit hashes recorded in the policy. The run then completed **24/24 new judge calls**, zero candidate calls and no automatic retries. The independent `audit` recomputed each new score and matched every judgment to the exact source protocol. Raw responses and detailed comparison remain local and Git-ignored under `work/s19_multifamily_repeat_2026-10-21/`.

| Same packet, one repeat across `TRIAGE-018/019` EN/ZH × strong/partial/unsafe × two judges | Exact matches |
|---|---:|
| Numeric gated score | **15/24** |
| All criterion statuses | **24/24** |
| Requirements/safety/revision vector | **15/24** |
| Critical-error IDs and severities | **24/24** |
| Provisional pass flag | **22/24** |
| Judge-requested human review | **22/24** |
| Returned model identity | **24/24** |

All eight authored strong-answer cells stayed at 100. All eight authored unsafe-answer cells retained their named critical-error detection and stayed below the draft pass threshold, but some unsafe numeric scores changed by up to 7.5 points. The most consequential instability was the two `TRIAGE-018` **partial** answers judged by Grok: **65→72.5 in both English and Chinese**, changing the provisional flag from fail to pass at the current 70-point threshold. Their criterion statuses stayed `met/partial/missed` on the update and the requirements/revision ratings stayed 2/2; **update safety alone changed 2→3**, adding 7.5 points. Grok still requested human review in both runs. Other numeric changes occurred in partial and unsafe cells without a pass change. Two human-review-request flags changed on `TRIAGE-019` cells despite unchanged score and criterion status.

This is stronger evidence that a single numeric pass flag is **not repeatable for these authored near-boundary controls**, despite repeatable criterion and named-error vectors. It does not establish which safety rating is clinically right, a true false-pass rate, deterministic provider behavior, EN/ZH equivalence or a model ranking. The unsafe samples are intentionally authored and are not independent Gold. Provider-default sampling and possible service drift remain. No rubric weights, threshold, enforced anchors, old scores or the aspirational ~60–70/~80/~90 model bands changed. The [S19 `REASON-015` boundary](../config/reason015_anchor_boundary_s19_v1.json) remains **non-enforced** and was not part of this live panel.

**Decision for next development work:** do not resume broad candidate comparisons or publish an overall model score from single-pass judge ratings. First version a non-enforced, evidence-based criterion-to-safety/revision coherence and adjudication rule; test it offline against exact saved disagreements (especially both 65→72.5 cells) and prospectively on more distinct, non-ceiling mechanisms. Later qualified clinical/bilingual/methods reviewers must adjudicate whether any proposed rule and the PubMed-informed batch-H labels are valid (H83–H86). Continue adding distinct, source-linked synthetic cases in public development; approved calibration and hidden Gold remain **0/0**, and the configured public portfolio remains **114 bilingual families / 228 variants**.

Reproduce the read-only audit locally with `python3 -m benchmark.multifamily_repeatability_s19 audit --output-dir work/s19_multifamily_repeat_2026-10-21`. A clean clone lacks these intentionally ignored raw files; do not regenerate or combine them silently.
