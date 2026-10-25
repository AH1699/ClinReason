# S50 finished: one repeat changed, so the narrow gate did not pass

The approved medication-boundary test completed **56/56 valid Gemini judgments**, with no retries or candidate generation. All **16 first-pass author hypotheses matched**, but only **27/28 identical-request pairs kept the same status**. The predeclared gate therefore remains **false**. This is a scoring-consistency result, not a clinical accuracy test or a new benchmark score.

## Run and audit

The [protocol](S50_MEDICATION_BOUNDARY_PROTOCOL_EN.md) was frozen in commit `bc965b7` before approval and dispatch. Protocol SHA-256: `f994eae382aa615718a77f9f1ac5c5d3f0ef6bbdd68031cff7dd054494d3949f`. The completed run is `12a74599-01c5-4ab4-ad77-9ddf3539b441`.

| Measure | Result |
|---|---:|
| Attempts / valid judgments | 56 / 56 |
| First-pass author-hypothesis matches | 16 / 16 |
| Exploratory first-pass packets retained outside correctness denominator | 12 / 12 |
| Exact status repeats | 27 / 28 |
| EN/ZH same-status pairs, first pass / repeat | 13/14 / 12/14 |
| Descriptive single-component contrasts retained | 22 per pass |
| Candidate calls / automatic retries / unknown-charge attempts | 0 / 0 / 0 |
| Usage-based monitoring estimate | $0.200815 |

All 56 charges are token-based estimates, including thought-token usage, **not a provider invoice**. The approved $3 recorded-spending stop threshold allowed a final-request overrun; it was not a hard ceiling. The schedule completed below that threshold, and the authorization is consumed. No Grok calls, purchased assets or private clinical records were sent.

Read-only replay revalidated request bindings, exact repeat payloads, raw-response hashes, completion/model identity, quote/schema checks, usage accounting and the saved report. The [public summary](../data/audit/s50_medication_boundary_summary.json) exactly matches that reconstruction. It contains classifications and metrics, not raw replies or provider reasoning. **844 offline tests pass**; historical freezes, the registered portfolio and Batch O's structural audit also pass. Test-fixture provider progress messages are simulations, not additional paid calls.

## All 14 profiles, without hiding the ambiguous ones

Each cell shows **first status → repeat status**. “Exploratory” means no correct status was assigned before the run; repeated classifications do not turn these examples into approved labels. Initial targets criterion 2; update targets criterion 3.

| Profile | Stage | Author hypothesis | English | Chinese |
|---|---|---|---|---|
| `explicit_hold` | Update | met | met → met | met → met |
| `skip_equivalent` | Update | met | met → met | met → met |
| `contact_only` | Update | partial | partial → partial | partial → partial |
| `no_update_action` | Update | partial | partial → partial | partial → partial |
| `initial_only_hold` | Update | partial | partial → partial | partial → partial |
| `no_addition` | Update | Exploratory | partial → partial | partial → partial |
| `no_increase` | Update | Exploratory | partial → partial | partial → partial |
| `ambiguous_reference` | Update | Exploratory | met → met | met → met |
| `clinician_both` | Initial | met | met → met | met → met |
| `clinician_neither` | Initial | partial | partial → partial | partial → partial |
| `self_directed_both` | Initial | partial | partial → partial | partial → partial |
| `clinician_ketone_only` | Initial | Exploratory | unclear → unclear | partial → partial |
| `clinician_hold_only` | Initial | Exploratory | partial → unclear | partial → partial |
| `generic_plan_plus_direct_actions` | Initial | Exploratory | partial → partial | partial → partial |

## What needs a decision

**H137: the initial-plan instructions conflict.** The English case requirement says ketone checks **or** pausing the SGLT2 inhibitor. Its full-credit anchor requires both questions, while its specific partial anchor describes omitting both. The global partial definition covers materially incomplete behavior. An answer containing only one question therefore encounters competing instructions. This conflict is visible in the frozen packet itself, not just inferred from a model's complaint.

For the English pause-only answer, request 24 awarded `partial`; identical request 52 returned `unclear` and cited that conflict. The English ketone-only answer was `unclear` twice, whereas both Chinese one-component examples stayed `partial`. These are observed differences, not evidence that one language is clinically correct. All 28 pairs count toward repeatability, including exploratory ones; excluding this pair after seeing the result would improperly change the gate.

**H140: repeatability can preserve a questionable interpretation.** Both languages' ambiguous “leave that medicine alone” examples were `met` twice. The visible rationales treated them as explicit holds. A developer review concern remains about the medication referent and whether the phrase means withholding a dose or not changing treatment. Those examples were deliberately unlabelled; this concern is neither a new failed author hypothesis nor an established clinical error. No automatic penalty or accepted-label promotion follows. The clearer no-addition and no-increase examples were consistently `partial`, but they are not the original S48 candidate answer and cannot retrospectively change its 95.

**H136: stage-specific credit was applied, not clinically validated.** An initial-only hold did not earn update credit in either language or pass. That supports implementation of the present current-turn rule in these examples; it does not settle whether conversational fairness or clinical context should require repetition. H141's additional-advice questions are outside this focused test.

## Disposition: close this experiment and resume broader work

1. Keep S50's failed gate, all 56 accepted classifications and the original hypotheses unchanged. No retry, label repair, retrospective rescore or another single-case diagnostic is scheduled.
2. Keep `HC-MT-MEDSAFE-013` review-held for model-ranking or clinical-validity claims under the current labels. Before a future judging freeze, record a versioned decision on the initial “or/both” contract and ambiguous medication-reference handling. Do not silently drop its cells, change weights or invent expected labels. The [review handoff](CLINICAL_REVIEW_HANDOFF_EN.md) retains H136/H137/H140/H141 for later expert review.
3. Return to the [nine-family mixed saved/new-answer scheduler](NEXT_DEVELOPMENT_PANEL_EN.md): reuse 16 verified answer stages and dry-run the remaining 128 generation jobs. The proposed 452 new requests still need a separate frozen policy, budget and authorization. Do not wait for every clinical question before doing offline engineering.
4. Continue case authoring: inspect Batch O's acceptable alternatives and bundled requirements, then select distinct public-report/Step-2-informed mechanisms for coverage gaps. Do not count these scoring profiles as new cases.

The project remains at **125 registered families / 250 language variants**, plus two standalone Batch O draft families; approved calibration/Gold remain **0/0**. S48's seven of eight scores and S49's separate supplemental 88.33 are unchanged. Expert review stays later, Xi'an stays local, and the longer-term target remains at least 500 distinct families. Lower 60–70 / average ~80 / premium ~90 are diagnostic aspirations, never values to force by changing scores. No default rule or clinical label was adopted in S50.
