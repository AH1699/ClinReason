# Fixed bilingual second-candidate check — completed draft diagnostic

The earlier Grok 4.7 → Gemini 3.8 Flash pilot gave **12/12 provisional 100s** on six paired patient-facing two-turn families. This check fixes the same 12 case IDs before looking at a second candidate: `HC-MT-TRIAGE-003/005`, `HC-MT-MEDSAFE-003/005`, and `HC-MT-REASON-003/004`, English and Chinese for each. The sample balances three categories but is tiny, synthetic, unreviewed, and not held out. The aim is to see whether one weaker/different candidate breaks the ceiling, **not** to rank models.

The selected second candidate is Google `gemini-3.5-flash-lite`, distinct from the `gemini-3.8-flash` judge. [Google's model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) lists the exact candidate ID. The new adapter uses the [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview) with `store=false`, resending only previously visible user/assistant text at each turn. Unlike the Grok adapter's native role messages, Gemini receives a role-delimited text transcript; this **prompt serialization difference is a confound**. A Google candidate assessed by a Google judge also introduces same-vendor preference risk. Both model IDs and the request format are recorded in the local manifest; sampling remains provider-default/unpinned.

## Result as of 2026-10-12 (local time)

The dry run planned **12 conversations / 24 candidate calls**. The first opt-in live attempt failed at transport with unknown delivery state and no artifact. Following a new explicit request to proceed, a **separate second attempt** completed all 12 conversations and 24 model calls under a fresh ignored `work/` basename. The configured Gemini 3.8 Flash judge then completed 12 conversation-level calls (24 staged turns). Both candidate and judge manifests recorded returned model IDs and exact case revisions. The prior Grok result was separately re-audited against its historical pilot + batch-C dataset; the newer Gemini run used pilot + C + D. Although the merged dataset hashes differ, all 12 selected case-content hashes match exactly.

| Draft diagnostic | Grok 4.7 candidate | Gemini 3.5 Flash-Lite candidate |
|---|---:|---:|
| Provisional 100/100 conversations | 12/12 | 10/12 |
| Provisional mean gated score | 100.00 | 98.46 |
| Judge-flagged critical errors / hard fails | 0 / 0 | 0 / 0 |
| Judge-requested human review | 0 | 0 |

The two nonzero case deltas were `HC-MT-MEDSAFE-003-EN` (100 → **97**) and `HC-MT-TRIAGE-003-ZH-HANS` (100 → **84.5**). For the former, the judge deducted initial-turn requirements because the answer told the patient to disclose the product but did not explicitly ask which anticoagulant they take. For the latter, it deducted for describing an asymptomatic first reading as an emergency and recommending an ambulance/ED before distinguishing the repeat-without-symptoms pathway; the updated turn with chest pressure scored 100. All other case scores remained 100. These are AI-judge observations, not independent clinical findings. Manual inspection suggests the Chinese `MEDSAFE-003` answer also did not explicitly elicit the anticoagulant name, despite a 100 score; this requires the same consistency check.

Manual transcript inspection raised a separate **judge-consistency question**: the English response for `TRIAGE-003` also says a persistently high repeat reading **or** new red-flag symptoms should prompt an ambulance, but the judge awarded its initial turn 100. The case key and the [American Heart Association source](https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/when-to-call-911-for-high-blood-pressure) distinguish repeated severe readings without symptoms (prompt clinician contact) from readings with concerning symptoms (emergency response). Whether the English wording should lose points requires qualified adjudication; the asymmetry is an inference from the stored text, not a clinical verdict. The Chinese response also gives example emergency numbers despite the prompt specifying no country, another portability issue not reflected in its AI score. Both are added to the review queue.

**Interpretation:** one second candidate produced slight score dispersion, but 10/12 remain at the ceiling. This does not establish model discrimination, a statistically meaningful score gap, safe clinical behavior, or a ranking. There is one run per candidate, one uncalibrated judge, unreviewed translations, a Google candidate judged by Google, and different provider transcript serialization. Every provisional score still requires human review under the pipeline.

## Local artifacts and next measurement gate

The completed candidate output is `work/difficulty_audit_2026-10-12_gemini35lite_attempt2_answers.jsonl`; the judge output is the same basename ending `_judgments.jsonl`. The checked Gemini audit is `work/difficulty_audit_2026-10-12_gemini35lite_attempt2_report.json`, and the matched comparison is `work/difficulty_audit_2026-10-12_cross_candidate_report.json`. The old Grok audit is `work/difficulty_audit_2026-10-12_grok_report_v2.json`. All are ignored locally; `.env.local` and raw outputs were not committed or pushed. Replays require a fresh basename and should not silently merge the failed first attempt.

The fixed candidate selection was:

```bash
python3 -m benchmark.cli generate-gemini-multiturn \
  --model gemini-3.5-flash-lite --limit 12 \
  --family-ids HC-MT-TRIAGE-003,HC-MT-TRIAGE-005,HC-MT-MEDSAFE-003,HC-MT-MEDSAFE-005,HC-MT-REASON-003,HC-MT-REASON-004 \
  --output work/difficulty_audit_2026-10-12_gemini35lite_attempt2_answers.jsonl --live
```

The `compare-multiturn-candidates` command rejected mismatched case sets, case hashes, rubric, judge identity, and instruction hashes before reporting deltas. The next non-clinical work should test judge consistency with blinded, bilingual controlled responses for `TRIAGE-003` and medication-product identification, and add a judge from another provider if feasible. Do **not** rewrite the case key or tune the judge to these observed responses alone. Qualified clinicians and bilingual reviewers remain required before an external score or discriminative-validity claim.

The local measurement design follows [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices) on representative cases, human calibration, and inspecting variability. We do not use or depend on OpenAI's hosted Evals platform.
