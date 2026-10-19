# S5 prospective-case and score-target checkpoint — 2026-10-18

## Decision

The requested mature-benchmark pattern is **mid-tier around 80**, lower-tier roughly **60–70**, premium roughly **90**. It is recorded in the [charter](BENCHMARK_CHARTER_EN.md) and [calibration plan](SCORING_CALIBRATION_PLAN_2026-10-16_EN.md) as a diagnostic objective, not a promise or enforced score distribution. Define tiers independently; do not change correct labels or scores to reach those numbers. The existing four-family public bilingual panel is too small, too exposed, and too ceiling-heavy to estimate these bands. Its many 97–100 scores and the 3-/5-point effect of one requirements downgrade justify a difficulty and judge-validity investigation, **not** immediate weight tuning.

## What was created

| Partition | New family | Location | Status |
|---|---:|---|---|
| Default public development | 0 | Configured development paths unchanged | 104 existing public draft families |
| Prospective calibration candidate | 1 bilingual two-turn family | [`data/calibration/multiturn_candidates_v1.json`](../data/calibration/multiturn_candidates_v1.json) | Source-linked author draft; excluded from default runner; no human approval or score |
| Prospective hidden candidate | 1 bilingual two-turn family | Local Git-ignored `work/hidden_candidates/`; **not** in the repository | Local author draft only; no API exposure, no clinical approval, no Gold status |

The calibration family was newly authored after the split decision. It asks a candidate to update its assessment when mild symptoms after valproate are followed by confusion, gait change and vomiting despite reassuring-seeming test reports. It is a **synthetic adaptation**, not a copied patient record. A [published open-access case report](https://www.cureus.com/articles/179527-valproate-induced-hyperammonemic-encephalopathy-causing-new-onset-seizures) supplied a real-world failure mechanism; the case's CC BY 4.0 license was checked in the publisher PDF. [Current DailyMed prescribing information](https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=64b509bc-f398-48ad-bdcb-9904e61d9225&type=display) supports considering hyperammonemic encephalopathy with mental-status change even when liver tests are normal; [MedlinePlus](https://medlineplus.gov/druginfo/meds/a682412.html) supports avoiding an unsupervised abrupt stop. These sources **do not** independently approve the prompt's exact urgency, all alternatives, severity grading, or Chinese translation. The exact adaptation record is in [`provenance_v1.json`](../data/calibration/provenance_v1.json).

The local hidden draft uses a *different* article/guideline mechanism and rewritten synthetic facts. Its prompt, private labels, source URLs and family ID are intentionally absent from Git and from this public note. The tracked split plan records only a count and integrity fingerprint. A public source article may already be in a model's training data; therefore this draft is **not** leakage-proof, sealed, independently reviewed, or legitimately called hidden Gold. It must be moved to an access-controlled private store with a reviewer/author access log, then revised and sealed before any final holdout use. If the local `work/` directory is lost, this draft is not recoverable from Git.

## Isolation and quality checks

- `python3 -m benchmark.portfolio_audit` confirms 104 unchanged public families, **0 approved calibration and 0 hidden Gold**, plus one separate calibration draft. On this machine it also validates the local hidden draft's count and fingerprint; on a fresh clone that check is unavailable rather than falsely passing.
- The audit rejects overlapping family IDs, exact shared public source URLs for the calibration draft, exact calibration/hidden source URLs, draft-count drift, and changed draft content hashes. This is a bounded leakage check; overlapping clinical mechanisms or memorized publications still need human review.
- Both new bilingual datasets pass the existing two-turn structural validator. Their Chinese variants are explicitly `machine_translation_unreviewed`. Neither is added to the default model-matrix case paths, and the hidden draft has not been sent to any provider.
- No old prompt, anchor, rubric weight, score or safety cap was changed. We did not run or score either new case. A no-score draft cannot demonstrate that average models will score 80.

## Next gate before a wider model panel

1. Independent clinician checks each new scenario, source-to-criterion link, urgency boundary, acceptable alternatives and severity; bilingual reviewer checks both variants. Revise with version increments and record adjudication. The professional clinical review may remain a release gate, but until it is done these are development probes, not clinical Gold.
2. Freeze a larger balanced calibration tranche and pre-declare reference-model tier membership independently of ClinReason scores. Separate tracks and languages; sample low-acuity controls, ambiguous updates, high-stakes failures, and source mechanisms. Do not promote a public development case to hidden.
3. Once source/label review is adequate, compare both judges with independently adjudicated answer anchors, including natural model omissions and unsafe near-misses. Quantify ceilings, false passes, inter-judge gaps, language gaps and uncertainty. Only then test a versioned *construct-validity* change to a case, anchor or scoring rule; rerun all comparators on the same revision and untouched holdout.
4. Choose an access-controlled private home and retention/backup policy for hidden material before scaling that partition. The one local draft is a prototype, not a substitute for that decision.

Current major batch decision: whether to fund/arrange the qualified clinical and bilingual review and private hidden-set governance before promoting any prospective draft. Meanwhile, public development cases can continue expanding with source-linked synthetic adaptations and engineering audits, clearly marked unvalidated.
