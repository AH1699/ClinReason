# Explicit evidence requirements and saved answers for judge only testing

The next scoring experiment can reuse **all 144 saved answer stages across 72 conversations**. The offline preparation now gives the judge an explicit quote rule for every criterion and status, and verifies each saved answer against its original request and response. **No new provider calls or scores were produced.** The new instructions have not yet been tested by a live judge.

## What changes and what stays fixed

The [new instruction module](../scripts/judge_evidence_s56.py) computes a table for each judgment. For every criterion it lists whether `met`, `partial`, `missed` or `unclear` needs a nonblank quote and whether the quote must come from the initial or update answer. The same table appears in the response-schema field description. The schema shape is unchanged; the local validator remains authoritative.

| Criterion status | Existing rule now made explicit |
|---|---|
| met | Nonblank matching-stage quote, except the existing literal `Does not ` / `Avoids ` anchor prefixes |
| partial | Nonblank matching-stage quote, including avoidance requirements |
| missed or unclear | Empty quote permitted; rationale still required |
| Any nonempty quote | One contiguous allowed assistant span under the existing normalization; never user text, stitched passages or a paraphrase |

The `Do not ` anchor that stopped [S55](S55_MIXED_PANEL_RUN_EN.md) still requires a quote for `met`. The failed reply is not repaired or accepted. Observation quotes retain their separate permission to use either visible assistant turn, while overlap explanations and the revision's new fact remain mandatory. Case labels, weights, error caps, pass threshold and S36 validation are unchanged. An evidence-format rule does not establish the clinically correct status; H147 remains open.

## Saved answer verification

The [bank verifier](../scripts/judge_saved_bank_s56.py) reads the sealed source without changing it. It checks the frozen S54 implementation and a hash of all **2,379 source files**, replays the journal, and revalidates the upstream S45/S46 provenance for the 16 historical imports. The other 128 stages are decoded again from accepted raw candidate replies. Each stage retains its family, language, candidate model, stage, case version, case hash, answer hash, request hash, response hash and source origin. Every update request is reconstructed with that same model's initial answer.

The private bank is `work/s56-banks/panel-answer-bank.json`. It contains final answers, not provider reasoning, and stays ignored by Git alongside credentials and raw captures. The [public readiness record](../data/audit/s56_saved_bank_readiness.json) contains only identifiers, counts and hashes. It does not publish answers, quote text, judge explanations or numeric scores. A self-consistent bank hash alone is insufficient: verification rechecks the raw source.

To reproduce the read-only check locally:

```sh
python3 -m scripts.judge_saved_bank_s56 --verify-bank work/s56-banks/panel-answer-bank.json
```

This command prints public metadata and has no live execution, credential-loading or network path. It requires the existing private source records; a public checkout alone cannot reproduce private answer provenance.

## Proposed next experiment

| Phase | Requests | Purpose |
|---|---:|---|
| Fresh judge controls | 36 | Check the revised instructions against the unchanged control gate |
| First candidate judgments | 144 | Score both stages of all 72 saved conversations uniformly |
| Repeated candidate judgments | 144 | Rejudge identical payloads and report repeat stability separately |
| Total proposed maximum | 324 | No new candidate generation |

The judge remains Gemini 3.8 Flash with the existing 32,768-token output setting, medium thinking and unpinned provider sampling defaults. This setting is not a verified spending ceiling. Candidate answers still cover both Gemini versions and both MiniMax versions. Grok stays out of this continuity panel; its absence is not a clinical zero.

All first judgments would be new. Do not mix the 99 accepted S55 stage judgments with judgments made under the new instructions, and do not carry S55's successful control gate forward. Retain the S55 record separately. The future engine must enforce the unchanged six unsafe-error checks, six strict-order groups, at least eleven of twelve repeated control stage vectors, and six partial-repeat differences within five points before development scoring. It must keep the 72-cell denominator, eight medication review holds, missing values as null, no pooled model means or rankings, and no automatic retries or resume.

## Next work and approval boundary

1. Implement and test a separately versioned judge-only execution engine with sealed captures, source verification, budget stops and a fresh control gate. The current module only constructs and verifies offline inputs.
2. Freeze the new protocol, check current provider pricing and obtain fresh bounded approval for disclosure and spending. The old $20 allowance was for one consumed run; its unused balance is not permission for another experiment.
3. Run the approved experiment once, then audit evidence-format failures, missing cells, first/repeat disagreement and family-level ceiling effects. Passing format tests alone does not demonstrate that the new wording solves the live failure or calibrates clinical scoring.

The expansion target remains **at least 500 distinct families**. This checkpoint adds no cases: registered development is **125 families / 250 variants**, plus four standalone O/P families / eight variants outside the registry and frozen panel. Approved calibration/Gold remain **0/0**. H142–H147 remain open, Xi'an stays local and expert review stays deferred. Lower-tier 60–70, average around 80 and premium around 90 remain diagnostic aspirations, never scores to manufacture.

## Offline verification

The full offline suite passed **999 tests**. The **22 new S56 tests and four S55 evidence regressions** also passed as a separate 26-test check. Public readiness recomputes exactly from sealed raw sources, recorded bank/file hashes match, the S54 freeze remains unchanged and 448 local documentation links resolve.

The new tests cover per-status evidence rules in both languages and stages, exact-prefix exceptions, schema shape, missing or duplicate criteria, wrong-turn and fabricated quotes, observation requirements, 144-stage completeness, model/case/history bindings, raw-source provenance, tampering, private-text exclusion, identical repeat payloads and the absence of a live command. A sealed simulated candidate journal exercises extraction separately from the actual private-source replay. Frozen S26–S55 artifacts and the historical rejection remain unchanged.
