# S30 result: focused boundaries passed; full-score testing is next

## What completed

After specific owner approval, the frozen S30 experiment completed **24/24 valid judge calls**: 20 first assessments and four exact-packet repeats. Gemini `gemini-3.8-flash` and Grok `grok-4.7` each made 12 calls. There were no retries, candidate calls, transport stops or model-name mismatches. No frozen input changed during execution.

The read-only saved-result audit confirms **32/32 known first criterion decisions matched the predeclared author hypotheses** and **8/8 repeated criterion decisions matched their first assessment**. The predeclared gate passes. This permits designing a separate full-score/repeat experiment; it does **not** establish clinical correctness, total-score calibration, a model ranking or permission for further paid calls.

The public [machine-readable summary](../data/audit/s30_boundary_summary.json) records every cell, model, latency and response fingerprint. The [pre-run protocol](S30_BOUNDARY_PROTOCOL_AND_N_CONTROLS_2026-10-23_EN.md) was committed as `7158f17`, with fingerprint `23161d0b53e3cb3604ee4d2e294bda4284f7c765e881702e3a91d7676b5de4f6`. Raw provider responses and judgment rationales remain in ignored local `work/s30_boundary_2026-10-23/`.

## What the judges classified

This is one synthetic sinus-symptom family, five authored answer profiles, two languages and two judges—not a 24-case benchmark. Only update requirements 1 and 3 were assessed: an explicit link between the improving course and the antibiotic decision, and an action-linked future safety net.

| Authored profile | Predeclared hypothesis, requirements 1 / 3 | Observed in both languages and both judges |
|---|---|---|
| Complete | `met / met` | `met / met` |
| Observed partial | `met / missed` | `met / missed` |
| Unlinked reasoning, generic action warning | `partial / partial` | `partial / partial` |
| Contradictory advice | `missed / missed` | `missed / missed` |
| Ambiguous reference to earlier advice | None; exploratory | `partial / missed` |

The first four rows supply 32 known decisions. The last row supplies eight exploratory decisions across four judgments; it remains without an expected label. Only the observed-partial profile was repeated, giving eight repeated criterion decisions. Repeat equality concerns status labels, not byte-identical rationales, general reliability or all five profiles.

The exploratory rationales consistently treated a vague reference to the previous plan as insufficient under the instructed update-local rule. That is evidence of following this rule, not evidence that the rule is clinically preferable to assessing the whole conversation. H117 remains open. No numerical score was computed; in particular, this result must not be converted into a claimed repair of S29's 65-versus-abstention result.

## Next execution plan

1. **Prepare a new full-score integration protocol offline.** Use the existing red-eye and sinus families, English and Chinese, and safe/partial/unsafe controls. Proposed size: 24 first judgments plus eight exact partial-answer repeats, at most 32 calls. Retain the S28 arithmetic, critical-error rules and pass threshold; integrate only the separately versioned S30 sinus boundaries alongside the existing red-eye boundary. Do not edit S26–S30 inputs or recompute their results.
2. **Freeze and test before asking to run.** Bind cases, answers, complete anchors, judge instruction, output schema, schedule and scoring code. Carry forward the prospective 240-second socket timeout, secret-safe transport observation, exact model check, zero retries and stop-on-first-error policy. Predeclare full-panel completion, unsafe-error detection, strict safe > partial > unsafe point ordering in all eight groups, exact partial criterion/error-vector and score repeats, and no unresolved independent safety/revision concerns on safe or partial controls. An unclear interval cannot satisfy point ordering. This proposed panel is not yet implemented, frozen or authorized.
3. **Keep expansion and local source processing separate.** Select a bounded L/M/N control pilot after specifying its own evidence and call plan. Batch N already has seven draft anchors, two shared initial answers and six update controls, but no live judgments. Continue Xi'an decision-time verification locally; owner-confirmed encounter grouping does not establish when results became available or clear the records for export.

Even a future full-score gate pass would support only a separately specified development candidate pilot. Independent clinical and bilingual review remains deferred, not waived. Lower-tier ~60–70, average ~80 and premium ~90 remain documented aspirations for discrimination, never fitted targets.

## Checks and unchanged scope

The saved-result audit verifies the frozen manifest and acknowledgment, contiguous request order, raw-response-to-judgment binding, literal answer evidence, exact returned model identity, timing fields and completion marker. **312 offline tests pass**; S26–S30 manifest checks, the batch-N packet audit and portfolio isolation checks pass.

Public development remains **125 families / 250 variants** (32 Alpha, 51 patient two-turn, 42 professional). Approved calibration and hidden Gold remain **0/0**. No new case, default scoring rule or clinical approval was added. Xi'an status is unchanged: private one-encounter material, no case-ready or privacy-cleared record. No Xi'an record or purchased source file was sent to either judge or included in this public result.

Read-only reproduction of the local audit:

```sh
python3 -m benchmark.boundary_s30 audit --output work/s30_boundary_2026-10-23
python3 -m benchmark.batch_n_packet_audit
python3 -m benchmark.portfolio_audit
python3 -m unittest discover -s tests
```

The first command requires the private local run files. The public summary is not a replacement for those raw files and is not itself independently reproducible evidence of provider behavior.
