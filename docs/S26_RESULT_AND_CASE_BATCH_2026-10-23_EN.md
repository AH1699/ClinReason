# S26 result, Step 2 batch L and Xi'an verification

## Current result

Public development now contains **122 bilingual families / 244 language variants**: 32 Alpha single-turn, 48 patient two-turn and 42 professional. Five new families are original synthetic drafts, not actual patient records or evidence of expert-level difficulty. Approved calibration and hidden Gold remain **0/0**. All **234 local tests** pass at this checkpoint.

Scoring work progressed, but calibration is **not complete**. The preregistered S26 run stopped after a transport failure on attempt 14, preserving 13 valid judgments. It did not reach the repeat stage, and its advance gate is false. No candidate model was called and no retry was made. The failed request's delivery/billing state is unknown.

## What the scoring experiment changed

The [frozen protocol](S26_CRITERION_SCORE_PROTOCOL_2026-10-23_EN.md) was committed as `624a564` before the live run. It is opt-in and leaves the default rubric, cases, anchors, old scores and 70-point diagnostic threshold unchanged. Instead of free-form numeric ratings, the judge identifies criterion status; software converts met/partial/missed into fixed credit. Unclear returns an interval without a point score. Named critical-error rules remain, while separate safety/revision observations flag review without another numeric deduction. S26 scores have a new definition and must not be pooled with historical ones.

Returned model identities were `gemini-3.8-flash` and `grok-4.7`. Exact saved responses were re-audited against the frozen packets and recomputed scores. The [portable summary](../data/audit/s26_saved_prefix_summary.json) includes response hashes; raw responses remain in ignored `work/s26_criterion_score_2026-10-23/`.

| Diagnostic | Observed result | Limitation |
|---|---|---|
| Valid judgments | 13 of 32 planned; 14 attempted | Grok request 14 failed in transport; no response to inspect |
| Named unsafe-error detection | 4/4 available unsafe cells | Only the red-eye family reached unsafe controls |
| Strict point-score ordering | 2/4 complete triplets | Grok abstained on one criterion in both unsafe language versions |
| Partial-answer repeats | 0 pairs | Repeatability was not measured |
| Independent safety/revision concern on available safe/partial cells | 0 | AI observations, not clinical approval |
| Advance to candidate pilot | **No** | Incomplete panel and point-score ordering gate not satisfied |

For `TRIAGE-018`, both judges gave the authored strong response 100 and the partial response 65 in both languages. Gemini gave the unsafe response 25; Grok returned **25–48.33 with no point score**, while still detecting its configured error. The only saved `TRIAGE-020` cell was Gemini's English partial response at 65. Missing judgments are not zeros. The authored complete controls are not average-model outputs; their 100s do not measure a ceiling effect in candidate models.

Grok's uncertainty identifies a concrete anchor gap: update requirement 2 covers observation/routine follow-up and explicitly ignoring persistent symptoms, but does not classify replacing that plan with mandatory emergency care. Gemini chose a status; Grok abstained. An interval ordering can be described retrospectively, but it cannot replace S26's preregistered **point-score** gate after seeing the results. Do not label this a successful calibration or stable pass boundary.

## Five new patient-facing families

Cases and draft reference criteria are in [batch_l_cases.json](../data/multiturn/batch_l_cases.json). All **34 criterion positions** have an author source mapping in [batch_l_provenance.json](../data/multiturn/batch_l_provenance.json). A mapping test verifies structure, not medical correctness.

