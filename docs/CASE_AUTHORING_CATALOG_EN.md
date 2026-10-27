# Find cases and prepare the next expansion batch

The public draft inventory contains **129 distinct families**: 125 registered development families and four standalone drafts. Each has English and Chinese versions. The new catalog makes these cases discoverable without adding the standalone drafts to a benchmark run or changing historical inputs. It does not create new cases or count calibration, confirmation or private Xi’an records toward this total.

## Find a case and its answer labels

Run these commands from the project directory:

```sh
python3 -m scripts.authoring_catalog --summary
python3 -m scripts.authoring_catalog
```

The full output lists each family ID, track, registration status, case file, languages, content hash, source references and where its answer labels live. [The catalog configuration](../config/authoring_catalog_v1.json) lists the standalone batches; [the existing benchmark configuration](../config/benchmark.json) remains the authority for registered development datasets.

| Track | Families | Where the expected answer lives |
|---|---:|---|
| Alpha single turn | 32 registered | `reference_answer`, `critical_requirements` and `critical_errors` inside each JSONL case |
| Patient multi-turn | 51 registered | Each turn's `critical_requirements` and `critical_errors`; a scoring experiment must also select and freeze the corresponding exact-case anchors |
| Professional | 42 registered | Each language variant's `reference_elements` and `critical_errors`; professional scoring remains disabled |
| Standalone O and P | 4 unregistered | Separate cases, anchors, reference examples and source mappings linked below |

[Batch O](BATCH_O_STANDALONE_EN.md) covers competing fluid/renal concerns and nutrition-related electrolyte changes. [Batch P](S54_LIVE_ADMISSION_AND_BATCH_P_EN.md#new-cases-and-answer-labels) covers unreliable platelet measurements and discordant clinic/home blood-pressure readings. Their labels are author drafts, not clinically approved answers. Neither is silently added to the current scoring panel.

## Next expansion work

The target remains **at least 500 distinct families**, leaving 371 additional public draft families beyond this inventory. Rewordings, translations and controlled-answer variants do not reduce that gap. Reaching the draft count will not establish clinical readiness.

The next batch should add four distinct, source-backed reasoning problems. Use the panel readout to prioritize gaps, but keep the new cases separate from the measured cases. Favor competing explanations, changes over time, treatment trade-offs and evidence that changes a decision. Avoid giving the intended conclusion away in the patient's question. Balance difficult problems with appropriate restraint; “always escalate” should not be a shortcut to a high score.

For each new family, deliver an original bilingual conversation, stage-specific expected behaviors, acceptable alternatives, proposed critical errors, reference answers with controlled omissions, and a source-to-requirement map. Published actual cases can supply mechanisms and decision sequences; they do not automatically validate the synthetic answer key. Record source limits and unresolved clinical or language questions when authoring, and keep patient identifiers and source images out of public drafts.

Before a new batch is used in an experiment, check identity and source overlap with development and reserved sets, verify case-to-label hashes, and freeze its own inputs. Do not alter the completed panel or fit labels to produce lower-tier 60–70, average around 80 or premium around 90. Those remain diagnostic aspirations. Expert clinical and bilingual review stays deferred, not waived.

The catalog's structural tests cover counts, duplicate IDs/files, paired languages and public-path boundaries. It does not assess medical correctness, measured difficulty or release readiness.

## First source leads for the next batch

Two leads were screened on October 26, 2026 (New York time). They are not authored cases or approved answer labels yet:

- **Iron treatment versus a new metabolic complication.** [Fang et al.'s published case](https://doi.org/10.1002/jgh3.12150) describes symptomatic hypophosphatemia after repeated ferric carboxymaltose. [MHRA guidance](https://www.gov.uk/drug-safety-update/ferric-carboxymaltose-ferinject-risk-of-symptomatic-hypophosphataemia-leading-to-osteomalacia-and-fractures), including its September 2026 product note, supports risk-based phosphate monitoring and treatment reassessment when low phosphate persists. Authoring hypothesis: test whether new symptoms prompt reassessment rather than automatic treatment escalation. Separate this from the existing refeeding case; do not infer a universal treatment or replacement dose.
- **A worsening postoperative wound with competing explanations.** [Wanner et al.'s case report](https://pmc.ncbi.nlm.nih.gov/articles/PMC7595358/) describes postoperative pyoderma gangrenosum mimicking other wound problems. Authoring hypothesis: reassess a poorly responding wound without prematurely excluding infection. Before drafting labels, add current differential/management guidance and define a safe clinical-review pathway; this report alone cannot justify withholding urgent surgery or starting immunosuppression.

The keyword screen is only an initial overlap check. Full source and mechanism comparison with reserved datasets remains required. Keep these as mechanisms for newly written synthetic conversations, with no copied patient narrative or image.
