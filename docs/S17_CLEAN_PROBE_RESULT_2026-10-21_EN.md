# S17 punctuation-clean `REASON-015` result — 2026-10-21

The [S17 packet and eight-call cap](S17_SCORING_EVIDENCE_AND_CLEAN_PROBE_2026-10-21_EN.md) were committed before the live run. Gemini 3.8 Flash and Grok 4.7 completed **8/8 judge calls, zero candidate calls, no automatic retries**. The [independent saved-result audit](../benchmark/scoring_dimension_evidence_s17.py) rebuilt exact packets, checked case/probe/policy/anchor/rubric/prompt/roster and returned-model bindings, and recomputed scores. Raw judgments and the audit remain local in Git-ignored `work/s17_reason015_clean_2026-10-21/`.

| Language / judge | S16 omission | S17 clean omission | S17 update criterion 3 | S17 requirements / safety / revision delta | S17 pass / human-review request |
|---|---:|---:|---|---|---|
| EN / Gemini | 90 | 82.5 | partial | −1 / −1 / −1 | yes / no |
| EN / Grok | 77.5 | 90 | partial | −1 / 0 / −1 | yes / yes |
| ZH / Gemini | 82.5 | 95 | partial | −1 / 0 / 0 | yes / no |
| ZH / Grok | 82.5 | 90 | partial | −1 / 0 / −1 | yes / yes |

All S17 baselines scored 100 and all baseline update criteria were `met`. No configured critical-error ID was returned. The clean Chinese punctuation removed a known textual defect, but **both English omission scores and Grok EN's criterion status changed too, although the English answer was byte-identical to S16**. The model services' nondeterministic outputs and single observation per cell prevent attributing any numeric shift to the punctuation correction. In S17, Gemini lowered direct safety only in EN, while Grok lowered revision in both languages; their rationales cite the missing forward-looking safety net but do not themselves establish independent clinical grounds for each dimension. The identical `partial` status in all four cells still produced 82.5–95.

The result strengthens the *need to investigate* score coherence and repeatability; it is not a calibrated false-pass rate, a proof of double counting, bilingual approval or clinical ground truth. The [S17 offline flags](S17_SCORING_EVIDENCE_AND_CLEAN_PROBE_2026-10-21_EN.md) remain non-enforced. Do not change historical scores, weights, threshold or the aspirational ~60–70/~80/~90 model bands from this public authored contrast. Public development remains **112 bilingual families / 224 variants**; approved calibration and hidden Gold are **0/0**.

**Next scoring gate:** before a wider candidate pilot, specify a small repeatability design with fixed provider settings and a cost cap, plus case-specific evidence notes distinguishing direct harm from simple requirement incompleteness. Later qualified clinical/bilingual/methods review should adjudicate [H78/H80](CLINICAL_REVIEW_HANDOFF_EN.md). If repeatability is poor, treat pass flags as provisional and report criterion patterns and judge disagreement rather than a single definitive model score.
