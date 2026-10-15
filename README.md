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
- `docs/MULTITURN_BATCH_C_2026-10-11_EN.md` and `docs/MULTITURN_BATCH_C_2026-10-11_ZH.md`: source-linked 12-family two-turn expansion, partial-answer diagnostics, and pending review questions.
- `docs/PATIENT_DIFFICULTY_AUDIT_2026-10-12_EN.md` and `docs/PATIENT_DIFFICULTY_AUDIT_2026-10-12_ZH.md`: bounded paired-language difficulty pilot, exact local commands, descriptive metrics, and interpretation limits.
- `docs/PROFESSIONAL_PILOT_2026-10-12_EN.md` and `docs/PROFESSIONAL_PILOT_2026-10-12_ZH.md`: a separate four-family clinician-facing draft, prompt-only export, evidence links, and unresolved review questions; scoring is disabled.
- `docs/CANDIDATE_COMPARISON_2026-10-12_EN.md` and `docs/CANDIDATE_COMPARISON_2026-10-12_ZH.md`: completed fixed bilingual second-candidate diagnostic, transport-attempt history, case-level findings, and comparison limits.
- `docs/BILINGUAL_JUDGE_PROBES_2026-10-14_EN.md` and `docs/BILINGUAL_JUDGE_PROBES_2026-10-14_ZH.md`: matched blinded English/Chinese near-miss judge probes, provisional Gemini findings, and an incomplete second-provider attempt.
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
- **Separate multi-turn track:** the [pilot](docs/MULTITURN_PILOT_2026-10-11_EN.md), [batch C](docs/MULTITURN_BATCH_C_2026-10-11_EN.md), and [batch D](docs/MULTITURN_BATCH_D_2026-10-12_EN.md) total **20 bilingual draft families / 40 two-turn conversations**. This track is not pooled with single-turn Alpha. Two new subtle English contrast pairs are offline-tested only; their attempted live judge run failed at transport and produced no score.
- **Difficulty audit:** the [paired-language patient-facing pilot](docs/PATIENT_DIFFICULTY_AUDIT_2026-10-12_EN.md) found 12/12 provisional 100s from one Grok candidate and Gemini judge. Rejudging the *same answers* with the same judge configuration changed 0/12 scores or flags; that narrows judge repeatability only, not clinical validity or model discrimination.
- **Separate professional draft:** [four clinician-facing families / eight prompts](docs/PROFESSIONAL_PILOT_2026-10-12_EN.md) now cover CKD chronicity, bacteriuria/delirium reasoning, anticoagulant-list handoff, and appraisal of invented trial rates. The professional rubric is authoring-only; there is no professional score or judge.
- **Second candidate:** the [fixed 12-conversation bilingual Gemini 3.5 Flash-Lite check](docs/CANDIDATE_COMPARISON_2026-10-12_EN.md) completed on a fresh second attempt after the first transport failure. The same provisional Gemini 3.8 Flash judge assigned 10/12 perfect scores versus 12/12 for Grok; two nonzero deltas and a judge-consistency concern are documented. This is a development diagnostic, not clinical validation or a model ranking.
- **Judge consistency:** [matched blinded EN/ZH probes](docs/BILINGUAL_JUDGE_PROBES_2026-10-14_EN.md) found positive Gemini gaps for all four controlled first-turn near-misses, with a 3-point cross-language difference in the triage gap. An independent Grok judge attempt failed at transport with no complete result, so cross-provider agreement remains unknown. These probes are not clinical calibration.
- **Next milestone:** complete an independent-provider judge pass after the transport path is reliable, then have qualified reviewers adjudicate the natural answers and controlled probes for `TRIAGE-003`/`MEDSAFE-003` before external comparisons. Professional clinical/language review is deliberately deferred but mandatory before validation or release. Counts and infrastructure tests are not quality guarantees.
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
