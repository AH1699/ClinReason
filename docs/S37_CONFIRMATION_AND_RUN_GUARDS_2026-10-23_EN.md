# S37 — confirmation cases and offline run safeguards

Status: offline checkpoint, not a frozen or authorized live protocol. No model API requests, charges, new model scores or changes to historical scoring. Expert review stays later.

Verification: **487 tests pass, including 36 new**. S37 audit and the unchanged 125-family portfolio audit pass; prior scoring freezes remain intact.

## What is ready

All six confirmation reservations now have exact bilingual case and anchor hashes. Three are existing batch-L drafts; three are newly authored from public guidance. They remain outside the nine-family development tuning panel.

| Slot | Family | Purpose in this small panel |
|---|---|---|
| C01 | `HC-MT-REASON-019` | Existing conditional reasoning |
| C02 | `HC-MT-MEDSAFE-016` | Existing conflicting medication evidence |
| C03 | `HC-MT-MEDSAFE-017` | Existing conflicting medication evidence |
| C04 | `HC-MT-TRIAGE-022` | New routine triage: a small nosebleed resolves |
| C05 | `HC-MT-REASON-023` | New routine reasoning: incidental gallbladder stones |
| C06 | `HC-MT-TRIAGE-023` | New conditional triage: presumed blockage becomes sudden hearing loss |

The panel has two families per design stratum and two per category, with both languages. “Routine” and “conditional” describe author intent, not measured model difficulty. Routine cases are necessary controls against indiscriminate escalation; the broader panel still includes conflicting-evidence cases.

New material lives in:

- [Cases](../data/confirmation/s37_cases_v1.json): six language variants, two turns each.
- [Reference answers](../data/confirmation/s37_reference_answers_v1.json): twelve author-written stage examples, **not Gold, expected scores or development controls**.
- [Scoring anchors](../data/confirmation/s37_anchors_v1.json): met/partial/missed boundaries and acceptable equivalents for eighteen stage requirements.
- [Source mapping](../data/confirmation/s37_provenance_v1.json): all eighteen requirements and six named errors, with limits and later review questions.
- [Six-family reservation](../config/confirmation_s37_reservation_v1.json): exact case/anchor bindings and no-tuning rule.

Default development remains **125 families / 250 language variants**. The three new families add six separately reserved variants, not three additional development or approved calibration cases. The existing three reservations are already included in 125; do not count them twice. Approved calibration and hidden Gold remain zero. The existing ten prospective calibration drafts remain separate.

## Evidence and isolation

