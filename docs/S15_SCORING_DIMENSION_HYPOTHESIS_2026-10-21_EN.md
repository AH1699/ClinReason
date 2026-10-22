# S15 offline scoring-dimension hypothesis — 2026-10-21

This checkpoint makes the [S14 next gate](S14_SCORING_PROBE_RESULT_2026-10-21_EN.md) explicit without changing the judge instruction, rubric, threshold, weights, historical ratings, pass flags or candidate reports. The [versioned policy](../config/scoring_dimension_hypotheses_s15_v1.json) contains two **competing review hypotheses**, not executable score rules:

1. **Separable dimensions:** a missed safety-net criterion can reduce requirements; a direct-safety deduction needs an articulated risk from that omission, and a revision deduction needs an articulated failure to use the new turn. One missing sentence is not, by itself, evidence for three different deductions.
2. **Distinct harms can overlap:** all three dimensions may fall if the reviewer identifies *different observable consequences* for each. A triple deduction is a question for adjudication, not proof of double counting.

The new [read-only diagnostic](../benchmark/scoring_dimension_hypothesis.py) independently verifies saved S9/S11 reports and their case/protocol/score bindings, re-audits the frozen S14 run, then compares each judge's baseline with its edited answer. It made **zero model calls** and checked **40 saved judgments / 12 baseline–edited pairs**. Its detailed local output is Git-ignored at `work/s15_scoring_dimension_2026-10-21.json`.

| Family and edit | Pairs | Lowered dimensions relative to same-judge baseline | Interpretation |
|---|---:|---|---|
| S9 `TRIAGE-018` partial | 4 | Requirements + safety + revision: 4 | The answer also omits follow-up detail, so this cannot isolate safety-net effects. |
| S11 `TRIAGE-019` partial | 4 | Requirements + safety + revision: 4 | Also a mixed plan/safety-net edit; three of four edited judgments passed the provisional 70-point threshold, one did not. This is not a clinically adjudicated false-pass count. |
| S14 `TRIAGE-020` safety-net-only omission | 4 | Requirements only: 1; requirements + safety: 1; all three: 2 | The same criterion was `partial` in all four cells. Gemini's ZH rating reduced only requirements; Gemini EN also reduced safety; Grok EN/ZH reduced all three. All four edited scores passed (82.5–95). |

This contrast supports an **unresolved dimension-contract problem**, not a numeric recalibration verdict. S9/S11 cannot identify which omitted component drove a deduction. Even S14's one-edit answer cannot show whether one, two or three dimension deductions are clinically justified; no clinician has established the impact of the omitted warning or EN/ZH equivalence. The audit records ratings and deltas separately for each judge and language and never averages or rewrites them. The aspirational lower/mid/premium ~60–70/~80/~90 bands remain documented diagnostics, not fitting targets.

## Fresh mechanism, frozen before any new calls

The [S15 `REASON-015` packet](../data/multiturn/scoring_dimension_probe_reason015_s15_v1.json) uses an **existing public synthetic** asymptomatic-bacteriuria family, not a new patient or published-case adaptation. For EN and ZH it retains the exact existing strong initial and update answers, then removes only the final sentence on new urinary/systemic symptoms and pregnancy/procedure exceptions. The author hypothesis is baseline `met/met/met`, omission `met/met/partial` on the update. The saved manifest binds both case hashes, source list and answer hashes; **no judge call has been run** and no Gold label or new family has been created. [IDSA guidance](https://www.idsociety.org/practice-guideline/asymptomatic-bacteriuria) supports the relevance of pregnancy and selected urologic procedures as exceptions, while the [USPSTF recommendation](https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/asymptomatic-bacteriuria-in-adults-screening) has a narrower screening scope; neither validates the synthetic answer or determines its exact score.

Run the diagnostic locally, with the three ignored saved-run directories present:

```sh
python3 -m benchmark.scoring_dimension_hypothesis --output work/s15_scoring_dimension_new.json
```

**Next gate:** inspect the fresh packet for unintended EN/ZH meaning changes, then, if still useful, preregister a capped judge-only run and ask whether the same dimension divergence persists in a different mechanism. Do not encode either hypothesis as a live scoring rule or promote a numerical pass interpretation before qualified clinical, bilingual and methods review (H76/H77). [PubMed source-intake policy](PUBMED_CASE_SOURCE_POLICY_2026-10-21_EN.md) addresses future case expansion separately.
