# Nine family panel scope and reporting rules

**Current work:** [S67](S67_COMPACT_FEASIBILITY_RESULT_EN.md) closed the approved 16-request batch at $0.145569 estimated cost: all references and MiniMax turns completed, but five of six repeat vectors match and six of 58 reviewed entries remain held. Next is bounded offline semantic/evidence work, not another provider diagnostic. Broader confirmation requires a fixed prospective scope and new approval; the $3 permission is consumed. No total score or historical rescore. Inventory is 135 draft families. The nine-family S55 scope below is historical, not permission to rerun.

The owner approved one execution of this fixed panel, recorded in [S55](S55_MIXED_PANEL_RUN_EN.md). This document grants no repeat execution or use of an earlier experiment's unused allowance. The declared control gate still governs development judgments. Failed controls remain recorded; do not weaken acceptance rules to obtain scores. S50 is closed with the medication item held, not an automatic prerequisite for another single-item diagnostic.

Recorded S55 outcome: the approved execution closed after **264 requests / $1.990560 estimated cost**, below its $20 stop threshold. Generation and the control gate completed, but a required-quote failure closed the judge lane after 99 accepted first-stage judgments. There are 49 complete first pairs and no candidate repeats. All 16 imports and 72 cells remain. Eight medication cells are raw diagnostics only; no pooled means or rankings. See [S55](S55_MIXED_PANEL_RUN_EN.md) for the report and stop diagnosis. This consumed approval cannot authorize a restart. The fixed scope below records that run, not a new authorization.

## Fixed case selection

Keep the existing S38 selection; do not select replacements after seeing candidate scores.

| Author-defined design stratum | Existing families | Intended distinction |
|---|---|---|
| Routine / de-escalation | TRIAGE-019, TRIAGE-020, REASON-015 | Avoid reflexively escalating or treating when stated exceptions are excluded |
| Conditional interpretation | REASON-014, MEDSAFE-013, MEDSAFE-014 | Change interpretation or management when medication, timing or new symptoms alter the decision |
| Conflicting evidence | REASON-020, REASON-022, MEDSAFE-019 | Reconcile reassuring tests with limitations or clinical deterioration |

All IDs have the `HC-MT-` prefix. These are author-defined strata, not empirically proven easy/medium/hard levels. The 3/3/3 balance is **by reasoning design**, not clinical domain: the panel contains two triage, three medication-safety and four reasoning families.

## Fixed execution scope

Use the same four working Gemini/MiniMax candidates and Gemini 3.8 Flash judge for a provisional continuity panel; leave Grok unavailable rather than assigning it a clinical zero. Preserve both languages and two turns: **72 conversations / 144 candidate turns** across nine families.

S51 verified the exact 16 saved stages; only the other 128 are generation jobs. S52/S53 provide the offline journal/transport baseline, while S54 supplies separately versioned live-labelled journals, replay and approval consumption. Compatibility, no duplicate generation, follow-up history, fixed denominators, interruption and spending stops are tested. The approved protocol and fresh owner permission—not an old allowance—will govern any paid execution.

The approved maximum is 128 new candidate turns + 36 judge controls + 144 first-pass stage judgments + 144 repeated stage judgments = **452 new requests**. This is a request limit, not a promise of completion. Rejudge the one-family pilot answers under the panel's declared judging protocol; retain pilot scores separately. Run repeats against identical saved packets and report them separately rather than averaging away disagreement. The owner's $20 threshold applies only to the single recorded S55 execution.

## Offline implementation status and remaining engineering

The new [S51 module](../scripts/mixed_panel_s51.py) leaves frozen S45/S46 and their banks untouched. These four offline checks are implemented:

1. Build the complete 72-conversation manifest first. Bind each of the 16 imported stages to its saved request, raw response, model identity, case version and answer hash. Reject incompatible or duplicate imports instead of quietly regenerating them.
2. Produce a dry-run schedule with exactly 128 generation jobs. Each update uses its own verified initial answer and matching user follow-up; no missing initial stage may be replaced with a different model's answer.
3. Add the 36 controls, 144 first judgments and 144 identical-payload repeats. Test missing-stage handling, closed provider lanes, unknown usage, stop thresholds and no dispatch after a stop. Keep all 72 conversation cells in reporting, including missing and review-held ones.
4. Export an offline readiness report. S54 now binds the uniform judging policy, treatment of disputed medication criteria and spending threshold. The one live execution was separately approved; readiness alone never authorizes another run.

S54 retains S53's uniform 32,768/medium S47 judging and reporting policy. Its live CLI consumes a protocol/run-bound approval before reading credentials and uses the existing verified-TLS transport; tests inject simulated connections. HTTP failures are never passed to the answer parser. Approval expiry, source changes, unknown cost and spending stops prevent further dispatch. Read-only replay does not permit retry or resume. No numeric scoring rule or historical result changes.

## What the readout must answer

1. Which models/cells completed, and were failures transport, format, evidence or scoring uncertainty? Keep all 72 expected conversation cells in the denominator; do not substitute zero for missing clinical scores.
2. What are the first-pass scores by model, language and design stratum, perfect-score frequency, critical errors and criterion-level deductions? Do the intended conflict cases actually discriminate?
3. How often do identical-packet repeats change criterion status, point score, uncertainty interval or provisional pass status? Inspect the changed evidence rather than only a global mean.
4. Do both English and Chinese answers follow the requested language, and where do paired results diverge? Language quality and clinical equivalence still need later independent review.

The desired lower-tier 60–70, average around 80 and premium around 90 remain diagnostics. Do not relabel model tiers after seeing scores, add arbitrary penalties or choose cases to force these bands. A four-model mean is not the original six-model roster mean; Gemini self-judging remains a limitation.

## Case expansion alongside testing

[Batch O](BATCH_O_STANDALONE_EN.md) retains its complete structural controls and open H142/H143/H144 questions. [Batch P](S54_LIVE_ADMISSION_AND_BATCH_P_EN.md) adds two distinct families on platelet specimen validity and routine blood-pressure surveillance, with references and source mappings. O/P total four standalone families outside this panel and the registered 125/250 portfolio. Continue new mechanisms toward 500 families; difficulty is still unmeasured. Expert review stays later but required, and Xi'an remains local and uncleared for testing.
