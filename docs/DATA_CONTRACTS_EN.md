# Data Contracts and Versioning v0.1 — English

Canonical machine-readable definitions are in `schemas/`. SQLite stores identifiers in columns and full records as JSON so fields can evolve without immediate database migrations.

## 1. Entity map

| Entity | Purpose | Immutable identity |
|---|---|---|
| Case | Prompt, reference, observable requirements, prohibited errors, provenance | `case_id + case_version + content_hash` |
| Model response | Candidate output and generation metadata | `response_id`; links to exact case and model identity |
| Judge output | One independent structured evaluation | `judge_output_id`; links to response, judge, prompt, rubric |
| Aggregate score | Deterministic combination and gates | `response_id + scoring-policy version` |
| Human review | Expert affirmation, override, escalation, or exclusion | `review_id`; never overwrites raw outputs |
| Case review | Expert validation of authored case content before dataset promotion | `case_review_id`; links to exact case version |
| Pairwise output | Blinded A/B preference | comparison ID plus ordered response IDs and seed |
| Benchmark run | One controlled execution | `run_id` plus reproducibility manifest |
| Version manifest | Complete provenance needed to reproduce/interpret a run | content-addressed release artifact |

## 2. Case contract

Required: stable ID, semantic version, lifecycle status, sector/category, prompt, reference answer, critical requirements, case-specific critical errors, applicable dimensions, and metadata. Each critical error has a stable ID, severity 1–3, and reviewer-facing description. `trigger_terms` are only mock/test aids; production critical errors require semantic judgment.

Recommended production metadata adds case-family ID, author, independent reviewers, jurisdiction, guideline/source references, effective date, intended workflow, sensitivity tags, and change rationale.

For the bilingual Alpha, `language`, `metadata.case_family_id`, `metadata.benchmark_layer`, jurisdiction, locale, and translation method are authoring-policy fields. Global Core release-ready cases require complete `en` and `zh-Hans` variants within each family and use `jurisdiction=global_core`. Family variants share taxonomy, difficulty, benchmark layer, jurisdiction, applicable dimensions, and critical-error IDs/severities while retaining independently reviewed text. Jurisdiction packs use explicit local jurisdictions and region-qualified `metadata.locale` values.

Status transitions are controlled:

```text
draft -> clinician_validated -> gold
  \-> withdrawn / quarantined (release process state)
```

The example status `example_unvalidated` may never transition automatically.

## 3. Model response contract

A response must retain the exact case version, candidate provider/model/snapshot, prompt-template version, request parameters, text, finish reason, latency, usage, timestamp, and optional raw-output reference. Do not infer a model version from a marketing name. If a provider exposes no immutable snapshot, store the returned model string, request date, endpoint revision if available, and mark reproducibility as limited.

## 4. Judge output contract

Each applicable dimension contains a numeric score, applicability flag, concise rationale, and cited evidence from the candidate response. The output separately lists only configured critical-error IDs, confidence, overall rationale, and a human-review flag. Reject unknown fields in production to prevent silent prompt/schema drift.

Store parse/repair history outside the final judge payload. Never silently repair meaning-changing fields. One constrained repair attempt may be allowed; otherwise require review or retry according to a fixed policy.

## 5. Human review contract

Use a pseudonymous reviewer ID, role, qualification scope, conflict disclosure, rubric version, decision, scores, critical-error labels, written notes, and timestamp. Human reviews append records; they do not mutate model or judge output. A separate deterministic resolution process selects the authoritative label and records the adjudication chain.

`human-review.schema.json` covers review of a model response. `case-review.schema.json` separately covers clinical, language-equivalence, methodology, and adjudication review of authored benchmark cases. Do not use a response review as evidence that a case itself was validated.

## 6. Version manifest

Every real run must record:

- benchmark, dataset, rubric, candidate-prompt, and judge-prompt versions;
- each candidate and judge provider, model ID, immutable snapshot/revision when available;
- decoding parameters, seed, timeout, retries, and structured-output mode;
- code commit/release, Python/environment fingerprint, and schema versions;
- case content hashes and source-guideline effective dates;
- creation time and operator/service identity;
- privacy mode and raw-output retention policy.

Never edit a completed manifest. Corrections create a new run and link to the superseded run.

At run creation, the scaffold snapshots the exact active `case_id + case_version + content_hash` set into `run_cases`. Later dataset ingestion may change the active set but cannot silently change an existing run. Historical case versions remain in the case table for auditability.

## 7. Semantic versioning policy

- **Patch:** typo or metadata correction proven not to change expected behavior or scoring.
- **Minor:** added cases, clarified reference/anchors, or backward-compatible schema fields; scores may change and must be labeled with the new version.
- **Major:** taxonomy, weight, gate, intended-use, or incompatible schema changes; cross-major scores are not directly comparable.

Case versions advance independently from dataset versions. Any prompt/reference/requirement/critical-error change creates a new case version and content hash. A dataset release is an immutable list of exact case versions.

## 8. Reproducibility and audit rules

- Use UTC ISO-8601 timestamps.
- Store prompts and parameters by version plus content hash.
- Preserve raw candidate and judge outputs under access controls when policy permits.
- Log retries and provider request IDs without secrets.
- Keep PHI/PII out of logs and v0.1 cases.
- Compute reports from immutable raw records; generated reports carry the run ID.
- Quarantine partially completed or schema-invalid runs from comparisons.

## 9. Extension contract

New sectors reuse the entity and versioning contracts. They may add sector metadata and rubric dimensions, but cannot weaken run provenance or critical-error traceability. Cross-sector score comparison is prohibited unless a separate calibration study supports it.
