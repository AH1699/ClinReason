# Standalone case pilot inputs and next execution plan

The eight O/P/Q families now have a separate, reproducible [input manifest](../data/audit/s60_standalone_pilot_manifest.json). It binds the selected cases, scoring anchors, reference controls, source mappings and proposed schedule. This is an **offline input freeze**, not a live runner or paid-call approval. No new model answer, score or case family was produced.

## What this pilot should tell us

The previous panel often reached the ceiling: S58 recorded 38 perfect first-pass scores among 64 non-held conversations. This pilot asks whether different reasoning problems expose meaningful omissions, unsafe conclusions or failure to use new facts, and whether the judge repeats its decisions on identical answers. It does not promise lower scores merely because the scenarios look more complex.

Every family has English and Chinese versions and an initial question followed by new information. The selection balances reasoning patterns, not measured difficulty or medical specialties:

| Design group | Families | Reasoning problem |
|---|---|---|
| Diagnostic restraint, three families | REASON-025, TRIAGE-024, REASON-027 | Uncertain platelet measurements; routine follow-up after reassuring blood-pressure monitoring; an unresolved hypercalcemia diagnosis before surgery |
| Competing treatment risks, three families | REASON-024, MEDSAFE-020, MEDSAFE-021 | Congestion versus kidney-test changes; nutrition and electrolyte trade-offs; iron treatment and persistent low phosphate |
| Escalation under uncertainty, two families | REASON-026, TRIAGE-025 | Inflammatory wound versus infection; worsening bleeding despite an initially reassuring mixing test |

All IDs begin `HC-MT-`. There are four clinical-reasoning, two medication-safety and two triage families. The 3/3/2 grouping is not an easy/medium/hard classification or a representative global clinical sample. Related-family links remain attached for later grouped split review; translations and related mechanisms are not independent observations.

## Exactly which labels and answers are selected

P and Q use their existing version 0.1.0 cases and corresponding anchors. O uses the **separate S52-derived version 0.2.0**, not its original version 0.1.0. Only update requirement 3 changes in each O family. The original files and all historical scores stay intact.

There are **52 criterion positions / 104 bilingual instances**. O/P have three requirements per stage; Q has three initial and four update requirements. The builder checks all positions without truncating Q to three. Full-family hashes also bind acuity metadata, which the older variant hash alone does not cover.

Source mappings remain linked to each position. The two changed O wordings are explicitly marked as an original source mapping plus an unrevalidated S52 interpretation. They are not passed off as newly source-validated labels. H142–H146 and H149–H152 stay open, including the Q wound-source correction question. Clinical and bilingual review remain required later.

The core controls contain 16 shared initial answers and 48 update answers: one authored strong, one single-component omission and one unsafe foil per family/language. In the source files these profiles are named `safe`, `partial` and `unsafe`; those names describe construction, not guaranteed status or score. Removing a sentence may leave its meaning elsewhere in the answer. We therefore do not require every omission to lower the score or silently set a full-answer target of 100. The hypothetical unsafe-error IDs are retained outside judge inputs for later comparison.

The existing S52/S53 O supplement is also bound: 72 targeted records share 58 unique packets, including eight unlabelled exploratory records. It stays available for offline interpretation but **adds no calls to this proposal**. It is not 58 additional cases.

## Proposed model run

The continuity proposal retains Gemini 3.5 Flash-Lite, Gemini 3.8 Flash, MiniMax M3.1 Flash and MiniMax M3 as candidates, with Gemini 3.8 Flash as judge. These are the previously used names, not a fresh availability or price check. Grok is not scheduled; its access problem is not converted into a clinical zero. A single-company judge and Gemini judging Gemini remain limitations.

Eight families × two languages × four candidates gives **64 conversations / 128 candidate turns**. All answers would be newly generated; no old answers are imported.

