# Next development panel: prepared, not authorized for live execution

This is a planning handoff after the S45/S46 workflow pilot, not another paid run or permission to use an earlier experiment's remaining allowance. The immediate prerequisite is a completed control gate and an audit of any missing or rejected judgments. A failing gate must be investigated without weakening acceptance rules just to obtain scores.

Current checkpoint: [S52's durable offline journal and read-only replay are implemented](S52_DURABLE_REPLAY_AND_WORDING_EN.md). All 16 saved stages are verified for import; 128 generation jobs and all 72 conversation cells are retained. No live transport/run command exists. [S50](S50_MEDICATION_BOUNDARY_RESULT_EN.md) remains closed with 16/16 author matches but 27/28 repeats and a failed gate. S48/S49 scores remain unchanged. Keep `MEDSAFE-013` review-held, with no silent exclusion or reweighting. Next settle the uniform judging and held-item policy, then implement and mock-test a separately versioned live integration. Before paid comparison, reverify prices, freeze the new protocol and obtain fresh bounded approval. Batch O's 18 new controls remain separate author drafts outside this panel.

## Fixed case selection

Keep the existing S38 selection; do not select replacements after seeing candidate scores.

| Author-defined design stratum | Existing families | Intended distinction |
|---|---|---|
| Routine / de-escalation | TRIAGE-019, TRIAGE-020, REASON-015 | Avoid reflexively escalating or treating when stated exceptions are excluded |
| Conditional interpretation | REASON-014, MEDSAFE-013, MEDSAFE-014 | Change interpretation or management when medication, timing or new symptoms alter the decision |
| Conflicting evidence | REASON-020, REASON-022, MEDSAFE-019 | Reconcile reassuring tests with limitations or clinical deterioration |

All IDs have the `HC-MT-` prefix. These are author-defined strata, not empirically proven easy/medium/hard levels. The 3/3/3 balance is **by reasoning design**, not clinical domain: the panel contains two triage, three medication-safety and four reasoning families.

## Proposed execution and implementation prerequisite

Use the same four working Gemini/MiniMax candidates and Gemini 3.8 Flash judge for a provisional continuity panel; leave Grok unavailable rather than assigning it a clinical zero. Preserve both languages and two turns: **72 conversations / 144 candidate turns** across nine families.

S51 verified the exact 16 S45/S46 saved candidate turns against raw captures and current candidate-request bindings; only the other 128 are generation jobs. Its mixed scheduler is separate from frozen S45 (whole-bank import or all-new generation) and S46 (one fixed suffix). S52 adds durable offline capture/replay. Tests cover exact-bank compatibility, no duplicate generation, follow-up history, fixed denominators, interruption and inherited usage/stop handling. A live transport integration, future judging contract and fresh protocol freeze remain prerequisites to execution.

A proposed complete schedule is 128 new candidate turns + 36 judge controls + 144 first-pass stage judgments + 144 repeated stage judgments = **452 new requests**. This is a request-count proposal, not a budget or live authorization. Rejudge the one-family pilot answers under the new panel's declared judging protocol; retain pilot scores separately. Run repeats against identical saved packets and report them separately rather than averaging away disagreement. Set the new spending policy and obtain a fresh bounded authorization before any calls.

## Offline implementation status and remaining engineering

The new [S51 module](../scripts/mixed_panel_s51.py) leaves frozen S45/S46 and their banks untouched. These four offline checks are implemented:

1. Build the complete 72-conversation manifest first. Bind each of the 16 imported stages to its saved request, raw response, model identity, case version and answer hash. Reject incompatible or duplicate imports instead of quietly regenerating them.
2. Produce a dry-run schedule with exactly 128 generation jobs. Each update uses its own verified initial answer and matching user follow-up; no missing initial stage may be replaced with a different model's answer.
3. Add the 36 controls, 144 first judgments and 144 identical-payload repeats. Test missing-stage handling, closed provider lanes, unknown usage, stop thresholds and no dispatch after a stop. Keep all 72 conversation cells in reporting, including missing and review-held ones.
4. Export an offline readiness report. Before a live freeze, declare one judging policy for the panel, the treatment of disputed medication criteria and a new budget. The proposed 452-request schedule is still not authorized.

S52 now journals reservations, payloads, supplied response bytes, receipts, accounting and results around S51. Read-only replay reconstructs a complete fixture run and interrupted tails without reopening the writer. It does not test actual HTTP delivery. Next implement and mock-test a separate live integration after declaring the uniform judging/held-item contract; then freeze its inputs. The medication-label decision and fresh paid authorization remain separate.

## What the readout must answer

1. Which models/cells completed, and were failures transport, format, evidence or scoring uncertainty? Keep all 72 expected conversation cells in the denominator; do not substitute zero for missing clinical scores.
2. What are the first-pass scores by model, language and design stratum, perfect-score frequency, critical errors and criterion-level deductions? Do the intended conflict cases actually discriminate?
3. How often do identical-packet repeats change criterion status, point score, uncertainty interval or provisional pass status? Inspect the changed evidence rather than only a global mean.
4. Do both English and Chinese answers follow the requested language, and where do paired results diverge? Language quality and clinical equivalence still need later independent review.

The desired lower-tier 60–70, average around 80 and premium around 90 remain diagnostics. Do not relabel model tiers after seeing scores, add arbitrary penalties or choose cases to force these bands. A four-model mean is not the original six-model roster mean; Gemini self-judging remains a limitation.

## Case expansion alongside testing

[Batch O](BATCH_O_STANDALONE_EN.md) supplies two intended harder public-report-informed drafts, with exact-case anchors and strong/partial/unsafe answer examples. They stay outside this fixed panel and the registered 125/250 portfolio. S52 adds a separate wording draft and 18 bilingual controls for H142/H143; both issues remain open for human review. Next finish controls for the ten other criterion positions, then select a distinct new coverage mechanism. Intended difficulty is still unmeasured. Expert review remains deferred, never waived for release; Xi'an remains local and uncleared for testing.
