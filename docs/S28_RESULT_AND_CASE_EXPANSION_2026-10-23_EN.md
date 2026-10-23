# Full score test and case expansion update

## Current position

The full-score experiment stopped on a transport error after **13 valid judgments from 14 attempted requests**. Four completed red-eye groups now have the expected point-score order, but the second family and repeat stage are incomplete. **Scoring calibration is not complete.** No candidate call, retry, resumed panel, default scoring change or score-band fitting occurred.

Two new bilingual Step 2–informed families bring public development to **124 families / 248 variants**: Alpha 32, patient two-turn 50, professional 42. A third draft was held outside the configured dataset after a calibration-source overlap was detected. Xi'an source checks found missing identifier values, so episode linkage still needs a de-identified source manifest. Approved calibration/hidden Gold remain **0/0**; expert review remains deferred during partner discussions.

## Full score result

The [S28 protocol](S28_FULL_SCORE_PROTOCOL_2026-10-23_EN.md) was committed as `18322bf` before calls. The [audited summary](../data/audit/s28_saved_prefix_summary.json) binds the frozen manifest, saved responses and recalculated scores. The original S26 and S27 files are unchanged.

| Completed red-eye groups | Strong | Partial | Unsafe |
|---|---:|---:|---:|
| English, Gemini | 100 | 65 | 25 |
| English, Grok | 100 | 65 | 25 |
| Chinese, Gemini | 100 | 65 | 25 |
| Chinese, Grok | 100 | 65 | 25 |

All four available unsafe errors were detected, with no separate safety/revision concern on the saved strong/partial controls. Gemini's first sore-throat partial answer also scored 65; the next Grok request failed. There are **zero repeat pairs**, and the advance gate is **false**. This is compatible with the intended anchor clarification, but a different run cannot prove that wording alone caused the change.

Saved Grok requests had median latency **65.891 seconds**, maximum **81.273 seconds**; Gemini median **18.903 seconds**, maximum **26.649 seconds**. The failed attempt took approximately **120.1 seconds by local file timestamps**, consistent with the configured 120-second limit. The saved error does not distinguish timeout, connection failure or HTTP rejection, so this is not a confirmed root cause and says nothing about account credit or model quality. Delivery/billing remain unknown.

The new opt-in [transport observer](../benchmark/providers/observed_http.py) has offline tests for timeout, HTTP status, DNS, TLS, unreadable JSON and secret exclusion. It retains one attempt and zero retries. It is **not retrofitted into frozen S28 and has not been used live**. Before spending more calls, use it in a fresh small transport-characterization protocol with an explicitly chosen timeout; only then register another complete scoring/repeat panel. Do not silently increase the old timeout or resume S28.

## Two new families and one held draft

[Batch M](../data/multiturn/batch_m_cases.json) has 13 draft requirement positions, each linked in its [provenance ledger](../data/multiturn/batch_m_provenance.json):

- `MEDSAFE-018`: medication and volume confounding in hypotonic hyponatremia, followed by new confusion despite a slightly improved laboratory value. The public basis is [IAEM's assessment guideline](https://iaem.ie/wp-content/uploads/2024/05/Hyponatraemia-Guideline-V1.0.pdf) and [Queensland Health's symptom-led emergency guidance](https://www.health.qld.gov.au/cpc/diabetes-and-endocrinology/disorders-of-salt-and-water). Exact urgency and severity are author hypotheses awaiting review.
- `REASON-022`: a negative IgA-based celiac test while gluten intake continues, followed by markedly low total IgA. Test selection and specialist assessment are grounded in [NIDDK's testing guidance](https://www.niddk.nih.gov/health-information/professionals/clinical-tools-patient-management/digestive-diseases/celiac-disease-health-care-professionals) and [NICE recommendations](https://www.nice.org.uk/guidance/ng20/chapter/Recommendations). The latter's indexed recommendations were available; full-page/PDF retrieval was blocked. The key does not impose a universal adult biopsy pathway.

Purchased source locators are Renal and Electrolyte pages 17/21/22 and GIT pages 237/239/240. The dialogues, numerical values and sequential updates are newly authored; source stems, choices and figures are not exported. Complexity is designed, not measured, and these cases have not been scored live. Chinese dialogue is independently written and remains unreviewed.

The additional syphilis interpretation draft, informed by Infectious pages 730/732/733, is private and **not counted**: its CDC laboratory source overlaps reserved prospective calibration family `REASON-013`. It was not committed as public case data. Do not evade that isolation gate by changing a URL spelling. A future split/overlap decision is needed before inclusion. Celiac and electrolyte overlaps within public development are explicitly recorded for grouped future splits.

## Xi'an needs linkage evidence, not more assumed chronology

The new [local field-alignment checker](../benchmark/local_record_linkage.py) checked four selected first pages. It found one collection-time candidate, no usable name or admission-ID value, and no same-person or same-admission pair. A targeted masked source-image inspection confirmed that the inspected name and admission-ID regions were blank or obscured, not readable identifiers. This is a finding about those regions only, not all 50 PDFs or full-record privacy clearance.

The five previously verified lab rows remain preserved. OCR date candidates are still unverified, report time is not substituted for collection time, and no relative timeline or Xi'an-derived case was created. All records, dates, images and the held draft remain ignored/local.

**Minimal request for the data team:** provide PDF filename → de-identified encounter ID, or a source-manifest confirmation that all 50 PDFs belong to one encounter. Do not provide names or hospital numbers. A folder name or similar age/sex is not sufficient linkage evidence. This request has been sent to the project owner; it does not block unrelated scoring or case-authoring work.

## Next work

1. Address transport observability and timeout policy in a fresh bounded protocol before another full scoring panel. Keep failed delivery state and spending visible.
2. Add criterion boundaries and controlled answers for batch M; retain the held syphilis draft outside public/calibration runs.
3. Once a de-identified encounter map is supplied, join only mapped Xi'an pages, verify collection times and decision-time facts, then draft a private relative timeline.
4. Continue clinical/bilingual/methods questions in H107–H111. Lower ~60–70 / average ~80 / premium ~90 remains an aspiration, not a target imposed on scores.