These are original synthetic dialogues, not actual patient records or purchased-question adaptations. Sources were opened: [NHS nosebleed guidance](https://www.nhs.uk/conditions/nosebleed/), [NIDDK gallstone treatment](https://www.niddk.nih.gov/health-information/digestive-diseases/gallstones/treatment), [NHS gallstones](https://www.nhs.uk/conditions/gallstones/), and [NIDCD sudden hearing loss](https://www.nidcd.nih.gov/health/sudden-deafness). NICE pages returned access errors and are not cited as verified answer evidence. No precise global 24-hour referral rule is inferred.

Guidelines support broad behavior, not our exact credit levels, severity choices or bilingual equivalence. Chinese dialogue was composed naturally; the inherited schema tag `machine_translation_unreviewed` indicates that professional language validation is still absent. H127 records the remaining clinical questions. No Xi’an material, personal data, private holdout content or purchased text was used.

The audit checks normalized source URLs and existing declared mechanism groups against the selected development panel. These checks do not establish complete clinical-concept independence or freedom from model pretraining contamination. A filename-only search of local attempt/judgment/response/answer artifacts found no matching reserved IDs; that is not proof of no external exposure. The reservations are public drafts, not a hidden test set.

No target-model query was made on the new cases. The twelve stage packets exercise structure and initial/update visibility only; **zero reference examples were numerically scored**. Before confirmation, freeze the shared scoring version. Use confirmation once; pass, fail or inconclusive all end the cycle. Never tune on its results.

## Budget correction: an estimate is not a hard cap

The S36 count design remains 816 first-phase requests and at most 504 later requests, with separate approvals. Its $55/$35/$90 figures were proposed limits, not authorization. Its token-ceiling cost scenario assumed 8,192 output tokens covered reasoning as well as the visible response. That assumption is not established across the roster.

[xAI’s current guide](https://docs.x.ai/developers/model-capabilities/text/best-practices) explicitly excludes reasoning from the visible-output cap. Therefore a client counter using that cap cannot guarantee the earlier dollar limit. A timeout also does not prove generation or billing stopped.

[Google’s Generate Content thinking guide](https://ai.google.dev/gemini-api/docs/generate-content/thinking.md) describes a combined thinking/output limit. The project’s Gemini adapter uses [Interactions](https://ai.google.dev/api/interactions-api), so exact endpoint behavior still needs verification; we have not silently changed endpoints. [MiniMax’s compatibility documentation](https://platform.minimax.io/docs/api-reference/text-openai-api) describes generation limits including thinking, but the [current price overview](https://platform.minimax.io/docs/pricing/overview) does not settle M2.7’s rate. Its earlier successful calls are not evidence of today’s price. No provider is declared broken or removed.

Input bounds also need a verified method. Character-count heuristics are not a certified token upper bound, especially with provider-added prompt tokens. Unknown rates or bounds must block admission, not silently use an average estimate.

## What the guard code does—and does not do

[Run guard primitives](../benchmark/run_guard_s37.py) now provide provider-specific candidate payload drafts, decimal cost-reservation arithmetic, and a private, exclusive, synchronized fixture journal. An attempt and payload are saved before simulated dispatch; raw bytes are saved before JSON parsing. Malformed JSON, HTTP errors, wrong model IDs, validation rejection and interruptions remain visible. Failed or uncertain attempts retain their reservation. First technical failure stops the run; no retry, resume or automatic repair. Valid `unclear` judgments remain data rather than a reason to resample.

Files use mode 0600 inside a new 0700 directory. Exception text is not copied into metadata. The fixture journal accepts bytes/errors, not a network transport; no key loading or live HTTP exists here. The admission check stays closed even if someone flips readiness flags. `store=false` is only a request setting, not a promise of provider zero retention.

Still unfinished: full ordered live orchestration and gates, actual HTTP raw-body capture, verified per-request billing bounds/prices, usage reconciliation, effective sampling freeze and an approval-bound protocol fingerprint. The [offline snapshot](../config/s37_offline_frozen_v1.json) freezes this completed checkpoint, **not those unfinished live components**. Historical S26–S36 files/results remain unchanged.

## Next decision and execution order

1. Settle how to enforce spending before requesting call approval. Prefer verified all-billed-token bounds; if unavailable, evaluate a dedicated provider-side budget arrangement with the owner. [xAI billing documentation](https://docs.x.ai/console/billing) describes rejection after prepaid credit depletion when invoiced billing is zero, but team balance, auto top-ups, concurrent use and in-flight overshoot need checking. No account setting was inspected or changed, and an existing balance is not automatically an experiment cap.
2. Verify M2.7’s current price and exact endpoint settings; finish the live dispatcher and mocked end-to-end schedule/gate tests. Preserve Gemini/Grok/MiniMax, two versions each.
3. Freeze a complete new protocol, then request explicit disclosure/call/cost approval. Run controls before development, permit only the predeclared single engineering revision, then separately approved confirmation. Current live allowance remains **zero**.

The scoring objective remains approximately **80 averaged across the fixed broader roster**, separately per judge—not 80 for every model. No score curves, safety relaxation, model selection after results or manufactured difficulty. Clinical review stays a later validation/release gate, not the reason live work is paused now.

Reproduce offline checks with `python3 -m benchmark.confirmation_s37` and `python3 -m unittest discover -s tests -q`. See the [machine-readable audit](../data/audit/s37_confirmation_summary.json) and [readiness record](../config/run_s37_readiness_v1.json).
