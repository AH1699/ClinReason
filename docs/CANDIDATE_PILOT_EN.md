# External-model pilot exchange — English

This is a **local, experimental integration workflow**, not a clinical benchmark result. The 24 configured Alpha cases are synthetic drafts; real judge adapters and judge–clinician calibration do not yet exist. No API credential or proprietary endpoint is required for this file-based pilot.

## 1. Export model-visible inputs

```bash
python3 -m benchmark.cli --config config/benchmark.json export-prompts \
  --output work/candidate_prompts.jsonl
```

Each JSONL line contains `case_id`, `case_version`, a SHA-256 `case_content_hash`, `language`, `prompt_template_version`, `instruction`, and `prompt`. The exporter uses an explicit allowlist: **no reference answer, critical requirements, critical-error labels, category, or reviewer notes** are sent to the candidate. The hash binds later answers to the exact case revision; it is not an answer key. Export refuses to overwrite an existing file.

The in-process `CandidateProvider.generate()` route is also limited to case ID, version, language, and prompt. The direct adapter is responsible for adding its approved candidate instruction; it must not load the hidden reference from the dataset.

## 2. Run your model and prepare answers

For every exported line, send only its `instruction` and `prompt` to the model. Put one answer per line into a new JSONL file. Copy the three identity fields exactly from the export:

```json
{"case_id":"HC-GC-TRIAGE-001-EN","case_version":"0.1.0","case_content_hash":"<copy the exact 64-character hash from the export>","text":"<the model's answer>"}
```

Optional fields: `finish_reason` (string or null), `latency_ms` (nonnegative integer or null), and `token_usage` (object of nonnegative integer counters or null). Do not include prompts, references, secrets, or patient information in the answer file. The importer requires **exactly one nonempty answer for every configured case** and rejects duplicates, unknown IDs, stale hashes/versions, and unknown fields. A real model's refusal or error should be recorded as its actual response, not replaced with a fabricated answer; the later runner should track transport failures separately.

## 3. Import and inspect the run

```bash
python3 -m benchmark.cli --config config/benchmark.json import-responses \
  --input work/candidate_answers.jsonl \
  --provider my-provider --model-id my-model --model-version my-snapshot
```

The command returns a `run_id` and stores candidate responses in `work/benchmark.sqlite3`. Model identity is supplied once for the run and is not inferred from a marketing name. The case dataset is checked before import; an existing case ID/version cannot be silently overwritten with changed content.

## 4. Test scoring plumbing only

```bash
python3 -m benchmark.cli --config config/benchmark.json score-imported-demo RUN_ID
python3 -m benchmark.cli --config config/benchmark.json report RUN_ID
```

`score-imported-demo` uses two **mock** judges. They are deterministic lexical fixtures, not clinical experts; their scores have no clinical interpretation. The command requires one unjudged response per snapshotted case and will not rescore an existing run. The report is explicitly labeled `experimental_unvalidated` and includes case-level dimension scores, critical-error/review flags, a per-model category and language breakdown, an overall micro mean, a category macro mean, and coverage. With only two families per category, category means are especially unstable even if the judges were valid.

## What is still required

- Direct API adapters for specific model endpoints, with secret-safe configuration, timeouts, retries, error provenance, and exact model/version capture.
- Real independent judge adapters with schema validation and failure handling; calibrate them against human-graded responses.
- Qualified clinical and bilingual review of cases before interpreting model performance; keep development, calibration, and hidden Gold partitions separate.
- Report sample sizes, uncertainty intervals, and critical-error rates before any public comparison. Never interpret this pilot's mock output as a ranking.
