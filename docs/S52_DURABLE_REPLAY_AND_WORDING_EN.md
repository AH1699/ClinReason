# Durable offline replay and Batch O scoring drafts

The nine-family workflow now has a disk-backed **offline** journal and read-only replay. Batch O also has a separate wording draft with **18 bilingual control packets** for two scoring questions. No provider calls, new model scores or newly registered families were added. Historical experiments and the original Batch O files remain unchanged.

## What the journal verifies

[The journal](../scripts/mixed_capture_s52.py) wraps the existing mixed scheduler. It creates a fresh private directory, binds the inputs and imported answers, records the request reservation and exact payload, then saves supplied response bytes before interpreting them. It retains accounting and acceptance/rejection results separately. A write or parsing failure stops that writer; there is no reopen, retry or resume method.

The complete fixture exercise covers the fixed **452 proposed requests**: 128 new candidate stages, 36 controls, 144 first judgments and 144 exact-payload repeats. All **72 conversations / 144 answer stages** remain visible, including eight medication conversations held from comparative claims. Sixteen saved stages are imported rather than regenerated. These counts describe a simulated workflow, not newly obtained model answers.

Replay reconstructs requests, skipped jobs, answers, judgments, accounting and stop decisions from the saved bytes, then compares them with the recorded results. It rejects changed payloads, context or raw-byte bindings, gaps, unexpected files, linked captures and events after a stop. It uses the same frozen scheduler/decoders; it is an independent reading of the journal, **not an independent clinical scorer**.

An incomplete final entry cannot authorize continuation:

- A reservation without a complete response receipt stays visibly unresolved. Raw bytes without that receipt might be partial and are not interpreted.
- A complete receipt without a saved result can be reconstructed for inspection. Replay does not write the missing result or restart work.
- Unknown simulated accounting stops the whole panel. A known-cost invalid response closes its model lane; missing results remain missing, not zero scores. The simulated spending threshold permits a final-request overrun.

Fixture imports are explicitly labelled unverified. The optional saved-bank path instead reconstructs the actual S45/S46 captures and checks the pinned provenance before creation and again during replay. That path was checked locally with one supplied fixture response; no original answer or raw provider reasoning was published.

This is not a live transport. It accepts supplied bytes only, does not load credentials, and does not test HTTP delivery, socket timeouts or network response truncation. Those require a separately versioned live adapter and mock-transport tests. Its simulated threshold is neither a new spending authorization nor a verified hard ceiling.

## What changed in the separate Batch O draft

[The draft](../data/audit/batch_o_wording_controls_s52.json) changes only update criterion 3 in each of the two standalone families. [Its materializer](../scripts/batch_o_wording_s52.py) constructs derived case views at version 0.2.0, with new content hashes and matching anchors. User prompts, other requirements, critical errors and original files stay intact. The derived views are not registered in the default dataset or the nine-family panel.

| Author decision | Controls in each language | Provisional focus-criterion expectation |
|---|---|---|
| Heart-failure warnings cover three domains: perfusion/mental status, urine and breathing. Named symptoms within a domain are examples, not a required word list. | Baseline; omit confusion only; omit breathing; omit urine | met; met; partial; partial |
| No family-administered replacement regimen is an absence condition, not a mandatory disclaimer. Reassessment and explicit limits on both feeding extremes remain positive requirements. | Baseline; omit dosing disclaimer; assessed monitored continuation; conditional temporary hold with reassessment/recovery; omit explicit indefinite-starvation limit | met; met; met; met; partial |

These are **author hypotheses under the new draft**, not clinical truth or observations of a judge. In particular, whether the proposed symptom grouping is adequate, and whether an implied feeding limit should count without explicit wording, remain review questions. H142/H143 stay open. Continuation and temporary interruption are conditional alternatives, not treatment recommendations for a real patient.

All 18 packets keep the original initial answer and the first two update components. Only the third component varies. Author expectations and construction metadata are outside the blinded judge packets. Counts do not increase the case inventory. Ten other Batch O criterion positions still need their planned component/alternative controls.

## Next work

1. Set the prospective uniform judging contract and explicit handling of the held medication item. Then implement and mock-test a separate live transport integration. Preserve all panel cells; do not reuse an old approval or retrospectively repair scores.
2. Complete the ten remaining Batch O control positions, then author distinct public-report/Step-2-informed cases for the coverage gaps. Newly interpreted requirements need later source-to-answer and bilingual review.
3. Before sending anything to providers, verify current prices, freeze the new protocol and obtain fresh bounded approval. The 452-request proposal still has no approved budget. No further single-medication diagnostic is scheduled.

Registered coverage remains **125 families / 250 variants**, plus two standalone Batch O families; approved calibration/Gold remains **0/0**. The longer-term target is at least **500 distinct families**. Expert review remains later, Xi'an stays local, and 60–70 / about 80 / about 90 remain diagnostic aspirations, never score-fitting targets.

Verification: **905 offline tests pass**, including 30 new journal/wording tests. S51's saved readiness snapshot still recomputes exactly with private-source verification; original Batch O hashes and historical freezes pass their audits. The 18 new packet hashes are reproducible with the wording audit below.

Offline commands:

```sh
python3 -m unittest tests.test_mixed_capture_s52 tests.test_batch_o_wording_s52 -q
python3 -m scripts.batch_o_wording_s52
python3 -m scripts.mixed_capture_s52 replay /absolute/path/to/local/journal
```

The replay command accepts an existing S52 journal only and never resumes it. There is no live-run command. Capture files, imports and response text belong in ignored local storage, not GitHub.
