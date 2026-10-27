# Find cases and prepare the next expansion batch

The public draft inventory contains **133 distinct families**: 125 registered development families and eight standalone drafts. Each has English and Chinese versions. The new catalog makes these cases discoverable without adding the standalone drafts to a benchmark run or changing historical inputs. It does not create new cases or count calibration, confirmation or private Xi’an records toward this total.

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
| Standalone O, P and Q | 8 unregistered | Separate cases, anchors, reference examples and source mappings linked below |

[Batch O](BATCH_O_STANDALONE_EN.md) covers competing fluid/renal concerns and nutrition-related electrolyte changes. [Batch P](S54_LIVE_ADMISSION_AND_BATCH_P_EN.md#new-cases-and-answer-labels) covers unreliable platelet measurements and discordant clinic/home blood-pressure readings. Their labels are author drafts, not clinically approved answers. Neither is silently added to the current scoring panel.

## Next expansion work

The target remains **at least 500 distinct families**, leaving 367 additional public draft families beyond this inventory. Rewordings, translations and controlled-answer variants do not reduce that gap. Reaching the draft count will not establish clinical readiness.

[Batch Q](S59_BATCH_Q_CASE_EXPANSION_EN.md) has added the four planned source-backed reasoning problems. [S60](S60_STANDALONE_PILOT_EN.md) now binds all eight O/P/Q families for an offline pilot proposal; it does not register them or create additional families. Next integrate that pilot with simulated replies while continuing separate expansion. Use the panel readout to prioritize gaps, but keep the new cases separate from the measured cases. Favor competing explanations, changes over time, treatment trade-offs and evidence that changes a decision. Avoid giving the intended conclusion away in the patient's question. Balance difficult problems with appropriate restraint; “always escalate” should not be a shortcut to a high score.

For each new family, deliver an original bilingual conversation, stage-specific expected behaviors, acceptable alternatives, proposed critical errors, reference answers with controlled omissions, and a source-to-requirement map. Published actual cases can supply mechanisms and decision sequences; they do not automatically validate the synthetic answer key. Record source limits and unresolved clinical or language questions when authoring, and keep patient identifiers and source images out of public drafts.

Before a new batch is used in an experiment, check identity and source overlap with development and reserved sets, verify case-to-label hashes, and freeze its own inputs. Do not alter the completed panel or fit labels to produce lower-tier 60–70, average around 80 or premium around 90. Those remain diagnostic aspirations. Expert clinical and bilingual review stays deferred, not waived.

The catalog's structural tests cover counts, duplicate IDs/files, paired languages and public-path boundaries. It does not assess medical correctness, measured difficulty or release readiness.

## Completed four-family expansion

[S59 / Batch Q](S59_BATCH_Q_CASE_EXPANSION_EN.md) adds IV-iron-associated phosphate depletion, an inflammatory postoperative wound/infection differential, uncertain hypercalcemia before surgery, and new bleeding despite immediate mixing correction. It delivers eight bilingual conversations, 28 mapped requirement positions, eight initial references and 24 strong/partial/unsafe update examples.

The two leads previously listed here are now complete draft packages alongside two additional public-report-inspired mechanisms. [Cases](../data/multiturn/batch_q_cases.json), [anchors](../config/multiturn_criterion_anchors_batch_q_v1.json), [reference answers](../data/multiturn/batch_q_contrasts_v1.json) and [source mappings](../data/multiturn/batch_q_provenance.json) remain separate from the default registry. H149–H152 track expert questions. No new score or demonstrated difficulty is claimed.

`python3 -m scripts.audit_batch_q` checks the structural/source bindings and visible report-identifier overlap with public development and reserved cases. Manual related-family grouping remains necessary. S60's selected input manifest uses the S52-derived O revision, whereas this catalog continues to point to the original authoring files; neither counts as a new family. Execution settings, gates, current cost evidence and separate paid-call approval are still needed. S58 cannot be reopened using these drafts.
