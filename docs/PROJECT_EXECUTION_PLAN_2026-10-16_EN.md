# ClinReason current execution plan — 2026-10-16

This is the **current project checkpoint**. Earlier batch and progress notes remain historical evidence; update this page after each material batch. None of the current cases, AI judgments, translations, or model comparisons has clinical approval.

## Where the project stands

| Area | Verified current state | Open gate |
|---|---|---|
| Public authoring portfolio | 104 bilingual draft families / 208 language variants: 32 single-turn Global Core, 30 patient two-turn, 42 professional; 26 article-derived professional families have a declared CC BY adaptation trail. | Coverage and source-to-label quality are not established by the count. |
| Calibration and hidden testing | 0 prospective calibration families; 0 hidden Gold families. All 104 existing families are public development cases. | New families must be allocated prospectively and related variants kept together; no public case can be relabeled hidden. |
| Live comparison | Seven configured candidates (two Gemini, two Grok, three MiniMax) and Gemini/Grok judges. One four-candidate triage item was 100 from both judges for all candidates. On one harder reasoning item, MiniMax M3.1 scored 100 from Gemini and 92 from Grok. | Scores are provisional single-item diagnostics, not model rankings or difficulty estimates. The saved Grok answer for the reasoning item remains unjudged. |
| Engineering and access | All three provider keys have passed local connectivity checks; the bounded two-judge MiniMax run completed. The local suite passed 115 tests at this checkpoint. Secrets and raw runs are Git-ignored. | No judge-only recovery path; provider aliases/default sampling and 2,048-token MiniMax cap limit cross-provider comparability. |
| Release | No clinical or bilingual approvals; professional cases have no enabled judge or score. | Human review, criterion-to-source verification, language review, statistical plan, and genuinely hidden testing precede external clinical claims. |

The count and split status are reproducible with `python3 -m benchmark.portfolio_audit`; the run and model details are in [the matrix pilot](MODEL_MATRIX_PILOT_2026-10-15_EN.md), [roster](../config/model_matrix.json), and [calibration plan](SCORING_CALIBRATION_PLAN_2026-10-16_EN.md).

## Decision: address scoring validity next

Do **not** change the rubric weights, subtract points from a correct answer, average the two judges into a purported truth, or tune to make lower/mid/premium models land at 60–70/80/90. Those bands are diagnostic aspirations. First separate three possible causes of high scores: an easy item, an underspecified criterion, or a judge that misses an explicit requirement. Keep critical-safety caps and first-turn safety visible.

### SC-01 — MiniMax M3.1 / celiac-testing judge disagreement (open)

- Fixed item: `HC-MT-REASON-009-EN`, version `0.1.0`, case hash `54dadbdf17977dbb964a2b94cca35490e11b3d2339025380b118e050c5b7ce2b`.
- Fixed artifact: ignored local `work/model_matrix_minimax_m31_reason009_credit_retry_2026-10-16/report.json`. Gemini 3.8 Flash: **100**; Grok 4.7: **92**. Both gave safety 4/4 on each turn, revision 4/4, and no configured critical error; Grok gave requirements 3/4 on both turns versus Gemini's 4/4.
- Initial-turn question: the label says **ask whether gluten was eaten regularly before testing**. The candidate explained why gluten intake matters and told the person to disclose their intake, but did not directly ask that question. Does functionally equivalent guidance satisfy this requirement, or is the explicit question part of the construct? The current key does not define the boundary. Grok penalized it; Gemini did not.
- Update-turn question: Grok viewed “inconclusive unless your clinician knows exactly how much gluten you were eating” as potentially imprecise despite the explicit statement that the negative test does not rule out disease. Whether that wording warrants a requirements deduction is unresolved. Do not infer a clinical error or adjust the score from one judge's interpretation.
- [NIDDK's public diagnosis page](https://www.niddk.nih.gov/health-information/digestive-diseases/celiac-disease/diagnosis) supports that a gluten-free diet can affect diagnostic tests and that symptoms alone do not establish diagnosis. It does not by itself settle the scoring-equivalence question or verify the candidate's specific challenge regimen. Record this as a source-to-criterion review need, not as clinical approval.
- Disposition today: **no adjudicated score, case-label edit, or rubric-weight change**. Both original judgments and their disagreement remain visible and require later qualified review.

## Execution sequence and acceptance gates

| ID | Work, in order | Evidence required before advancing | Status |
|---|---|---|---|
| S1 | Preserve current run, hashes, disagreement, and decision boundary. | Reproducible raw artifacts remain local; public docs state the exact gap and unresolved criteria. | Done in this checkpoint. |
| S2 | Draft item-level anchors for a balanced development panel: `TRIAGE-010`, `MEDSAFE-007`, `REASON-009` in EN/ZH, plus simpler non-emergency controls. For each required behavior, define **met / partial / missed / unclear**, acceptable equivalents, evidence citation, and critical-error boundary. Start with SC-01. | Anchor packet is versioned, linked to exact case hashes and public sources, and marked provisional pending clinical/language review. No score weights change. | **Next**. |
| S3 | Add a judge-disagreement audit and safe judge-only recovery for saved answers; require criterion-level evidence in the next judge contract while preserving historical report versions. Test strong, partial, omission, and unsafe fixtures offline. | Deterministic tests show binding to case/rubric/prompt hashes, no secret leakage, no automatic candidate replay, and explicit safety gates. | Planned. |
| S4 | Pre-register a small, cost-capped bilingual live comparison on exactly matched case revisions and independently selected reference models. Keep each judge's score separate; measure full-score ceiling, criterion misses, safety false passes, language gaps, and disagreement. | Complete paired reports, call/cost ceiling, model provenance, and a descriptive audit; no public ranking. Expand to all seven candidates only after this pilot is interpretable. | Planned; no new calls authorized by this document. |
| S5 | Revise only invalid or non-discriminating items/anchors based on evidence, version all changes, and rerun affected candidates. Build new prospective calibration and hidden families in parallel, honoring provenance/leakage groups. | Change log explains each revision; unchanged holdout never used to tune; human clinical/language review remains a release gate. | Planned. |

If an unsafe answer passes, a severity-2/3 error is disputed, or an item lacks an evidence-backed scoring boundary, pause comparative claims for that item and add it to the reviewer queue. A score-band target is never a reason to bypass that gate. Professional scoring stays separate until its own validated contract exists.

## Tracking convention

After each batch, update this page's state, SC issue register, artifact links, decision, next action, and test count; add a dated note when a decision changes. Keep key values in ignored `.env.local` and raw model outputs in ignored `work/`, not in Git. Commit source, labels, rubrics, and plans with explicit version/provenance; publish only reviewed aggregate claims. The immediate next executable task is **S2: a provisional criterion-level anchor packet and SC-01 resolution proposal**, not a larger model spend.