| Family | New decision challenge | Public answer basis |
|---|---|---|
| `REASON-019` | Improvement on iron versus resolving the cause of anemia | [AGA guidance education](https://agau.gastro.org/Course/AGA_Clinical_Guidelines_on_Gastrointestinal_Evaluation_of_Iron_Deficiency_Anemia_-_Accompanying_Educational_Presentation/d351c1ce-dc6f-4523-9606-868e04ad4359) |
| `REASON-020` | Crystals and apparently reassuring tests versus new fever and loss of function | [SANJO guideline](https://jbji.copernicus.org/articles/8/29/2023/index.html) |
| `REASON-021` | Discordant C. difficile assays, a medication confounder and later symptom resolution | [CDC testing](https://www.cdc.gov/c-diff/hcp/diagnosis-testing/), [CDC clinical guidance](https://www.cdc.gov/c-diff/hcp/clinical-guidance/), [IDSA/SHEA](https://www.idsociety.org/practice-guideline/clostridium-difficile/) |
| `MEDSAFE-016` | Past HBV infection versus vaccine-only immunity before a high-risk cancer regimen | [ASCO provisional clinical opinion](https://pmc.ncbi.nlm.nih.gov/articles/PMC11828660/) |
| `MEDSAFE-017` | Revising low initial HIT suspicion after a later platelet fall and thrombosis | [ASH guideline](https://pmc.ncbi.nlm.nih.gov/articles/PMC6258919/) |

Purchased Step 2 material supplies themes, not copied questions or answer keys. The ledger names exact PDF pages, limits and rejected older assumptions. In particular, the joint case does not import negative-Gram reassurance, and the HBV item is only broadly inspired by an exam serology/vaccination question—the anti-CD20 scenario is guidance-derived. Chinese dialogue was written for natural patient usage and checked against the paired facts; the existing schema's unreviewed-language flag is retained. No clinical or bilingual approval is claimed.

These cases add conditional reasoning and conflicting information, but how difficult they are remains an empirical question. They are configured for development only and have not been sent to a candidate or judge. Public exam-derived mechanisms can be memorized; neither changing names nor adding a second turn makes them hidden Gold. Exact failure/partial-credit anchors and controlled answer examples are still needed before a new scored panel.

## Xi'an: useful facts, not a cleared timeline

The new [local excerpt utility](../benchmark/local_lab_excerpt.py) uses on-device OCR and original image pixels. It masks everything except narrowly allowlisted lab labels and short aligned numeric/unit cells. It is a private review aid, **not a full de-identification guarantee**; OCR errors, missed units and column alignment still need checking.

This optional local utility requires macOS Vision/PyObjC, Pillow and Poppler's `pdftoppm`; none is required by the core benchmark tests. With the existing private OCR inventory, use `python3 -m benchmark.local_lab_excerpt --hash-prefix SOURCE_HASH_PREFIX --page 1 --output work/FRESH_PRIVATE_DIRECTORY`. It refuses reused output directories and changed source bytes, and writes private-permission outputs. A clean clone does not contain the patient inventory or records and cannot reproduce this private extraction.

Three selected pages were processed. Two yielded five candidate rows whose numeric values and reference intervals were visually checked. **Two potassium rows also had verified units; three other rows still lack verified units.** The third page yielded no allowlisted row and stays held—not normal or cleared. Local facts and unresolved issues are recorded in permission-restricted `work/xi_an_lab_review_facts_v1.json`; raw records, images, exact lab values and OCR are excluded from Git.

No collection-time ordering or same-episode linkage has been verified. The candidate timeline therefore contains **unordered source facts only**, no events or drafted clinical questions. It would be wrong to infer improvement, deterioration, diagnosis or treatment response from these pages. None of the 90 pages has received full-record privacy clearance and no Xi'an-derived case is counted in the portfolio.

## Next execution order

1. **Scoring:** draft a new, non-enforced anchor version for the observed gap. Include omitted follow-up, explicit dismissal, routine care, mandatory emergency care and uncertain wording as separate blinded fixtures. Check EN/ZH consistency and potential duplicate penalties. Preserve S26 v1 and all historical results. Decide the point-versus-interval gate *before* a fresh bounded live study; do not silently resume or pool this stopped run.
2. **Xi'an:** locally verify identity/encounter linkage and collection-versus-report times, then missing units and decision-time symptoms/treatments. Only then form relative-day events and a source-supported question. Keep unresolved material local; later professional review remains deferred, not waived.
3. **Case expansion:** write explicit partial-credit boundaries and response contrasts for batch L, prioritizing conditional treatment and uncertainty. Test those controls before judging actual candidate answers or using a batch average.
4. **Candidate trial:** wait for a complete, interpretable repeated-judge control experiment, then specify a small candidate panel separately. Do not widen directly to all providers or all 122 families.

The standing desired distribution remains lower-tier **~60–70**, average **~80**, premium **~90**. It is a diagnostic ambition, not a rescaling rule, target label or justification for changing penalties after seeing scores. Later clinical, bilingual and methods decisions are tracked as H96–H102 in the review handoff. Development can continue while partner review is deferred, but the benchmark is not ready for comparative clinical claims.
