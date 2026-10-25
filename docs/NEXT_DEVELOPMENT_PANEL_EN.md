# Next development panel: prepared, not authorized for live execution

This is a planning handoff after the S45/S46 workflow pilot, not another paid run or permission to use an earlier experiment's remaining allowance. The immediate prerequisite is a completed control gate and an audit of any missing or rejected judgments. A failing gate must be investigated without weakening acceptance rules just to obtain scores.

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

Reuse the exact 16 S45/S46 saved candidate turns if all case, prompt, model and response bindings remain compatible; obtain only the other 128. This requires a **new mixed import/generation scheduler**: the frozen S45 runner supports whole-bank judge-only import or new generation, and S46 is deliberately restricted to one fixed suffix. Neither currently implements this broader mixed panel. Add offline tests for exact-bank provenance, no duplicate calls, follow-up history, fixed denominators and inherited cost tracking before freezing a new experiment.

A proposed complete schedule is 128 new candidate turns + 36 judge controls + 144 first-pass stage judgments + 144 repeated stage judgments = **452 new requests**. This is a request-count proposal, not a budget or live authorization. Rejudge the one-family pilot answers under the new panel's declared judging protocol; retain pilot scores separately. Run repeats against identical saved packets and report them separately rather than averaging away disagreement. Set the new spending policy and obtain a fresh bounded authorization before any calls.

## What the readout must answer

1. Which models/cells completed, and were failures transport, format, evidence or scoring uncertainty? Keep all 72 expected conversation cells in the denominator; do not substitute zero for missing clinical scores.
2. What are the first-pass scores by model, language and design stratum, perfect-score frequency, critical errors and criterion-level deductions? Do the intended conflict cases actually discriminate?
3. How often do identical-packet repeats change criterion status, point score, uncertainty interval or provisional pass status? Inspect the changed evidence rather than only a global mean.
4. Do both English and Chinese answers follow the requested language, and where do paired results diverge? Language quality and clinical equivalence still need later independent review.

The desired lower-tier 60–70, average around 80 and premium around 90 remain diagnostics. Do not relabel model tiers after seeing scores, add arbitrary penalties or choose cases to force these bands. A four-model mean is not the original six-model roster mean; Gemini self-judging remains a limitation.

## Case expansion alongside testing

[Batch O](BATCH_O_STANDALONE_EN.md) supplies two harder public-report-informed drafts, with exact-case anchors and strong/partial/unsafe answer examples. They stay outside this fixed nine-family panel and the registered 125/250 portfolio until explicitly integrated into a new version. Next inspect acceptable alternatives, bundled requirements and EN/ZH equivalence, then test their authored contrasts in a separately declared development batch. Expert review remains deferred, never waived for release. Xi'an remains local and is not yet a cleared test case.
