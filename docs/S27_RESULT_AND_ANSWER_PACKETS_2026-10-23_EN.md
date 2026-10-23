# Scoring boundary result and case answer packets

## What is complete

The focused S27 experiment completed **32/32 valid judge calls**, with **20/20** predeclared non-ambiguous classifications matched and **8/8** repeated statuses unchanged. The five batch-L families now have **34 provisional criterion boundaries** and **30 bilingual update-answer examples**, plus ten shared initial answers. Xi'an source-image checks resolved the three missing lab units. All **249 local tests pass**.

The portfolio remains **122 development families / 244 language variants**. This batch improves evaluation materials, not case count. No candidate model was called, default scoring was not changed, and approved calibration/hidden Gold remain **0/0**. Professional review remains deferred during partner discussions.

## What the scoring result means

The [protocol](S27_BOUNDARY_PROTOCOL_2026-10-23_EN.md) was frozen in commit `bbb39d1` before calls. Gemini `gemini-3.8-flash` and Grok `grok-4.7` judged one requirement in one family, in both languages. Both consistently classified the clear examples under the revised anchor: full routine plan as met, limited observation as partial, and omission, dismissal or appearance-only emergency substitution as missed. The omission/substitution statuses repeated in all eight pairs. No request failed, no output was repaired and no retry was made.

The [saved-result summary](../data/audit/s27_boundary_summary.json) records all cells and response hashes. The audit binds each result to the scheduled attempt, frozen packet, exact provider response and returned model. Raw responses remain in ignored `work/s27_boundary_2026-10-23/`.

The exploratory ambiguous answer was deliberately excluded from expected-status agreement **before** calls. Its results were:

| Wording | Gemini | Grok |
|---|---|---|
| English | missed | missed |
| Chinese | partial | missed |

That is an unresolved paired-language/interpretation difference, not evidence of systematic language bias. It must not be retroactively given an expected label to improve the result. The focused gate passed as preregistered, but it tests only criterion interpretation. It does **not** establish total-score repeatability, clinical correctness, severity calibration, freedom from duplicate deductions or a suitable model-score distribution. Clear authored examples are easier than unrestricted candidate answers.

S26 remains an incomplete historical run. Neither its files nor scores were modified, and S27 results are not pooled with it. The new anchor is still opt-in. The ~60–70 lower-tier / ~80 average / ~90 premium aspiration remains documented and unfitted.

## Five families now have explicit answer contrasts

The [batch-L anchors](../config/multiturn_criterion_anchors_batch_l_v1.json) bind all 34 requirement positions to the exact English/Chinese case hashes. The existing [source ledger](../data/multiturn/batch_l_provenance.json) still supplies each requirement's evidence and author-inference limits. Boundaries distinguish meaningful incompleteness from absent or contradictory advice and allow equivalent patient-facing wording.

[The answer packet](../data/multiturn/batch_l_contrasts_v1.json) contains ten shared initial answers and three update variants per bilingual case: strong, a one-component omission, and a one-component unsafe replacement. These are authored controls, not model outputs. The labels “strong” and “partial” are response-profile names, not established clinical scores or promises that only one criterion changes.

The [offline audit](../benchmark/batch_l_packet_audit.py) checks every source mapping, case hash, paired language, anchor count, configured unsafe-error ID and literal edit. It constructs 30 judge packets without exposing profile names or expected errors. It cannot determine that the edited component has only one clinical effect; bundled requirements and overlap remain review questions. No new packet has been sent to a judge, and default anchor configuration has not been switched.

Run `python3 -m benchmark.batch_l_packet_audit` to reproduce the structural audit. The packet and source tests reject changed cases, undeclared edits, missing languages, missing sources/anchors and invented error IDs.

## Xi'an progress without inventing a timeline

The local excerpt utility now has an optional `--unit-column-review` mode. It uses an already recognized unit cell to locate a narrow unit-column strip on selected lab rows; it does not unmask headers, unrelated rows or full records. Source pixels, not assumed conventional units, resolved the three earlier gaps. **Five rows across two pages now have visually checked values, ranges and units.** The earlier private record is preserved; the new record is `work/xi_an_lab_review_facts_v2.json`, with private permissions and no Git inclusion.

The [date-role checker](../benchmark/local_temporal_check.py) separately recognizes same-line collection, received and report/test dates. It rejects invalid dates, does not borrow a date from the next OCR line, and never substitutes a report date for a collection date. On the two selected pages, only **one** had a usable same-line collection-time candidate; the other remains unresolved. This is an OCR candidate, not a visually verified timestamp. All date values remain in private `work/xi_an_temporal_candidates_v1.json`.

There is still no verified same-episode linkage, no relative-day event sequence and no Xi'an-derived case. Five checked lab rows do not establish a diagnosis, treatment response or whole-record de-identification. The remaining task is targeted source-layout verification of collection time and identity/encounter linkage, then symptoms/treatments known at the intended decision point—not another broad OCR pass.

## Next execution order

1. **Full scoring repeat:** prepare a fresh version using the original two-family S26 control panel, the S27 anchor change, and unchanged S26 credit/penalty rules. Freeze a maximum of 24 first judgments plus 8 partial repeats before calls. Keep strict point-score ordering and exact criterion/error-vector/score repeatability; do not replace the gate with interval ordering after results. This will test integration rather than only the isolated criterion. It has not been launched.
2. **Batch-L controls:** inspect overlap and acceptable alternatives in the new anchors; select a bounded subset for a separately specified judge-only panel after the full-score integration check. Do not treat source mappings or authored answer profiles as clinician-approved labels.
3. **Xi'an:** resolve the remaining source layout and linkage questions locally. Build a relative timeline only when each event has verified source and time provenance; keep unresolved items empty.
4. **Candidate models later:** only after an interpretable complete full-scoring repeat, design a small candidate pilot. Keep professional clinical/bilingual/methods review deferred but required before external comparative claims.

H103–H106 in the reviewer handoff record the focused-score limits, ambiguous bilingual result, batch-L overlap and private-record checks. No score has been pushed toward the preferred bands.
