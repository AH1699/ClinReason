# SectorBench Healthcare/Clinics v0.1

A bilingual, local-first planning package and runnable scaffold for evaluating LLMs in high-stakes sector workflows. Healthcare/clinics is the first domain module; the core data model and scoring engine are designed to extend to finance and legal.

This package is **research/evaluation infrastructure, not medical advice**. All included cases are synthetic and unvalidated: examples are marked `example_unvalidated`, while the bilingual Alpha cases are marked `draft`. They must not be presented as a validated benchmark or used for clinical decisions until qualified clinicians complete the validation and Gold Set process.

## 中文简介

这是一个双语、本地优先的行业大模型评测规划包与可运行脚手架。首个领域是医疗/诊所，但核心数据结构与评分引擎可扩展到金融与法律。

本项目是**研究与评测基础设施，不构成医疗建议**。所有案例均为合成且未经验证：示例案例状态为 `example_unvalidated`，双语 Alpha 案例状态为 `draft`。在合格临床专家完成验证与 Gold Set 流程前，不得将其宣传为已验证基准，也不得用于临床决策。

## Included / 内容

- `docs/DESIGN_EN.md` and `docs/DESIGN_ZH.md`: strategy, governance, architecture, MVP phases, cost controls, and path from frontier judges to hybrid/distilled evaluators.
- `docs/TAXONOMY_RUBRIC_EN.md` and `docs/TAXONOMY_RUBRIC_ZH.md`: taxonomy, anchors, critical-error gating, disagreement, confidence, absolute and pairwise scoring.
- `docs/DATA_CONTRACTS_EN.md` and `docs/DATA_CONTRACTS_ZH.md`: entity contracts and versioning rules.
- `docs/BENCHMARK_CHARTER_EN.md` and `docs/BENCHMARK_CHARTER_ZH.md`: intended use, exclusions, governance, decision rights, and release gates.
- `docs/RISK_REGISTER_EN.md` and `docs/RISK_REGISTER_ZH.md`: active healthcare benchmark risk register and immediate controls.
- `docs/CASE_AUTHORING_GUIDE_EN.md` and `docs/CASE_AUTHORING_GUIDE_ZH.md`: bilingual family design, source policy, review workflow, and completion checklist.
- `docs/PURCHASED_ASSET_INTAKE_2026-10-22_EN.md` and `docs/PURCHASED_ASSET_INTAKE_2026-10-22_ZH.md`: simple raw-data handoff for the acquisition team and ClinReason's privacy-to-question/answer processing workflow; the team does not prepare labels.
- `docs/GLOBAL_CORE_DESIGN_EN.md` and `docs/GLOBAL_CORE_DESIGN_ZH.md`: separation of jurisdiction-neutral behavior, local jurisdiction packs, and cross-jurisdiction adaptation.
- `docs/REVIEW_WORKFLOW_EN.md` and `docs/REVIEW_WORKFLOW_ZH.md`: append-only clinical/language review operations, evidence rules, and promotion gates.
- `docs/PRELIMINARY_CLINICAL_REVIEW_EN.md` and `docs/PRELIMINARY_CLINICAL_REVIEW_ZH.md`: public-evidence first pass across all 12 Alpha families; explicitly not clinical validation.
- `docs/CLINICAL_REVIEW_HANDOFF_EN.md` and `docs/CLINICAL_REVIEW_HANDOFF_ZH.md`: living prioritized questions for later qualified reviewers.
- `docs/CANDIDATE_PILOT_EN.md` and `docs/CANDIDATE_PILOT_ZH.md`: prompt-only export, optional local Gemini runner, external-answer import, and mock-scored experimental reports.
- `docs/GROK_GEMINI_PILOT_EN.md` and `docs/GROK_GEMINI_PILOT_ZH.md`: opt-in Grok candidate → Gemini provisional judge workflow, local model/key settings, and end-to-end test commands.
- `docs/LIVE_PILOT_2026-10-08_EN.md` and `docs/LIVE_PILOT_2026-10-08_ZH.md`: first live 24-case integration run, ceiling-effect warning, and corrected single-judge review gate.
- `docs/COVERAGE_ROADMAP_EN.md` and `docs/COVERAGE_ROADMAP_ZH.md`: gaps in complex and clinician-facing evaluation, with staged expansion controls.
- `docs/BATCH_E_100_FAMILIES_2026-10-14_EN.md` and `docs/BATCH_E_100_FAMILIES_2026-10-14_ZH.md`: 100-family milestone, new cases, provenance, verification, and remaining gates.
- `docs/PORTFOLIO_AUDIT_BATCH_F_2026-10-15_EN.md` and `docs/PORTFOLIO_AUDIT_BATCH_F_2026-10-15_ZH.md`: 104-family update, mechanism/source-label audit, four public-case adaptations, and prospective split plan.
- `docs/S6_DEVELOPMENT_GAPS_BATCH_F_2026-10-19_EN.md` and `docs/S6_DEVELOPMENT_GAPS_BATCH_F_2026-10-19_ZH.md`: historical 108-family development checkpoint, four harder patient drafts, coverage audit and offline saved-panel diagnostic.
- `docs/S6_BATCH_F_LIVE_PILOT_2026-10-19_EN.md` and `docs/S6_BATCH_F_LIVE_PILOT_2026-10-19_ZH.md`: frozen batch-F model pilot, exact-case provisional anchors, two complete candidate panels and one partial panel; scores are development-only.
- `docs/S7_DEESCALATION_AND_ANSWER_AUDIT_2026-10-20_EN.md` and `docs/S7_DEESCALATION_AND_ANSWER_AUDIT_2026-10-20_ZH.md`: preceding 112-family checkpoint, four low-acuity/de-escalation controls, answer-level judge-gap analysis and an offline response-language flag.
- `docs/S8_BATCH_G_PROTOCOL_2026-10-20_EN.md` and `docs/S8_BATCH_G_PROTOCOL_2026-10-20_ZH.md`: batch-G exact-case anchors and controlled bilingual contrasts, opt-in language protocol, and offline checks.
- `docs/S9_BATCH_G_PAIRED_CONTRAST_2026-10-20_EN.md` and `docs/S9_BATCH_G_PAIRED_CONTRAST_2026-10-20_ZH.md`: preceding 12-call English/Chinese two-judge controlled-answer result and the next near-miss gate.
- `docs/S10_GLOVE_NEAR_MISS_PREREG_2026-10-20_EN.md` and `docs/S10_GLOVE_NEAR_MISS_PREREG_2026-10-20_ZH.md`: fixed before-results glove-rash near-miss protocol and exact EN/ZH probes.
- `docs/S11_GLOVE_NEAR_MISS_RESULT_2026-10-20_EN.md` and `docs/S11_GLOVE_NEAR_MISS_RESULT_2026-10-20_ZH.md`: paired near-miss result and cross-language score-coherence gap.
- `docs/S12_SCORING_COHERENCE_DIAGNOSTIC_2026-10-20_EN.md` and `docs/S12_SCORING_COHERENCE_DIAGNOSTIC_2026-10-20_ZH.md`: current versioned offline scoring-coherence flags on saved S9/S11/F judgments and the next controlled-probe gate.
- `docs/S13_SCORING_SEPARATION_PREREG_2026-10-20_EN.md` and `docs/S13_SCORING_SEPARATION_PREREG_2026-10-20_ZH.md`: frozen pre-run eight-answer EN/ZH scoring-separation packet and planned judge-only readout.
- `docs/S14_SCORING_PROBE_RESULT_2026-10-21_EN.md` and `docs/S14_SCORING_PROBE_RESULT_2026-10-21_ZH.md`: completed 16-call judge-only result, independent saved-score audit and unresolved safety/revision scoring gap. The S13 preregistration remains the pre-run record.
- `docs/S15_SCORING_DIMENSION_HYPOTHESIS_2026-10-21_EN.md` and `docs/S15_SCORING_DIMENSION_HYPOTHESIS_2026-10-21_ZH.md`: non-enforced scoring-dimension hypotheses, offline S9/S11/S14 comparisons and a frozen cross-mechanism `REASON-015` probe; no score changes or new model calls.
- `docs/S16_REASON015_JUDGE_RESULT_2026-10-21_EN.md` and `docs/S16_REASON015_JUDGE_RESULT_2026-10-21_ZH.md`: subsequent capped eight-call cross-mechanism judge-only result, independently audited scores and unresolved EN/ZH/dimension differences; historical S15 remains the pre-run record.
- `docs/PUBMED_CASE_SOURCE_POLICY_2026-10-21_EN.md` and `docs/PUBMED_CASE_SOURCE_POLICY_2026-10-21_ZH.md`: PubMed/PMC case-report discovery, article-level license/privacy/provenance checks and limits on deriving reference answers.
- `docs/S16_PUBMED_INTAKE_2026-10-21_EN.md` and `docs/S16_PUBMED_INTAKE_2026-10-21_ZH.md`: citation-only intake of three candidate CC BY case reports and one rights exclusion; no new case or label.
- `docs/S17_SCORING_EVIDENCE_AND_CLEAN_PROBE_2026-10-21_EN.md` and `docs/S17_SCORING_EVIDENCE_AND_CLEAN_PROBE_2026-10-21_ZH.md`: non-enforced dimension-evidence flags and the pre-run, punctuation-clean `REASON-015` protocol.
- `docs/S17_CLEAN_PROBE_RESULT_2026-10-21_EN.md` and `docs/S17_CLEAN_PROBE_RESULT_2026-10-21_ZH.md`: eight-call clean-probe result; identical English answers also shifted, so score changes cannot be attributed to punctuation.
- `docs/S17_PUBMED_SOURCE_TO_ANSWER_2026-10-21_EN.md` and `docs/S17_PUBMED_SOURCE_TO_ANSWER_2026-10-21_ZH.md`: independent public-guidance mapping for six broad candidate behaviors and a citation-only privacy boundary; no exact answer key or derived cases.
- `docs/S18_JUDGE_REPEATABILITY_PREREG_2026-10-21_EN.md` and `docs/S18_JUDGE_REPEATABILITY_PREREG_2026-10-21_ZH.md`: committed, eight-call exact-packet repeatability protocol with provider-default sampling and no candidate calls.
- `docs/S18_JUDGE_REPEATABILITY_RESULT_2026-10-21_EN.md` and `docs/S18_JUDGE_REPEATABILITY_RESULT_2026-10-21_ZH.md`: audited S17→S18 same-packet comparison; two of four omitted-safety-net scores changed, while all baseline scores stayed at 100.
- `docs/S19_ANCHOR_AND_MULTIFAMILY_PLAN_2026-10-21_EN.md` and `docs/S19_ANCHOR_AND_MULTIFAMILY_PLAN_2026-10-21_ZH.md`: pre-run, non-enforced `REASON-015` boundary and call-capped multi-family repeatability plan.
- `docs/S19_MULTIFAMILY_REPEATABILITY_RESULT_2026-10-21_EN.md` and `docs/S19_MULTIFAMILY_REPEATABILITY_RESULT_2026-10-21_ZH.md`: completed 24-call, two-family judge-only repeat; 15/24 exact scores and two provisional pass flips despite stable criterion statuses.
- `docs/S19_PUBMED_CASE_BATCH_2026-10-21_EN.md` and `docs/S19_PUBMED_CASE_BATCH_2026-10-21_ZH.md`: two original PubMed-informed public-development cases, independent source-to-requirement map, privacy limits and review queue.
- `docs/S20_EVIDENCE_HOLD_AND_PUBMED_BATCH_2026-10-22_EN.md` and `docs/S20_EVIDENCE_HOLD_AND_PUBMED_BATCH_2026-10-22_ZH.md`: offline identical-packet score-boundary holds and one PubMed-informed steroid-safety draft with separate guideline-mapped answer requirements.
- `docs/S21_EVIDENCE_EXPLICIT_JUDGE_PROTOCOL_2026-10-22_EN.md` and `docs/S21_EVIDENCE_EXPLICIT_JUDGE_PROTOCOL_2026-10-22_ZH.md`: a separate v3 judge instruction and capped two-mechanism exact-packet test; first live attempt aborted with unknown delivery and no verified judgments, so no scoring-contract or clinical claim.
- `docs/S22_REPLACEMENT_JUDGE_PANEL_2026-10-22_EN.md` and `docs/S22_REPLACEMENT_JUDGE_PANEL_2026-10-22_ZH.md`: separately authorized prospective replacement protocol using the same frozen packets and keyless host preflight.
- `docs/S22_ABORTED_PANEL_RESULT_2026-10-22_EN.md` and `docs/S22_ABORTED_PANEL_RESULT_2026-10-22_ZH.md`: the new panel stopped after 23/24 saved first-pass judgments on an ambiguous Grok timeout; offline saved-cell audit only, no repeat or clinical scoring claim.
- `docs/S23_OFFLINE_SCORING_BOUNDARIES_2026-10-22_EN.md` and `docs/S23_OFFLINE_SCORING_BOUNDARIES_2026-10-22_ZH.md`: exact-answer scoring-boundary review and one-point sensitivity on verified S20/S22 saved results; non-enforced and no new model calls.
- [S35 quotation and candidate-boundary draft](docs/S35_CANDIDATE_BOUNDARIES_2026-10-23_EN.md) / [中文](docs/S35_CANDIDATE_BOUNDARIES_2026-10-23_ZH.md): 46 bilingual focused packets, three separate draft anchor edits, 54 existing-validator quote checks and a hash-bound harder-family shortlist. Red-eye care OR/AND follow-up remains held, with 14 unlabelled probes. 420 tests pass; zero calls, new scores or cases. Proposed 72-call controls and a separate 36-call MiniMax extension are estimates, not frozen or authorized protocols.
- [S33 controls and S34 MiniMax results](docs/S33_S34_RESULTS_2026-10-23_EN.md) / [中文](docs/S33_S34_RESULTS_2026-10-23_ZH.md): S33 completed 48/48 valid judgments and passed all narrow ordering/boundary/repeat gates. MiniMax M2.7 completed 8/8 answer calls; S34 stopped at request 21 on a Gemini stitched quote, retaining six conversation/judge records and no Chinese sinus score. 69 total requests, no retries; 395 tests passed at that checkpoint. Candidate disagreements and one uncertainty interval remain, so no ranking or completed calibration. The [S33 protocol](docs/S33_STAGE_ISOLATED_PROTOCOL_2026-10-23_EN.md) and [S34 protocol](docs/S34_MINIMAX_PROTOCOL_2026-10-23_EN.md) retain the pre-run rules.
- [S32 care boundaries and quotation draft](docs/S32_CARE_BOUNDARIES_DRAFT_2026-10-23_EN.md) / [中文](docs/S32_CARE_BOUNDARIES_DRAFT_2026-10-23_ZH.md): two separate draft anchor edits, 32 focused bilingual packets (28 author hypotheses, four exploratory), future-turn isolation for initial judgments and a single-span observation prompt clarification. 356 tests pass; no API calls, scores, new cases or default changes. Historical controls/results stay unchanged; the subsequent S33 protocol is linked above and clinical/bilingual review remains pending.
- [S31 result and next boundaries](docs/S31_FULL_SCORE_RESULT_2026-10-23_EN.md) / [中文](docs/S31_FULL_SCORE_RESULT_2026-10-23_ZH.md): 20 valid judgments from 21 requests; a joined cross-turn quotation stopped validation, with no repeats or retries. Six available groups ordered correctly, but Chinese sinus care-plan boundaries differ; the overall gate stays false. Read-only diagnostic added; 335 tests pass. Public development 125/250, calibration/Gold 0/0.
- [S31 pre-run protocol](docs/S31_FULL_SCORE_PROTOCOL_2026-10-23_EN.md) / [中文](docs/S31_FULL_SCORE_PROTOCOL_2026-10-23_ZH.md): preserved 32-call integration/repeat design using S30 boundaries and unchanged S28 score arithmetic. The stopped run is linked above; its unused call allowance is not permission to resume.
- [S30 completed boundary result](docs/S30_BOUNDARY_RESULT_2026-10-23_EN.md) / [中文](docs/S30_BOUNDARY_RESULT_2026-10-23_ZH.md): 24/24 valid calls, 32/32 predeclared criterion matches and 8/8 repeated matches. The focused gate passed; the subsequent S31 protocol is linked above. This result is not completed calibration or automatic call approval. Its checkpoint passed 312 tests.
- [S30 pre-run protocol and N controls](docs/S30_BOUNDARY_PROTOCOL_AND_N_CONTROLS_2026-10-23_EN.md) / [中文](docs/S30_BOUNDARY_PROTOCOL_AND_N_CONTROLS_2026-10-23_ZH.md): preserved prospective 24-call protocol; completed result linked above. Batch N has seven anchors, two shared initial answers and six bilingual update controls, still unscored.
- [S29 result, S30 draft and batch N](docs/S29_RESULT_S30_BOUNDARIES_STEP2_2026-10-23_EN.md) / [中文](docs/S29_RESULT_S30_BOUNDARIES_STEP2_2026-10-23_ZH.md): approved diagnostic completed 2/2 calls; Grok 133.301s / Gemini 19.914s. Gemini scored the authored partial 65; Grok abstained on unclear boundaries. The subsequent S30 freeze is linked above. New batch N added one bilingual salicylate family with seven mapped requirements; this earlier checkpoint passed 294 tests.
- [S29 readiness and Xi'an progress](docs/S29_SCORING_STEP2_XIAN_2026-10-23_EN.md) / [中文](docs/S29_SCORING_STEP2_XIAN_2026-10-23_ZH.md): historical pre-approval checkpoint (superseded by the completed result above); batch M now has 13 draft anchors and 12 bilingual update controls. Owner confirms all 50 Xi'an files belong to one encounter; a private four-event time scaffold is not yet case-ready. 284 tests pass.
- [S28 full-score result and expansion](docs/S28_RESULT_AND_CASE_EXPANSION_2026-10-23_EN.md) / [中文](docs/S28_RESULT_AND_CASE_EXPANSION_2026-10-23_ZH.md): preceding full-score panel stopped after 13 valid judgments; four complete red-eye groups ordered 100 > 65 > 25, but no repeat stage and no calibration completion. Two new bilingual families; the then-pending Xi'an grouping request is resolved in S29 by owner confirmation.
- [S27 boundary result and answer packets](docs/S27_RESULT_AND_ANSWER_PACKETS_2026-10-23_EN.md) / [中文](docs/S27_RESULT_AND_ANSWER_PACKETS_2026-10-23_ZH.md): preceding focused experiment completed 32 valid judge calls, 20/20 predeclared classifications and 8/8 repeated statuses; total-score calibration remains untested. Batch L now has 34 draft anchors and 30 bilingual update-answer controls. Five Xi'an lab rows have verified units, but chronology/linkage remain unresolved; private records stay local.
- [S26 result and case batch](docs/S26_RESULT_AND_CASE_BATCH_2026-10-23_EN.md) / [中文](docs/S26_RESULT_AND_CASE_BATCH_2026-10-23_ZH.md): preceding frozen scoring run stopped at 13 valid judgments after a transport failure; no repeats or candidate calls, advance gate false. Five new bilingual draft families and local-only Xi'an partial lab verification; no clinical/privacy clearance.
- `docs/PROJECT_EXECUTION_PLAN_2026-10-16_EN.md` and `docs/PROJECT_EXECUTION_PLAN_2026-10-16_ZH.md`: current checkpoint, scoring issue SC-01, ordered work, acceptance gates, and tracking convention; start here for the next task.
- `docs/CRITERION_SCORING_PILOT_2026-10-18_EN.md` and `docs/CRITERION_SCORING_PILOT_2026-10-18_ZH.md`: exact-revision provisional scoring anchors, criterion-evidence judge contract, judge-only recovery, and the pre-registered bilingual panel.
- `docs/MULTITURN_BATCH_C_2026-10-11_EN.md` and `docs/MULTITURN_BATCH_C_2026-10-11_ZH.md`: source-linked 12-family two-turn expansion, partial-answer diagnostics, and pending review questions.
- `docs/PATIENT_DIFFICULTY_AUDIT_2026-10-12_EN.md` and `docs/PATIENT_DIFFICULTY_AUDIT_2026-10-12_ZH.md`: bounded paired-language difficulty pilot, exact local commands, descriptive metrics, and interpretation limits.
- `docs/PROFESSIONAL_PILOT_2026-10-12_EN.md` and `docs/PROFESSIONAL_PILOT_2026-10-12_ZH.md`: the historical clinician-facing pilot, prompt-only export, evidence links, and unresolved review questions; scoring is disabled.
- `docs/CANDIDATE_COMPARISON_2026-10-12_EN.md` and `docs/CANDIDATE_COMPARISON_2026-10-12_ZH.md`: completed fixed bilingual second-candidate diagnostic, transport-attempt history, case-level findings, and comparison limits.
- `docs/BILINGUAL_JUDGE_PROBES_2026-10-14_EN.md` and `docs/BILINGUAL_JUDGE_PROBES_2026-10-14_ZH.md`: matched blinded English/Chinese near-miss probes, completed Gemini/Grok comparison after an initial transport failure, and unresolved calibration questions.
- `agents/preliminary_clinical_reviewer.md`, `data/evidence/public_sources.json`, and `benchmark/preliminary_reviewer.py`: a bounded, source-linked AI audit workflow that cannot clear human review gates.
- `schemas/`: JSON Schema definitions for cases, responses, judge outputs, human reviews, version manifests, aggregate scores, pairwise outputs, and runs.
- `benchmark/`: standard-library Python implementation with SQLite persistence and candidate/judge provider interfaces.
- `data/examples/`: six synthetic, unvalidated healthcare/clinic examples.
- `data/templates/`: case-authoring and independent case-review templates.
- `tests/`: scoring and end-to-end tests.

## Quick start

Requires Python 3.11+; the demo has no third-party dependencies and makes no network calls.

```bash
python3 -m benchmark.cli --config config/benchmark.json init
python3 -m benchmark.cli --config config/benchmark.json validate-data
python3 -m benchmark.cli --config config/benchmark.json dataset-status
python3 -m benchmark.cli --config config/benchmark.json validate-reviews
python3 -m benchmark.cli --config config/benchmark.json review-status
python3 -m benchmark.cli --config config/benchmark.json export-review-packets
python3 -m benchmark.cli --config config/benchmark.json run-demo
python3 -m unittest discover -s tests -v
```

For an external LLM, use the [English pilot guide](docs/CANDIDATE_PILOT_EN.md) or [中文试运行指南](docs/CANDIDATE_PILOT_ZH.md). The optional `generate-gemini` command defaults to a no-network dry run and needs `--live` for real calls; it reads a locally ignored `.env.local` or `GEMINI_API_KEY`. Exported rows contain only candidate-visible inputs; imported answers must match each exact case version and hash. `score-imported-demo` uses mock judges and its `experimental_unvalidated` report is **not** a clinical evaluation or ranking.

For the two-provider test, follow [Grok → Gemini (English)](docs/GROK_GEMINI_PILOT_EN.md) or [Grok → Gemini（中文）](docs/GROK_GEMINI_PILOT_ZH.md). `.env.local` holds `GROK_API_KEY`, `GROK_MODEL`, `GEMINI_API_KEY`, and `GEMINI_JUDGE_MODEL`; actual key values remain local and ignored by Git. The Grok generator and Gemini judge each require `--live` for network calls. A single Gemini judge on draft cases is useful for integration testing only.

For a bounded seven-candidate, two-judge **development** comparison, see the [model-matrix guide](docs/MODEL_MATRIX_PILOT_2026-10-15_EN.md) or [中文说明](docs/MODEL_MATRIX_PILOT_2026-10-15_ZH.md). It supports two Gemini, two Grok, and three MiniMax model IDs; Gemini and Grok judge each answer separately. `python3 -m benchmark.cli model-matrix` is a no-network preview. The matrix model IDs live in `config/model_matrix.json`; `GROK_MODEL` and `GEMINI_JUDGE_MODEL` in ignored `.env.local` are defaults for older single-model commands, not a limit on the matrix. See the [scoring calibration plan](docs/SCORING_CALIBRATION_PLAN_2026-10-16_EN.md) or [中文计划](docs/SCORING_CALIBRATION_PLAN_2026-10-16_ZH.md) before interpreting model scores.

The optional `--anchors config/multiturn_criterion_anchors_v1.json` activates exact-case requirement evidence in a versioned judge contract. `judge-saved-matrix-answer` can judge one saved answer with two calls and no candidate replay (use `--case-id` for a partial multi-case run); `assemble-model-matrix` verifies and combines completed partial artifacts without API calls; `audit-model-matrix` shows exact per-requirement disagreement, language splits, and ceiling counts. See the [criterion-scoring pilot](docs/CRITERION_SCORING_PILOT_2026-10-18_EN.md) or [中文说明](docs/CRITERION_SCORING_PILOT_2026-10-18_ZH.md). All resulting scores remain provisional.

The first live Grok → Gemini integration run completed 24/24 cases on 2026-10-08; see the [English findings](docs/LIVE_PILOT_2026-10-08_EN.md) or [中文结果](docs/LIVE_PILOT_2026-10-08_ZH.md). Its very high AI-judge scores are **not** clinical performance evidence. All 24 cases require human review because only one uncalibrated judge was used.

To inspect the evidence-limited AI reviewer prompt for one bilingual family, run `python3 -m benchmark.preliminary_reviewer HC-GC-TRIAGE-001`. With a **compatible, locally authenticated** Codex CLI, add `--run` to invoke the agent in a read-only sandbox. Validated output is written under `work/preliminary_reviews/`, never `data/reviews/`; it is not a clinical or language approval. The installed `codex-cli 0.23.0` currently cannot run the configured ChatGPT model (server requests a newer CLI), so this live path remains unverified until the CLI is updated. The initial first pass is recorded in the bilingual preliminary-review documents.

The generated SQLite file is `work/benchmark.sqlite3` and is intentionally excluded from the package. To install the CLI locally:

```bash
python3 -m pip install -e .
sectorbench --config config/benchmark.json run-demo
```

## What the demo proves—and does not prove

The mock candidate and judges only verify plumbing: ingestion, persistence, structured outputs, aggregation, gating, reporting, and tests. Their scores have **no clinical meaning**. Replace them with real provider adapters only after the evaluation protocol, data handling, and clinician oversight are approved.

The validation command has two modes. Development mode permits draft/example cases and reports provenance and bilingual-pair warnings. `validate-data --release-ready` also checks validated status, sources, jurisdiction, effective date, complete English/Chinese families, and matching clinical/language approvals in the review records. Passing automated checks does not establish clinical correctness; reviewer qualifications and governance decisions still require human verification.

Case reviews are append-only and content-bound. `review-template` generates a record containing the exact case ID, version, and canonical SHA-256 content hash. `validate-reviews` rejects stale, malformed, self-authored, or role-inappropriate reviews; `review-status` reports which clinical and language gates are actually complete. A file's existence never counts as approval.

`export-review-packets` writes one Markdown packet per bilingual family and an assignment manifest to `work/reviewer_packets/`. The packets contain the draft prompts, reference behavior, critical errors, sources, and review hashes. The command refuses to overwrite an existing packet directory. Reviewer IDs and real qualification checks remain to be supplied by the project team.

## Current project status

- **Complete:** bilingual design package, draft charter, risk register, authoring guide, machine-readable contracts, offline pipeline, scoring/gating, data validation, append-only review workflow, reviewer packet export, prompt-only candidate export, local Gemini candidate adapter, exact-revision answer import, experimental category/language reports, and mock tests.
- **Development examples:** six English-only synthetic infrastructure fixtures remain under `data/examples/`.
- **Alpha draft:** the bilingual, jurisdiction-neutral Global Core under `data/alpha/` has **32 matched families / 64 prompts**. The new routine and self-care triage controls fill two previously empty acuity cells; the other five categories still have five families each. [Family labels](data/alpha/family_labels.json), [coverage roadmap](docs/COVERAGE_ROADMAP_EN.md), and [public source inventory](data/evidence/public_sources.json) describe these development-only drafts. No family is clinically validated.
- **Non-clinical gap work:** the [progress log](docs/PROJECT_PROGRESS_2026-10-11_EN.md) tracks coverage, synthetic judge contrasts, paired family-level reporting, candidate provenance, and a same-answer judge-repeatability check. All 32 Alpha families are single-turn patient-facing; no hidden Gold or calibration split exists.
- **Separate multi-turn track:** the pilot and batches C–N total **51 bilingual draft families / 102 two-turn conversations**. [Batch H](docs/S19_PUBMED_CASE_BATCH_2026-10-21_EN.md) and [batch I](docs/S20_EVIDENCE_HOLD_AND_PUBMED_BATCH_2026-10-22_EN.md) add PubMed-informed original synthetic cases; [batch J](data/multiturn/batch_j_cases.json), [batch K](data/multiturn/batch_k_cases.json), [batch L](data/multiturn/batch_l_cases.json), [batch M](data/multiturn/batch_m_cases.json), and [batch N](data/multiturn/batch_n_cases.json) add purchased-Step-2-informed synthetic cases whose requirements are sourced to current public guidance. This track is not pooled with single-turn Alpha. Earlier contrast-pair transport failures remain unscored.
- **Difficulty audit:** the [paired-language patient-facing pilot](docs/PATIENT_DIFFICULTY_AUDIT_2026-10-12_EN.md) found 12/12 provisional 100s from one Grok candidate and Gemini judge. Rejudging the *same answers* with the same judge configuration changed 0/12 scores or flags; that narrows judge repeatability only, not clinical validity or model discrimination.
- **Separate professional draft:** the original pilot, batch E, and [batch F](docs/PORTFOLIO_AUDIT_BATCH_F_2026-10-15_EN.md) contain **42 clinician-facing families / 84 prompts**: 28 consults, seven medication handoffs and seven evidence appraisals. Twenty-six families are rewritten adaptations of distinct published CC BY case reports with a [source/changes/limitations registry](data/evidence/clinical_case_adaptations.json). The professional rubric is authoring-only; there is no professional score or judge.
- **Overall authoring count:** **125 bilingual families** across the three separate tracks, or 250 language variants. This is a development coverage count, not an aggregate benchmark score or proof of expert difficulty.
- **New standalone drafts:** [Batch O](docs/BATCH_O_STANDALONE_EN.md) / [中文](docs/BATCH_O_STANDALONE_ZH.md) adds two harder bilingual families on cardiorenal trade-offs and refeeding risk, with public-report provenance, 12 mapped requirements and reference-answer contrasts. These four variants are not yet in the registered 125/250 count or frozen pilot; three reserved new confirmation families also remain separate. Intended difficulty is not measured clinical validity.
- **Portfolio and gap audits:** `python3 -m benchmark.portfolio_audit` checks configured counts, declared provenance, selected mechanism-overlap pairs and the [prospective split plan](data/audit/prospective_split_plan.json); `python3 -m benchmark.development_gap_audit` reports patient-track coverage proxies. `python3 -m benchmark.pubmed_derived_case_audit` checks batches H/I source separation and per-requirement mapping, not clinical truth. [Batch J's ledger](data/multiturn/batch_j_provenance.json), [batch K's ledger](data/multiturn/batch_k_provenance.json), [batch L's ledger](data/multiturn/batch_l_provenance.json), [batch M's ledger](data/multiturn/batch_m_provenance.json), and [batch N's ledger](data/multiturn/batch_n_provenance.json) separate Step 2 inspiration from current public answer sources. All 125 public families remain development-only; no approved calibration or hidden Gold cases exist. The [review queue](data/audit/overlap_and_source_review.json) identifies possible duplication and high-priority source-to-label checks, not approved clinical labels.
- **Second candidate:** the [fixed 12-conversation bilingual Gemini 3.5 Flash-Lite check](docs/CANDIDATE_COMPARISON_2026-10-12_EN.md) completed on a fresh second attempt after the first transport failure. The same provisional Gemini 3.8 Flash judge assigned 10/12 perfect scores versus 12/12 for Grok; two nonzero deltas and a judge-consistency concern are documented. This is a development diagnostic, not clinical validation or a model ranking.
- **Judge consistency:** [matched blinded EN/ZH probes](docs/BILINGUAL_JUDGE_PROBES_2026-10-14_EN.md) were completed by Gemini and, after an explicitly authorized family-sized retry, Grok. Both ranked all four baseline/challenge pairs in the same direction; exact gaps matched in two medication pairs only. Triage deduction size and human-review flags differed. A checked local comparison command verifies case bindings and recomputes scores. These probes are not clinical calibration.
- **Batch-F development model pilot:** [the frozen pilot record](docs/S6_BATCH_F_LIVE_PILOT_2026-10-19_EN.md) reports 8/8 paired-language cases completed for Gemini 3.5 Flash-Lite and Grok 4.6, with Gemini/Grok judging separately; MiniMax M2.7 completed 6/8 before a rejected judge-evidence quote stopped the run. Both complete candidates received 100/100 on the stable *H. pylori* reasoning case in both languages, while the medication cases had substantial judge gaps. No model ranking, clinical calibration or score-band fit follows.
- **Batch-G development checkpoint:** [the S7 audit](docs/S7_DEESCALATION_AND_ANSWER_AUDIT_2026-10-20_EN.md) adds four unscored synthetic controls and documents all seven large same-answer judge gaps. A hash-bound offline scan found three unmistakable English-answer turns to Chinese cases among 46 saved turns; historical scores are unchanged and language equivalence remains unreviewed.
- **Current development checkpoint:** [S55 approved nine-family execution](docs/S55_MIXED_PANEL_RUN_EN.md) / [中文](docs/S55_MIXED_PANEL_RUN_ZH.md) is underway with the four Gemini/MiniMax candidates, Gemini judging, at most 452 new calls and a **$20 recorded-spending stop threshold with possible last-request overrun**. The amended configuration was frozen before dispatch. All 72 panel cells and 16 imports remain; eight medication cells are raw diagnostics only, without pooled means or rankings. No final outcome is claimed yet. S50's failed gate, historical scores and original labels are unchanged.
- **Next milestones:** inspect the terminal captures, control gate and separate repeated judgments using the new read-only report. No retry or restart is authorized. Continue distinct source-backed cases and a new authoring catalog toward **at least 500 families**. Registered coverage remains 125/250; standalone O/P total four families/eight variants. [English roadmap](docs/PROJECT_EXECUTION_PLAN_2026-10-16_EN.md) / [中文](docs/PROJECT_EXECUTION_PLAN_2026-10-16_ZH.md). Expert review stays later, Xi'an local and 60–70/~80/~90 remain unfitted aspirations. No further single-medication diagnostic is scheduled.
- **Deferred:** production-grade candidate connectors, judge calibration against human ratings, hidden Gold Set, external rankings, training, and deployment.

Latest verification: the existing full offline suite passed **962 tests**, and **11 new S55 report tests** passed separately, including a complete 452-request simulated journal. The **30 S54/Batch P tests** passed against the approved configuration before dispatch. S51's actual saved-bank readiness summary recomputes exactly with all 16 imported stages. Historical freezes are unchanged; only the previously unexecuted S54 budget/price record was amended and refrozen before this run. No clinical validation or historical rescoring is claimed.

## Adding a provider

1. Implement `CandidateProvider.generate()` and/or `JudgeProvider.evaluate()` in `benchmark/providers/`, or a candidate-only runner using the prompt export allowlist like the Gemini pilot.
2. Return the documented structured payload; validate production outputs against `schemas/judge-output.schema.json`.
3. Record provider, requested/returned model ID, prompt/config hashes, actual request parameters, retry policy, time, and Git state in a run manifest. Mark provider defaults and mutable aliases as limited reproducibility; do not invent a pinned snapshot or seed.
4. Keep credentials in environment variables; never store them in config, SQLite, or the ZIP.
5. Add retry/rate-limit handling, structured-output repair with an audit trail, and cost telemetry before a real run.

## Immediate TODOs before any external claim

- [ ] Appoint a clinical safety lead and define jurisdictions, intended users, and excluded uses.
- [ ] Obtain independent clinician review of taxonomy, every case, references, requirements, and critical errors.
- [ ] Create a locked Gold Set with dual review plus adjudication; keep it separate from prompt development.
- [ ] Run judge calibration and bias studies against the Gold Set, including self-preference, verbosity, position, language, demographic, and refusal bias.
- [ ] Define PHI/PII rules; v0.1 should use synthetic/de-identified content only.
- [ ] Set minimum inter-rater reliability and per-category sample-size requirements before publishing rankings.
- [ ] Perform security, privacy, legal, and clinical governance review.
- [ ] Freeze a release manifest and document known limitations.

## Repository map

```text
benchmark/                  Python package and provider abstractions
config/                     Benchmark, rubric, and provider examples
data/examples/              Synthetic unvalidated cases
data/templates/             Authoring and reviewer templates
docs/                       English and Chinese documentation
schemas/                    JSON Schemas
tests/                      Unit and pipeline tests
work/                       Runtime database (created locally)
```

License and organizational policies are intentionally not asserted in this planning scaffold; choose them before publication.
