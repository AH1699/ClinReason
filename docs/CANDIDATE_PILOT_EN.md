# External-model pilot exchange — English

This is a **local, experimental integration workflow**, not a clinical benchmark result. The 24 configured Alpha cases are synthetic drafts; real judge adapters and judge–clinician calibration do not yet exist. The file-based path needs no API key. The optional Gemini runner makes live, potentially billable calls only with `--live`.

## 1. Export model-visible inputs

```bash
python3 -m benchmark.cli --config config/benchmark.json export-prompts \
  --output work/candidate_prompts.jsonl
```

Each JSONL line contains `case_id`, `case_version`, a SHA-256 `case_content_hash`, `language`, `prompt_template_version`, `instruction`, and `prompt`. The exporter uses an explicit allowlist: **no reference answer, critical requirements, critical-error labels, category, or reviewer notes** are sent to the candidate. The hash binds later answers to the exact case revision; it is not an answer key. Export refuses to overwrite an existing file.

The in-process `CandidateProvider.generate()` route is also limited to case ID, version, language, and prompt. The direct adapter is responsible for adding its approved candidate instruction; it must not load the hidden reference from the dataset.

## Optional: run Gemini locally

Copy `.env.example` to `.env.local` in the project root and set `GEMINI_API_KEY` there, or set that environment variable yourself. Do not paste the key into chat, a command line, a tracked config file, or the future browser UI. `.env.local` is git-ignored; verify it remains untracked before committing. The runner reads the file as literal data, never executes it. Keep it readable only by your account (for example, `chmod 600 .env.local`). Google also recommends server-side key handling for applications; a later dashboard should send model requests through a backend, not expose the key to browser JavaScript. See [Google's API-key guidance](https://ai.google.dev/gemini-api/docs/api-key).

First inspect the planned call without using a key or network:

```bash
python3 -m benchmark.cli --config config/benchmark.json generate-gemini \
  --model YOUR_EXACT_GEMINI_MODEL_ID --limit 1 \
  --output work/candidate_gemini_smoke.jsonl
```

Then make one live smoke call (choose an [available model ID](https://ai.google.dev/gemini-api/docs/models) for your key):

```bash
python3 -m benchmark.cli --config config/benchmark.json generate-gemini \
  --model YOUR_EXACT_GEMINI_MODEL_ID --limit 1 --live \
  --output work/candidate_gemini_smoke.jsonl
```

After inspecting that answer, run all configured cases with an explicit new output path:

```bash
python3 -m benchmark.cli --config config/benchmark.json generate-gemini \
  --model YOUR_EXACT_GEMINI_MODEL_ID --limit 24 --live \
  --output work/candidate_gemini_answers.jsonl
```

The default limit is one case; `--live` is always required. The runner sends only the instruction and prompt from the same allowlisted export, with `store: false` to the [Gemini Interactions API](https://ai.google.dev/api/interactions-api-v1). It does not request Google Search or other tools. It records answer text, latency, token counts when returned, and a local manifest with requested and returned model IDs and exact case revisions. Neither answers nor manifest contain the key, and both are git-ignored. The returned model ID is not necessarily an immutable model snapshot; record any provider-side version information separately if needed. A transport failure has uncertain delivery/cost and is not auto-retried; HTTP 429/5xx is retried up to twice. Failed or incomplete interactions produce no answer file. Outputs are never overwritten. A one-case smoke file is intentionally too short to import into a full 24-case run.

## 2. Run your model and prepare answers

For every exported line, send only its `instruction` and `prompt` to the model. Put one answer per line into a new JSONL file. Copy the three identity fields exactly from the export:

```json
{"case_id":"HC-GC-TRIAGE-001-EN","case_version":"0.1.0","case_content_hash":"<copy the exact 64-character hash from the export>","text":"<the model's answer>"}
```

Optional fields: `finish_reason` (string or null), `latency_ms` (nonnegative integer or null), and `token_usage` (object of nonnegative integer counters or null). Do not include prompts, references, secrets, or patient information in the answer file. The importer requires **exactly one nonempty answer for every configured case** and rejects duplicates, unknown IDs, stale hashes/versions, and unknown fields. A real model's refusal should be recorded as its actual response, not replaced with a fabricated answer; transport or incomplete-response failures are not candidate answers.

## 3. Import and inspect the run

```bash
python3 -m benchmark.cli --config config/benchmark.json import-responses \
  --input work/candidate_answers.jsonl \
  --provider my-provider --model-id my-model --model-version my-snapshot
```

The command returns a `run_id` and stores candidate responses in `work/benchmark.sqlite3`. Model identity is supplied once for the run and is not inferred from a marketing name. The case dataset is checked before import; an existing case ID/version cannot be silently overwritten with changed content.

For Gemini, use `--provider google-gemini`, the exact requested ID for `--model-id`, and the `returned_model` from the generated manifest for `--model-version`. The returned ID may still be an alias, so do not claim immutable snapshot reproducibility unless the provider guarantees it.

## 4. Test scoring plumbing only

```bash
python3 -m benchmark.cli --config config/benchmark.json score-imported-demo RUN_ID
python3 -m benchmark.cli --config config/benchmark.json report RUN_ID
```

`score-imported-demo` uses two **mock** judges. They are deterministic lexical fixtures, not clinical experts; their scores have no clinical interpretation. The command requires one unjudged response per snapshotted case and will not rescore an existing run. The report is explicitly labeled `experimental_unvalidated` and includes case-level dimension scores, critical-error/review flags, a per-model category and language breakdown, an overall micro mean, a category macro mean, and coverage. With only two families per category, category means are especially unstable even if the judges were valid.

## What is still required

- More candidate API adapters and stronger provider provenance, cost controls, resumable runs, and immutable model snapshot capture where the provider supports it. The Gemini adapter is a first local pilot, not a general production connector.
- Real independent judge adapters with schema validation and failure handling; calibrate them against human-graded responses.
- Qualified clinical and bilingual review of cases before interpreting model performance; keep development, calibration, and hidden Gold partitions separate.
- Report sample sizes, uncertainty intervals, and critical-error rates before any public comparison. Never interpret this pilot's mock output as a ranking.
