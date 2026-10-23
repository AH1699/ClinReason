# Full score integration test

## Decision and scope

This fresh development experiment checks whether the S27 anchor clarification works inside the complete criterion-derived scoring pipeline. It uses the original S26 two-family controls (`TRIAGE-018` red eye and `TRIAGE-020` resolving sore throat), not new candidate answers. S26 and S27 remain separate historical experiments. This protocol and all executable inputs will be committed before calls.

The only substantive scoring-input change from S26 is the S27 definition of the red-eye update's second requirement. The original transcripts, judge instruction, criterion credits (1 / 0.5 / 0), stage weights (30% initial / 70% update), named error rules and provisional 70 threshold stay fixed. Independent safety/revision observations remain review flags, not additional numerical deductions. An unclear criterion yields an interval, no point score and no provisional pass. Default project scoring is unchanged.

## Calls and preservation

- Two families × two languages × three authored answer profiles × two judges = **24 first judgments**.
- Repeat the four partial-answer packets with both judges = **8 repeats**, maximum **32 total**, zero candidate calls.
- Judges: Gemini `gemini-3.8-flash`, Grok `grok-4.7`; provider-default sampling, 120-second request timeout, zero automatic retries.
- Keep S26's deterministic key order, first stage then repeats. Profile names and expected errors stay outside judge-visible packets.
- Freeze source/dependency and packet hashes in `config/scoring_s28_frozen_v1.json`. Record each attempt before sending and raw response before validation. Stop on the first transport, output-validation or model-drift failure; do not resume, repair responses or pool other runs.
- Raw responses stay in ignored `work/`; publish only verified descriptive results and hashes. Audit exact scheduled prefixes, attempts, raw responses, returned model IDs and recalculated scores.

## Fixed decision rule

The gate requires all 32 valid judgments, all eight expected unsafe errors detected, strict point-score ordering **strong > partial > unsafe** in all eight family/language/judge groups, all eight repeated criterion/error vectors and point scores matching, and no unresolved independent safety/revision concern on strong/partial controls. Do not replace point ordering with interval ordering after observing results. A failure is a diagnostic finding, not a reason to change the rule or retry until it passes.

A pass permits only design of a separately bounded small candidate pilot, not a validated ranking or deployment. Clear authored controls do not establish real-model performance. The preferred lower ~60–70 / average ~80 / premium ~90 distribution remains an aspiration, not a fitting target. Expert clinical, bilingual and methodology review remains deferred and required for external comparative claims.

## Reproduce

Offline: `python3 -m benchmark.scoring_s28 plan`.

Live after the freeze commit: `python3 -m benchmark.scoring_s28 run --output work/s28_full_score_2026-10-23 --max-calls 32`.

Read-only result audit: `python3 -m benchmark.scoring_s28 audit --output work/s28_full_score_2026-10-23`.
