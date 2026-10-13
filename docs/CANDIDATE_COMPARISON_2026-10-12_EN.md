# Fixed bilingual second-candidate check — attempted, no new score

The earlier Grok 4.7 → Gemini 3.8 Flash pilot gave **12/12 provisional 100s** on six paired patient-facing two-turn families. This check fixes the same 12 case IDs before looking at a second candidate: `HC-MT-TRIAGE-003/005`, `HC-MT-MEDSAFE-003/005`, and `HC-MT-REASON-003/004`, English and Chinese for each. The sample balances three categories but is tiny, synthetic, unreviewed, and not held out. The aim is to see whether one weaker/different candidate breaks the ceiling, **not** to rank models.

The selected second candidate is Google `gemini-3.5-flash-lite`, distinct from the `gemini-3.8-flash` judge. [Google's model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) lists the exact candidate ID. The new adapter uses the [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview) with `store=false`, resending only previously visible user/assistant text at each turn. Unlike the Grok adapter's native role messages, Gemini receives a role-delimited text transcript; this **prompt serialization difference is a confound**. A Google candidate assessed by a Google judge also introduces same-vendor preference risk. Both model IDs and the request format are recorded in the local manifest; sampling remains provider-default/unpinned.

## Result as of 2026-10-12

The dry run planned **12 conversations / 24 candidate calls** and made no network calls. The first opt-in live call returned `Provider transport failed; delivery state is unknown`. No candidate answer or manifest file was written, no Gemini judgment was requested, and **no second-candidate score or comparison exists**. An uncertain delivery is not automatically retried because it may duplicate a charged request. The old Grok result was re-audited successfully against its historical pilot + batch-C dataset revision in `work/difficulty_audit_2026-10-12_grok_report_v2.json`; that remains 12/12 provisional 100 and does not become more valid by itself.

## Reproducible continuation when transport is available

Use a **fresh output basename** only after deciding to retry the uncertain request; do not overwrite or silently merge attempts. Keep `.env.local` and raw `work/` artifacts local/ignored. The candidate sample must be selected exactly as follows:

```bash
python3 -m benchmark.cli generate-gemini-multiturn \
  --model gemini-3.5-flash-lite --limit 12 \
  --family-ids HC-MT-TRIAGE-003,HC-MT-TRIAGE-005,HC-MT-MEDSAFE-003,HC-MT-MEDSAFE-005,HC-MT-REASON-003,HC-MT-REASON-004 \
  --output work/difficulty_audit_gemini35lite_attempt2_answers.jsonl --live
```

If and only if all 12 candidate conversations complete, judge all **12 conversation packets (24 staged turns)** with the configured `gemini-3.8-flash` model using `judge-multiturn-gemini --answers ... --limit 12 --output ... --live`. Then run `difficulty-audit-multiturn` on those answer/judgment files with the current three configured batch files, and compare it to the historical Grok report with `compare-multiturn-candidates --first-report work/difficulty_audit_2026-10-12_grok_report_v2.json --second-report ... --output ...`. The comparison rejects different case sets, case hashes, rubric, judge model identity, and instruction hashes. It reports case-level score deltas and ceiling counts, not a public ranking. A complete run still needs repeat candidate samples, independent judge calibration, and qualified clinical/bilingual ratings before any discriminative-validity claim.

The local measurement design follows [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices) on representative cases, human calibration, and inspecting variability. We do not use or depend on OpenAI's hosted Evals platform.
