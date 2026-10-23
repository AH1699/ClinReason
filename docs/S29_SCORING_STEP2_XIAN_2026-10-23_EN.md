# Scoring readiness and linked Xi'an record progress

**Historical pre-approval checkpoint.** Owner approval arrived later on 2026-10-23 and both calls completed. See the [actual S29 result and S30 draft](S29_RESULT_S30_BOUNDARIES_STEP2_2026-10-23_EN.md). The “sore-throat” wording was a prose error: the unchanged packet is TRIAGE-020, improving sinus symptoms. Pending-approval and zero-call statements below describe the earlier state, not the current one.

## Current position

The two-call transport diagnostic is frozen and tested, but **has not run**: the local approval check blocked execution before any provider request because the exact benchmark packet would be sent to Grok and Gemini. Explicit approval for those two external calls is pending. This is not a provider failure or an ambiguous billed attempt. S28 remains unchanged at 13 valid judgments, with no repeats and no calibration completion.

The two Step 2–informed batch-M families now have **13 draft criterion boundaries, four shared initial answers and 12 bilingual update-answer controls**. No family was added by this answer-packet work: public development remains **124 families / 248 variants**; approved calibration and hidden Gold remain **0/0**. Expert review stays deferred during partner discussions.

The owner confirmed that **all 50 Xi'an PDFs belong to one encounter**. That resolves the grouping request for the current files. A local manifest binds the confirmation to their exact hashes and 90 pages; it does not silently include future files or claim independent identity verification. Four source-image time fields have been checked and a private relative-time scaffold created. No Xi'an-derived benchmark case is ready yet.

## Scoring diagnostic and next gate

The [S29 protocol](S29_TRANSPORT_PROTOCOL_2026-10-23_EN.md) was committed as `57d8a93` before the blocked execution request. It permits at most **two judge calls**, Grok then Gemini, using the same English sore-throat partial-answer packet, a prospective 240-second socket timeout, and zero retries/candidate calls. The observer distinguishes allowlisted transport failures without retaining secrets in the diagnostic. Two successes would only permit designing a fresh full scoring/repeat panel; they would not prove that timeouts are fixed or calibration is complete. No score-based selection is permitted.

Until specific external-call approval arrives, keep this diagnostic unrun. Do not bypass the approval check, disguise the packet or use another transport. The unchanged frozen inputs remain checkable with `python3 -m benchmark.transport_s29 plan`.

## Step 2 answer boundaries

[Batch M anchors](../config/multiturn_criterion_anchors_batch_m_v1.json) distinguish complete, partial, missed and genuinely unclear fulfillment, including acceptable alternative wording. The [answer controls](../data/multiturn/batch_m_contrasts_v1.json) remove one declared component for each partial answer. Unsafe answers replace explicitly listed related components, so they do not simultaneously retain the opposite action instruction. These are authored controls, not model-generated answers or clinical Gold.

`python3 -m benchmark.batch_m_packet_audit` verifies exact case hashes, all 13 source positions, paired language edit targets, configured error IDs and 12 distinct blinded judge packets. It checks construction, not whether a partial answer affects only one clinical criterion. The anchors are not enabled in the default judge. The original case files and provenance are unchanged.

Open review points include overlap between emergency disposition and rejection of numerical reassurance; omission versus affirmative dangerous advice; bundled diagnostic/follow-up requirements; and bilingual equivalence. The existing [source ledger](../data/multiturn/batch_m_provenance.json) remains the evidence map. NIDDK, Queensland Health and the IAEM source were rechecked; grading boundaries are author interpretations, not source-prescribed point deductions. The separately held syphilis draft remains excluded because of calibration-source overlap.

## Xi'an grouping and time verification

The local owner-attested manifest covers **50 files / 90 pages**. A conservative OCR scan found collection-time candidates on 28 pages, receipt-time candidates on 30, and report-or-examination-time candidates on 31. These counts overlap and are not numbers of verified clinical events.

Four narrow source-image fields on two lab pages were visually checked: **one collection time, two receipt times and one laboratory examination time**. The last label is `检验时间`, not proof of report issuance or clinician availability; the verified record preserves this distinction instead of accepting the earlier broad OCR category.

The relative scaffold is anchored to the earliest verified collection time in this small subset, **not admission or symptom onset**. Three previously verified lab rows can be linked to that collection event. Two rows on the other page remain without a verified collection time; its receipt time must not be substituted. None of the results is yet cleared for a decision-time question, because result availability, symptoms, treatments and context remain unverified. No trend, treatment response or diagnosis is inferred.

Source PDFs, filenames, exact dates, cropped images, the owner manifest and the relative scaffold remain local and Git-ignored. Public code uses synthetic test records. Grouping confirmation does not clear complete-record privacy; there were no external Xi'an model calls.

## Verification and next work

**284 tests pass.** S26, S27, S28 and S29 frozen-file checks pass; the portfolio remains 124/248. Next:

1. After explicit approval, run and audit the two-call diagnostic. If both responses are valid, freeze a fresh full-score/repeat panel before running it. Otherwise investigate the recorded failure without retrying the stopped run.
2. Test a bounded batch-L/M answer subset under a separately specified protocol, preserving source isolation and author-profile blinding. Continue distinct Step 2 case expansion with independent answer evidence rather than adding near-duplicate volume.
3. Verify Xi'an's remaining collection times and decision-time context. Use only the confirmed file membership; draft a private case only after its relevant facts and privacy disposition are ready.

Reviewer questions are tracked in H112–H115. Lower-tier ~60–70, average ~80 and premium ~90 remain desired diagnostic bands, not fitted scores or acceptance criteria.
