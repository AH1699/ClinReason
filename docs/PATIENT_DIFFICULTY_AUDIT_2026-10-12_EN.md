# Patient-facing difficulty audit — bounded pilot

This is a **development diagnostic**, not a clinical evaluation, a model ranking, or evidence of expert-level difficulty. The 30 single-turn Alpha families and the separate 16-family two-turn track remain draft. This pilot samples the two-turn track because it can observe whether an answer changes appropriately after new facts arrive. English and Chinese are paired variants of the **same** family, not independent clinical cases.

## Question and preregistered sample

Can the current cases and provisional judge reveal a ceiling, a missed revision, an unsafe error, or a language gap in one candidate? The sample was fixed before the live calls: two families per category, including emergency escalation and restraint from overtriage or overdiagnosis.

| Family | Intended probe |
|---|---|
| HC-MT-TRIAGE-003 | Asymptomatic severe blood pressure followed by chest pressure; revise urgency. |
| HC-MT-TRIAGE-005 | New breathlessness despite a reassuring oximeter reading; do not anchor on one number. |
| HC-MT-MEDSAFE-003 | Ibuprofen with anticoagulation but no current bleeding; avoid both unsafe clearance and automatic emergency framing. |
| HC-MT-MEDSAFE-005 | Ambiguous glucose unit followed by confirmed symptomatic low before driving. |
| HC-MT-REASON-003 | A1C change with anemia treatment and unchanged glucose log; do not infer proven improvement. |
| HC-MT-REASON-004 | Positive FIT followed by a negative home retest and travel barrier; do not cancel follow-up. |

These probes are author hypotheses, not validated difficulty labels. In particular, the existing partial-answer contrasts for TRIAGE-003 and MEDSAFE-005 have unresolved safety classifications; see [clinical review handoff](CLINICAL_REVIEW_HANDOFF_EN.md). This pilot does not use them as ground truth.

## Reproduce the workflow

The following commands use ignored local keys and write only to ignored `work/`. Omit `--live` for a no-network plan, and choose fresh output names for reruns because the CLI refuses to overwrite artifacts. A full candidate run uses 12 conversations / 24 Grok calls; judging uses 12 Gemini calls. Each candidate sees only the current user turn and prior visible conversation. Case labels and the later user turn are withheld until appropriate.

```bash
python3 -m benchmark.cli generate-grok-multiturn \
  --family-ids HC-MT-TRIAGE-003,HC-MT-TRIAGE-005,HC-MT-MEDSAFE-003,HC-MT-MEDSAFE-005,HC-MT-REASON-003,HC-MT-REASON-004 \
  --limit 12 --output work/difficulty_audit_2026-10-12_grok_answers.jsonl --live
python3 -m benchmark.cli judge-multiturn-gemini \
  --answers work/difficulty_audit_2026-10-12_grok_answers.jsonl \
  --limit 12 --output work/difficulty_audit_2026-10-12_gemini_judgments.jsonl --live
python3 -m benchmark.cli difficulty-audit-multiturn \
  --answers work/difficulty_audit_2026-10-12_grok_answers.jsonl \
  --judgments work/difficulty_audit_2026-10-12_gemini_judgments.jsonl \
  --output work/difficulty_audit_2026-10-12_report.json
```

The audit command validates exact case hashes, both manifests, rubric hash, provider identities, equal candidate/judge case sets, score recomputation, and complete English/Chinese family pairs. It reports score distribution, counts at or above 90 and exactly 100, initial/update/revision scores, critical errors by stage, and paired language gaps. These are **descriptions of one AI judge's output**; no score cutoff is a clinical pass standard. Raw prompts, candidate answers, and rationales are excluded from the summary report.

## Observed pilot — local October 12, 2026

Grok 4.7 returned all 12 selected conversations (24 candidate calls); Gemini 3.8 Flash returned all 12 structured judgments. The audit accepted both manifests and recomputed every stored score. All raw answers, rationales, and the machine-readable report remain under ignored `work/`, not in Git.

| Diagnostic | Observed result |
|---|---:|
| Paired families / conversations | 6 / 12 |
| Provisional gated scores exactly 100 | 12 / 12 |
| Provisional initial, update, and revision scores exactly 100 | 12 / 12 for each component |
| Judge-labeled critical errors / hard fails | 0 / 0 |
| EN–ZH score gaps | 0 across all six families |
| Judge-requested human review flags | 0 / 12 |

Each of the three categories had four 100-point conversations. A spot check of the candidate transcripts and judge rationales for triage, medication-safety, and FIT-follow-up cases found that the candidate addressed the *draft stated requirements*; it was **not** an independent medical assessment. The judge rationales sometimes called answers “clinically sound” and never requested human review, but its flags cannot clear the mandatory case and language review gates. Zero score gaps also do not prove translation equivalence.

**Interpretation:** This fixed sample produced no score dispersion under this candidate/judge combination. It is a concrete ceiling observation, not proof that the cases are objectively easy, that the candidate is clinically reliable, or that the judge is correct. The five earlier English controlled triplets did yield strong > partial > unsafe ordering, so the judge is responsive to those authored contrasts; their middle safety classifications remain unresolved. The next round should introduce an independent candidate capability level or imported answers and replicate selected runs before revising the rubric or writing many more cases. Inspect whether any apparent separation survives clinician and bilingual adjudication later.

## Interpretation and next gate

One candidate and one uncalibrated judge can identify suspicious ceilings and cases for inspection but cannot measure cross-model discrimination, repeatability, or clinical correctness. The next difficulty round needs at least another independent candidate capability level (or imported model outputs), repeated runs on selected cases, blinded judge calibration against qualified clinical and bilingual ratings, and an explicit development/held-out split. Analyze family-level scores and language gaps rather than inflating sample size with translations. Failure-driven case revision should target distinct reasoning traps, not merely longer prompts. The clinician-facing professional construct remains a separate track.

The task-specific, controlled-contrast, and human-calibration design follows [official OpenAI evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices). It does not imply that OpenAI validated these cases or this judge.
