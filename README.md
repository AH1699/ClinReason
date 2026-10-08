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

- **Complete:** bilingual design package, draft charter, risk register, authoring guide, machine-readable contracts, offline pipeline, scoring/gating, data validation, append-only review workflow, reviewer packet export, and mock tests.
- **Development examples:** six English-only synthetic infrastructure fixtures remain under `data/examples/`.
- **Alpha draft:** the configured dataset is the bilingual, jurisdiction-neutral Global Core under `data/alpha/`. It currently contains 12 matched families / 24 prompts, with two families in each category. All remain unvalidated drafts until expert review.
- **Next milestone:** assign qualified reviewers, run the first clinical and language-equivalence review round, resolve requested changes, and then expand the Global Core to 30–50 bilingual families.
- **Deferred:** real candidate/judge API adapters, judge calibration, hidden Gold Set, external rankings, training, and deployment.

## Adding a provider

1. Implement `CandidateProvider.generate()` and/or `JudgeProvider.evaluate()` in `benchmark/providers/`.
2. Return the documented structured payload; validate production outputs against `schemas/judge-output.schema.json`.
3. Pin provider, model ID/snapshot, prompt version, parameters, retry policy, and code revision in a run manifest.
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