| Proposed phase | Requests | Purpose |
|---|---:|---|
| First control judgments | 64 | Sixteen shared initial packets plus 48 updates |
| Control repeats | 32 | Repeat the 16 initial and 16 omission-update inputs exactly |
| Candidate generation | 128 | Two turns for each of 64 conversations |
| First candidate judgments | 128 | Judge each answer stage separately |
| Candidate judgment repeats | 128 | Rejudge the same saved inputs; do not regenerate answers |
| Total | **480** | Planning count, not an allowance or completion guarantee |

The read-only schedule specifies dependencies. A candidate update needs that same conversation's initial answer; a judgment needs the matching saved answer stages. The helper will not fill a missing answer with a reference. A future executor must enforce exact answer provenance and all stop/gate decisions; S60 itself dispatches nothing.

Candidates receive only visible conversation messages and the existing bilingual instruction—not labels, references, controls or future turns. Initial judges see only the first question/answer and initial criteria/errors. Update judges see the conversation to that point but only update criteria/errors. Control names, expected errors, review issues and candidate identities stay outside judge inputs. No previous judgment is supplied on repeat.

The selected judge contract reuses S56's explicit evidence instructions and variable-length S36 validation. S36 arithmetic is unchanged: initial/update weights 30/70; criterion credits 1/0.5/0; existing critical-error deductions/caps and provisional pass threshold 70. No score is calculated by the S60 builder.

## Reporting and spending rules

Keep all 64 planned cells, including missing or review-held results. Show first and repeat judgments separately, with criterion status/evidence, errors, uncertainty, completion failures, perfect-score frequency, pass changes and language-pair differences. Missing is not zero. Do not average repeats, remove difficult cells, pool model means or publish rankings from this draft pilot.

The desired lower-tier 60–70, average around 80 and premium around 90 remain diagnostic aspirations. We will use ceiling frequency and meaningful clinical omissions to assess the design, not tune labels or weights to manufacture those bands. The four-model proposal cannot estimate the original six-model roster mean.

The prospective cost policy is one request in flight, no automatic retries or resume, and a global stop for unknown delivery or cost. A recorded-spending threshold may permit a last-request overrun; it is not a hard account cap. **The threshold, current price evidence and approval are all unset.** S55/S58 and earlier allowances cannot be reused. No keys, Xi’an records or purchased material enter this package.

## Next work

1. Implement a separate journal, transport and report integration, testing it with simulated replies for this exact 480-request proposal. Include same-model history binding, variable criterion counts, preserved missing cells, interruption accounting and unchanged-input repeats.
2. Freeze provider settings, technical failure limits and prospective control/reporting gates before seeing any new model result. Control disagreements must remain visible; they are not grounds for relabelling or resampling. The old S58 gate/results remain unchanged.
3. Verify current models and prices, produce a bounded cost estimate and request fresh approval for the exact export/run scope. Do not turn this input manifest into an approval file.

Case expansion can continue separately without changing these selected inputs. Prioritize distinct longitudinal decisions and competing-risk problems in underrepresented clinical domains; link public reports to separate answer-supporting guidance before writing new labels. The inventory stays **133 public draft families / 266 variants**, of which 125/250 are registered and eight/16 standalone. We still need 367 additional families to reach 500. Approved calibration/Gold remain 0/0; Xi’an stays local. Professional review is deferred, not waived.

## Local verification

```sh
python3 -m scripts.standalone_pilot_s60 --verify --summary
python3 -m unittest tests.test_standalone_pilot_s60 -q
```

[The builder](../scripts/standalone_pilot_s60.py) has no live, approval, output-file or resume mode. Its 18 tests check the selected O revision, source-mapping qualifications, controls, stage isolation, four-criterion updates, same-cell schedule dependencies, repeat hashes, missing-answer refusal and stale/unsafe-input rejection. Together with the O/P/Q/catalog tests, 59 focused checks pass. The full offline suite passes **1,086 tests**. The saved manifest reproduces exactly, and the S57 historical freeze and S59 authoring audit remain unchanged. These verify engineering structure, not clinical adequacy.
