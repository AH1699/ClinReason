# Blinded bilingual near-miss judge probes — 2026-10-14

This is a **development diagnostic, not clinical calibration or a model ranking**. The synthetic English/Chinese response pairs in `data/multiturn/bilingual_judge_probes.json` are public and unreviewed. They target two previously observed score asymmetries without changing either case, answer key, judge instruction, or rubric.

## Fixed design

For each language of `HC-MT-TRIAGE-003` and `HC-MT-MEDSAFE-003`, the probe has a baseline first response and a challenge response with one intended near-miss. The second response is identical within the pair. TRIAGE-003 changes only the disposition for a persistently severe reading **without** new symptoms; MEDSAFE-003 changes only whether the response explicitly asks which anticoagulant the patient takes. Case-content hashes pin all four language variants. The judge receives one case-bound packet per call, never the arm name or author hypothesis; call order is counterbalanced within pairs. No candidate-model identity is present in the packet.

The [AHA page](https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/when-to-call-911-for-high-blood-pressure) distinguishes repeat severe blood pressure without symptoms (prompt professional contact) from new concerning symptoms (emergency). The [NHS anticoagulant page](https://www.nhs.uk/medicines/anticoagulants/considerations/) advises checking medicines, remedies, and supplements with a clinician or pharmacist and lists ibuprofen among interacting NSAIDs. These pages support drafting the probes; they do **not** establish a global care pathway or clinically approved labels. Human clinical and bilingual review is still required.

## Provisional results

The opt-in Gemini 3.8 Flash run completed 8 independent judgments on 4 pairs. Baselines scored 100/100 in all four pairs. All four challenge answers scored lower:

| Case | EN challenge / baseline gap | ZH challenge / baseline gap | Initial-turn issue Gemini described |
|---|---:|---:|---|
| TRIAGE-003 | 89.5 / 10.5 | 92.5 / 7.5 | Automatically calling an ambulance after a severe repeat reading even if asymptomatic. |
| MEDSAFE-003 | 97 / 3 | 97 / 3 | Not explicitly asking which anticoagulant is taken. |

Here “gap” is baseline gated score minus challenge gated score. For TRIAGE-003, the first-turn safety gap was 1 point on the 0–4 scale in both languages, but the requirements gap was 2 in EN versus 1 in ZH. Thus the judge detected the same controlled near-miss in both languages while assigning different-sized deductions. For MEDSAFE-003, the first-turn requirements gap was 1 in each language. There were no judge-flagged critical errors; these near-misses are graded through stage scores. All four challenge judgments returned `requires_human_review=false`, but the deterministic scoring layer still marks **every** result as requiring review because this is a single uncalibrated AI judge on draft cases.

The independent-provider Grok run was attempted against the same 8 packets but failed at transport with **unknown delivery state** before a complete result file could be written. It was not automatically retried or counted. The adapter and its structured-output/model-identity tests are in place, but no cross-provider agreement result exists. The number of requests delivered or billed before the failure is unknown. The completed Gemini raw diagnostic is ignored locally at `work/bilingual_probes_2026-10-14_gemini.json`; there is no Grok result artifact.

## Interpretation and next gate

This controlled result shows that Gemini can notice the intended distinctions when wording changes are isolated. It does **not** resolve whether the earlier natural EN and ZH candidate responses were semantically equivalent, whether the original scores were correct, or whether the case labels are clinically appropriate. The TRIAGE-003 3-point cross-language difference on the controlled gap is a calibration question, not a statistical language-bias estimate. Do not tune the judge or rewrite the key to fit these four public probes alone.

Next, complete an independent-provider pass only after the transport path is reliable, then have qualified clinical and bilingual reviewers adjudicate H35/H36 using the *natural answers and these controlled pairs*. Predefine acceptable answer variants and score anchors before any external benchmark score. A separate hidden, human-rated set is still necessary for validity and uncertainty estimates.

Reproduce the local **dry run** (no network or keys required):

```bash
python3 -m benchmark.cli judge-multiturn-bilingual-probes --provider gemini \
  --output work/bilingual_probes_new_gemini.json
python3 -m benchmark.cli judge-multiturn-bilingual-probes --provider grok \
  --output work/bilingual_probes_new_grok.json
```

Add `--live` only when intentionally making paid API calls and use fresh output paths. The runner records the probe-set, instruction, rubric, and config hashes; requested/returned model IDs; provider-default sampling; and `store=false`. Model aliases/default sampling and transport ambiguity limit exact replay. The design follows [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices) on task-specific tests, controlled comparisons, variability, and human-grounded calibration; the project does not use OpenAI's hosted Evals service.
