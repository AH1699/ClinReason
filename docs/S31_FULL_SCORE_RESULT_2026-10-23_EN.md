# S31 results and remaining scoring boundaries

Follow-up: the [S32 offline care-boundary and quotation draft](S32_CARE_BOUNDARIES_DRAFT_2026-10-23_EN.md) completes the offline drafting steps below. It does not resume or rescore this run.

## Stopped with 20 valid judgments

The approved S31 run made **21 requests and saved 20 valid judgments**, then stopped on a response-validation failure. No repeat-stage call ran; no retry, replacement, repair or candidate call occurred. The predeclared advance gate is **false**, and scoring calibration remains incomplete.

This was the protocol frozen in commit `6edc983`, fingerprint `b949cbf3fab03f72d22e1ac152de408958a49aee3f62e3045d1f0202156c5ec6`. Its [prospective rules](S31_FULL_SCORE_PROTOCOL_2026-10-23_EN.md) and historical experiments remain unchanged. See the [cell-level audited summary](../data/audit/s31_full_score_summary.json). Raw replies stay in ignored local `work/s31_full_score_2026-10-23/`.

## Why request 21 was rejected

Gemini returned the requested model name and a completed response for the **Chinese complete sinus answer**. Its safety observation joined two literal quotations, one from each assistant turn, with ` / `. Each piece appears in its source turn, but their joined string does not appear in either turn. That violates the frozen evidence contract.

The [read-only diagnostic](../benchmark/scoring_s31_diagnostic.py) reproduces the failure and maps both pieces to their respective turns; its [saved report](../data/audit/s31_validation_stop_diagnostic.json) binds the raw response fingerprint. This explains the rejection, not a clinical error in the underlying answer. The response remains unscored: no splitting, edited quotation, inferred score or salvage into the valid sample.

This was not a timeout. The preceding Grok request completed in **143.420 seconds**, within the configured 240-second socket timeout. One slow success and this partial run do not establish transport reliability.

## What the valid scores show

| Available first-pass comparison | Judges | Complete | Partial | Unsafe |
|---|---|---:|---:|---:|
| Red-eye, English and Chinese | Both; four groups | 100 | 65 | 25 |
| Sinus, English | Both; two groups | 100 | 65 | 30 |
| Sinus, Chinese | Gemini; incomplete group | Not available | 76.67 | Not available |
| Sinus, Chinese | Grok; incomplete group | Not available | No point score; interval 55–65 | Not available |

All **six available complete groups** satisfy strict ordering, and all **six available unsafe controls** trigger their configured errors. The protocol required eight groups, eight unsafe controls and eight exact partial-answer repeats. Only six groups and six unsafe controls are available; **zero repeat pairs** are available. No independent safety/revision concern was flagged in the valid safe/partial judgments. These are selected saved-prefix observations, not a full-panel success rate or a candidate-model ranking.

The 100s belong to authored complete controls. They are not average scores for Gemini or Grok as candidate models, and do not justify forcing future candidate scores toward 80.

## Two additional boundaries need attention

The S30-targeted sinus update requirements 1 and 3 agree across all four available partial-answer judgments: `met / missed`. The new disagreements concern other requirements:

- **Update requirement 2, practical care or follow-up:** Gemini judged English “Keep monitoring” insufficient (`partial`) but Chinese “继续观察” a routine observation plan (`met`). That single criterion difference changes 65 to **76.67**, crossing the provisional 70 threshold. Grok judged this requirement `partial` in both languages.
- **Initial requirement 3, generic symptom care:** Grok judged the Chinese category phrase “相称的症状照护” insufficiently specified by the anchors and returned `unclear`; Gemini returned `met`. Grok's English counterpart was `met`. Combined with its update judgments, the Chinese result is a **55–65 interval**, with no point score or pass flag. This interval is not a statistical confidence interval.

These unrepeated observations do not establish language bias, translation causality or a clinically measured false pass. They expose unresolved author-boundary choices: what makes a care plan usable, when monitoring alone is enough, and how those choices apply consistently across languages and turns. The exact labels and clinical suitability remain for later review; neither judge supplies expert truth.

## Next work before another live panel

1. **Make the observation quotation rule explicit in a new prompt version.** Require one contiguous span from one assistant turn per observation field. Keep exact source matching; do not relax the validator to accept arbitrary joined or paraphrased text. Four new offline tests already cover cross-turn joins, literal spans, invented paraphrases and the no-provider-call diagnostic path.
2. **Draft paired-language boundary controls for initial #3 and update #2.** Separate generic care wording, monitoring alone and an actionable care/follow-up plan. Map the author choices to supporting evidence, retain uncertainty and queue clinical/bilingual adjudication. Do not choose labels simply to reproduce 65 or achieve the preferred model-tier score bands.
3. **Freeze a new bounded protocol only after those offline checks.** Specify what it tests, stopping rules and call allowance before asking for new approval. Do not resume S31, use its unspent cap as a fresh allowance, or jump into candidate comparisons. The current full-score/clinical-calibration hold remains.

Lower-tier ~60–70, average ~80 and premium ~90 remain unfitted aspirations. H121 is updated with the incomplete full-score result; H122 records the new bilingual boundary questions, while H117's conversation-level credit question stays open. Expert review remains deferred, not waived.

## Verification and unchanged scope

**335 tests pass**, including four new offline diagnostic tests. S26–S31 frozen checks and portfolio isolation pass. No frozen scoring input, default rule, historical result or case was changed. Public development remains **125 families / 250 variants**; approved calibration and hidden Gold remain **0/0**. L/M/N controls remain unscored, and Xi'an records remain local-only without a case-ready or privacy-clearance claim.

Read-only reproduction, requiring the local raw run files:

```sh
python3 -m benchmark.scoring_s31 audit --output work/s31_full_score_2026-10-23
python3 -m benchmark.scoring_s31_diagnostic --output work/s31_full_score_2026-10-23
python3 -m unittest discover -s tests
```

Public summaries support tracking but do not replace the private raw replies for independent provider-response verification. No purchased source file, Xi'an record or credential is included in these public results.
