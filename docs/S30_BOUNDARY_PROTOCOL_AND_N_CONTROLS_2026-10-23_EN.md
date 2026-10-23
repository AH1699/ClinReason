# Focused scoring boundary protocol and new answer controls

## Post-run status — 2026-10-23

After specific approval, S30 completed 24/24 valid calls, 32/32 known first criterion matches and 8/8 repeated matches. The focused gate passed; full-score calibration remains incomplete. See the [audited result and next plan](S30_BOUNDARY_RESULT_2026-10-23_EN.md). The remaining text preserves the prospective protocol and its pre-run checkpoint; it is not a request or permission to run S30 again.

## Historical pre-run status: ready for approval

The S30 runner, judge instruction, response schema, cases, answers, anchors and request order are now frozen for a **maximum of 24 judge calls**. No S30 live request has been made. This is the next bounded experiment after S29, not an extension of its two-call approval.

The experiment asks whether Gemini 3.8 Flash and Grok 4.7 apply two clarified boundaries consistently to the existing synthetic sinus-symptom case. It does not generate candidate answers, award total scores or change the default scoring rules. The earlier [S29 result](S29_RESULT_S30_BOUNDARIES_STEP2_2026-10-23_EN.md) remains unchanged: two successful calls, one point score of 65 and one abstention on unclear criteria.

## What would be sent and counted

Each provider would receive the synthetic English or Chinese two-turn conversation, one authored answer, two target requirements with their draft anchors, general level definitions and the judge instruction. Author profile names, expected labels, earlier judge results and desired score bands are excluded. No Step 2 raw asset, Xi'an record, personal data or credential is included in the judge content. API credentials authenticate requests, and usage may be billed by each provider.

| Phase | Material | Requests | Criterion decisions |
|---|---|---:|---:|
| First assessment | Five answers × two languages × two judges | 20 | 40 |
| Repeat | Exact observed-partial answer × two languages × two judges | 4 | 8 |
| Maximum | No retries or candidate calls | 24 | 48 |

Four answer profiles have author hypotheses: complete, observed partial, unlinked reasoning with a generic warning, and contradictory advice. The ambiguous reference to earlier advice has no expected status. That gives **32 known first-pass criterion decisions**, **8 exploratory decisions** and **8 repeat decisions**. These are not independent patient cases or expert-approved labels.

Packets are ordered by their content hash, with Gemini then Grok for each packet. All first assessments precede the selected repeats. The same packet and instruction are used on repeat; phase names and profile identifiers are not sent. Each request uses a prospective 240-second socket timeout and provider-default sampling. This is not a guaranteed total deadline or exact determinism.

## Rules fixed before calling

The output must contain exactly two criterion assessments in order, requirements 1 and 3. Each needs a status and rationale. `met` or `partial` requires a literal quote from the update answer; any nonempty evidence must also come from that answer. Earlier advice can supply context but cannot silently fill an update omission under this experimental construct. Whether that construct is clinically appropriate remains H117, not something AI agreement settles.

The run stops at its first transport error, invalid response or unexpected returned model name. An `unclear` classification is a valid judgment, not a transport error. A disagreement with the author hypothesis is retained and does not trigger early stopping, repair or extra sampling. Attempts are recorded before sending; provider JSON is saved before judgment validation. Logs allow only bounded diagnostic fields, not secret-bearing error text. Raw results stay in ignored `work/`.

The advance gate requires all 24 valid judgments, **32/32** known classifications matching the predeclared hypotheses, and **8/8** repeated classifications matching their first assessment. Exploratory classifications are reported separately and never given a post-hoc expected label. Passing permits designing a separately frozen full-scoring/repeat panel, not automatically running one or claiming clinical calibration. Failure leaves the comparison hold in place; a future revision must get a new version, not reuse this call allowance.

## Reproducibility and execution

[The manifest](../config/s30_boundary_frozen_v1.json) binds 30 files, ten judge packets, the request schedule and response schema. Its protocol fingerprint is:

```text
23161d0b53e3cb3604ee4d2e294bda4284f7c765e881702e3a91d7676b5de4f6
```

Read-only checks:

```sh
python3 -m benchmark.boundary_s30 plan
python3 -m benchmark.batch_n_packet_audit
python3 -m unittest discover -s tests
```

Only after specific owner approval of the external transfer and call cap, and after committing the frozen protocol, run once in a fresh local directory:

```sh
python3 -m benchmark.boundary_s30 run --output work/s30_boundary_2026-10-23 --max-calls 24 --approved-protocol-sha256 23161d0b53e3cb3604ee4d2e294bda4284f7c765e881702e3a91d7676b5de4f6
python3 -m benchmark.boundary_s30 audit --output work/s30_boundary_2026-10-23
```

The acknowledgment flag binds the intended protocol; it does not independently establish owner consent. Missing or wrong acknowledgment, a different call cap or an existing output directory fails before loading keys or sending. A stopped or interrupted run cannot be resumed. The older `boundary_s30_draft` command describes the original offline draft only; use `boundary_s30 plan` for the frozen runner's readiness.

## Batch N answer controls completed offline

The existing salicylate family now has [seven draft anchors](../config/multiturn_criterion_anchors_batch_n_v1.json), two shared initial answers and [six update controls](../data/multiturn/batch_n_contrasts_v1.json). Partial answers remove only the specialist/removal-assessment component; omission alone is not the named severity-3 discharge error. Unsafe answers replace all four linked components, so they do not retain contradictory immediate-escalation advice. Text-edit counts do not establish isolated effects on clinical scoring.

The [seven-position source ledger](../data/multiturn/batch_n_provenance.json) and original case remain unchanged. EXTRIP supports considering serious clinical features independently of a high concentration; the exact credit levels, acceptable wording and proposed errors are author choices needing later review. [EXTRIP recommendations](https://www.extrip-workgroup.org/salicylates). Exposure and acid-base background remain supported by the [Merck professional reference](https://www.merckmanuals.com/professional/injuries-poisoning/poisoning/aspirin-and-other-salicylate-poisoning).

The offline audit checks case hashes, source positions, paired edits, configured error IDs and six distinct packets without author-control metadata. It does not judge the answers. These controls are not part of S30 and have no approved live pilot yet.

## Current checkpoint and next work

**312 tests pass**, including 18 new tests. S26–S29 frozen inputs remain unchanged; S30's freeze and portfolio/source-isolation checks pass. Public development remains **125 families / 250 variants**; approved calibration and hidden Gold remain **0/0**. Xi'an remains local-only, with no newly cleared facts or case in this checkpoint.

Next is the specific S30 external-call decision. After an approved run, audit all saved results before considering the full-scoring panel. Separately, select a small L/M/N answer-control pilot and continue local Xi'an decision-time verification. Reviewer items H116–H120 remain open. Expert review stays deferred; lower ~60–70, average ~80 and premium ~90 remain aspirations, not fitted scores.
