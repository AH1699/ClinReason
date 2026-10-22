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
- **Separate multi-turn track:** the pilot and batches C–G total **38 bilingual draft families / 76 two-turn conversations**. [Patient batch G](docs/S7_DEESCALATION_AND_ANSWER_AUDIT_2026-10-20_EN.md) adds four guidance-derived low-acuity/de-escalation controls. This track is not pooled with single-turn Alpha. Earlier contrast-pair transport failures remain unscored.
- **Difficulty audit:** the [paired-language patient-facing pilot](docs/PATIENT_DIFFICULTY_AUDIT_2026-10-12_EN.md) found 12/12 provisional 100s from one Grok candidate and Gemini judge. Rejudging the *same answers* with the same judge configuration changed 0/12 scores or flags; that narrows judge repeatability only, not clinical validity or model discrimination.
- **Separate professional draft:** the original pilot, batch E, and [batch F](docs/PORTFOLIO_AUDIT_BATCH_F_2026-10-15_EN.md) contain **42 clinician-facing families / 84 prompts**: 28 consults, seven medication handoffs and seven evidence appraisals. Twenty-six families are rewritten adaptations of distinct published CC BY case reports with a [source/changes/limitations registry](data/evidence/clinical_case_adaptations.json). The professional rubric is authoring-only; there is no professional score or judge.
- **Overall authoring count:** **112 bilingual families** across the three separate tracks, or 224 language variants. This is a development coverage count, not an aggregate benchmark score or proof of expert difficulty.
- **Portfolio and gap audits:** `python3 -m benchmark.portfolio_audit` checks configured counts, declared provenance, selected mechanism-overlap pairs and the [prospective split plan](data/audit/prospective_split_plan.json); `python3 -m benchmark.development_gap_audit` reports patient-track coverage proxies. All 112 public families remain development-only; no approved calibration or hidden Gold cases exist. The [review queue](data/audit/overlap_and_source_review.json) identifies possible duplication and high-priority source-to-label checks, not approved clinical labels.
- **Second candidate:** the [fixed 12-conversation bilingual Gemini 3.5 Flash-Lite check](docs/CANDIDATE_COMPARISON_2026-10-12_EN.md) completed on a fresh second attempt after the first transport failure. The same provisional Gemini 3.8 Flash judge assigned 10/12 perfect scores versus 12/12 for Grok; two nonzero deltas and a judge-consistency concern are documented. This is a development diagnostic, not clinical validation or a model ranking.
- **Judge consistency:** [matched blinded EN/ZH probes](docs/BILINGUAL_JUDGE_PROBES_2026-10-14_EN.md) were completed by Gemini and, after an explicitly authorized family-sized retry, Grok. Both ranked all four baseline/challenge pairs in the same direction; exact gaps matched in two medication pairs only. Triage deduction size and human-review flags differed. A checked local comparison command verifies case bindings and recomputes scores. These probes are not clinical calibration.
- **Batch-F development model pilot:** [the frozen pilot record](docs/S6_BATCH_F_LIVE_PILOT_2026-10-19_EN.md) reports 8/8 paired-language cases completed for Gemini 3.5 Flash-Lite and Grok 4.6, with Gemini/Grok judging separately; MiniMax M2.7 completed 6/8 before a rejected judge-evidence quote stopped the run. Both complete candidates received 100/100 on the stable *H. pylori* reasoning case in both languages, while the medication cases had substantial judge gaps. No model ranking, clinical calibration or score-band fit follows.
- **Batch-G development checkpoint:** [the S7 audit](docs/S7_DEESCALATION_AND_ANSWER_AUDIT_2026-10-20_EN.md) adds four unscored synthetic controls and documents all seven large same-answer judge gaps. A hash-bound offline scan found three unmistakable English-answer turns to Chinese cases among 46 saved turns; historical scores are unchanged and language equivalence remains unreviewed.
- **Next milestone:** follow the [current execution plan](docs/PROJECT_EXECUTION_PLAN_2026-10-16_EN.md): add exact-case G anchors and answer contrasts, version a response-language expectation and separate adherence check before any new bilingual live comparison, and preserve a separate prospective calibration/hidden track. The batch-F pilot is not a model ranking. Independent clinical and bilingual review is deferred during partner discussions, not waived; no draft label becomes ground truth or externally reportable in the meantime.
- **Deferred:** production-grade candidate connectors, judge calibration against human ratings, hidden Gold Set, external rankings, training, and deployment.

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
