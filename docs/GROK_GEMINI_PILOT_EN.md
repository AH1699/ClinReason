# Local Grok → Gemini pilot

This is an **experimental integration test**, not a validated healthcare benchmark. Grok is the candidate; Gemini is a single provisional AI judge. The 24 bilingual Alpha cases and their reference answers are drafts. No clinical or language review gate is cleared by this workflow.

## Local settings

The ignored `.env.local` contains four fields:

```text
GROK_API_KEY=replace-with-your-key
GROK_MODEL=grok-4.7
GEMINI_API_KEY=replace-with-your-key
GEMINI_JUDGE_MODEL=gemini-3.8-flash
```

Replace the two key placeholders on your computer; do not send keys in chat or commit them. Model IDs are nonsecret but belong in configuration so a run is explicit and repeatable. The CLI also accepts `--model` overrides. The file is read as literal data, not executed. The provided local file is ignored by Git and permissioned for your account only. A separate `.env` is also ignored; pass `--env-file .env` if you choose to use it instead. Check current model access in [xAI's models list](https://docs.x.ai/developers/rest-api-reference/inference/models) and [Gemini's models list](https://ai.google.dev/gemini-api/docs/models). Aliases can move; a returned model ID is not always an immutable snapshot.

## 1. Candidate: Grok

Dry run (no key or network):

```bash
python3 -m benchmark.cli generate-grok --limit 1 --output work/candidate_grok_smoke.jsonl
```

One live case, then inspect the answer and manifest locally:

```bash
python3 -m benchmark.cli generate-grok --limit 1 --live --output work/candidate_grok_smoke.jsonl
```

Full set, using a new output path:

```bash
python3 -m benchmark.cli generate-grok --limit 24 --live --output work/candidate_grok_answers.jsonl
```

The runner uses [xAI's Responses API](https://docs.x.ai/developers/rest-api-reference/inference/responses) with `store: false`. It sends only the approved candidate instruction and case prompt; no reference answer, rubric, or critical-error labels. It records answer text, latency, token counts when available, requested/returned model IDs, and exact case revisions. An incomplete/failed response produces no answer file; transport failures have uncertain delivery and are not retried automatically. HTTP 429/5xx may be retried twice. The one-case file cannot be imported as a complete run. A full candidate failure does not currently resume; repeat calls may add cost.

## 2. Import exact-revision answers

Read `returned_model` from `work/candidate_grok_answers.manifest.json`, then use that value for `--model-version`:

```bash
python3 -m benchmark.cli import-responses \
  --input work/candidate_grok_answers.jsonl \
  --provider xai-grok --model-id grok-4.7 --model-version RETURNED_MODEL_ID
```

Copy the resulting `run_id`. If you override `GROK_MODEL`, use that requested ID for `--model-id`. The importer rejects missing/duplicate answers and stale case hashes.

## 3. Provisional judge: Gemini

The judge receives the candidate answer plus the **draft** reference, critical requirements/errors, and rubric. It does not receive Grok's identity. Gemini's [structured-output mode](https://ai.google.dev/gemini-api/docs/structured-output) requests JSON; local validation rejects unknown dimensions, inapplicable scores, invented critical-error IDs, changed severities, and malformed fields.

```bash
python3 -m benchmark.cli judge-imported-gemini RUN_ID --limit 1
python3 -m benchmark.cli judge-imported-gemini RUN_ID --limit 1 --live
python3 -m benchmark.cli judge-imported-gemini RUN_ID --limit 24 --live
python3 -m benchmark.cli report RUN_ID
```

The first command is a no-network plan. The first live command judges one answer; the next judges the remaining 23 and scores only after all 24 have valid judgments. Unlike the candidate run, successful judgments are saved one by one and can be resumed after a failure. Each call uses `store: false`, no search tools, and the selected Gemini model ID. The scoring report remains `experimental_unvalidated`. One uncalibrated AI judge and two draft case families per category cannot support clinical claims, model rankings, or a meaningful safety certification. Qualified clinicians, bilingual reviewers, independent judges, and human calibration are still required.
