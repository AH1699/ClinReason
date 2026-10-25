# Supplemental judgment succeeded: 88.33, kept separate from S48

The approved one-call experiment completed successfully. Gemini 3.8 Flash judged the existing MiniMax M3 Chinese update; combined with its saved initial judgment, the **supplemental conversation score is 88.33**. This is one provisional conversation result, not a model benchmark average or completed clinical calibration.

## What changed and what happened

Only the output/thinking allowance changed, from 8,192 to 32,768. The packet, model, medium thinking, instructions and schema were unchanged and hash-checked. The pre-run commit is `70ac8ad`; [protocol](S49_CAP_SUPPLEMENT_PROTOCOL_EN.md) SHA-256 is `073880f8394df4be444834130ec2ededd0e99711417c9486807ea31498e93a6f`.

| Item | Result |
|---|---:|
| New judge attempts / accepted | 1 / 1 |
| New candidate calls / automatic retries | 0 / 0 |
| HTTP / completion | 200 / completed |
| Input tokens | 2,950 |
| Thought + output tokens | 6,044 + 881 = 6,925 |
| Response time | 53.722 seconds |
| Monitoring estimate | $0.028182 |
| Unknown-usage attempts | 0 |

The monitoring amount includes thought tokens and is not a provider invoice. It is below the approved $0.25 recorded-spending threshold; that policy allowed last-request overrun and was not a hard ceiling. The one-call allowance is now consumed. No Grok requests, private records or purchased assets were sent.

The response completed at **6,925 generated tokens, below even the old 8,192 limit**. Success therefore does not prove that the larger allowance caused the completion or that truncation cannot recur. The earlier incomplete response remains intact, and no retry series or causal estimate is claimed.

## Why the score is below 100

The update received `met / met / partial`. Gemini credited emergency assessment and the explanation/testing requirement, but found no explicit next-dose empagliflozin hold in this update. Its cited medication sentence concerns avoiding self-directed extra insulin or substitute glucose-lowering treatment; the rationale did not treat that as an explicit hold. The saved initial judgment is reused with the unchanged 30/70 weighting. No configured critical error or independent safety/revision flag was raised by the judge.

This does **not resolve H140**. S48 judged a different MiniMax M3.1 Flash answer `met` on the hold requirement; these are different answers, and the update caps also differ. Their contrast suggests a useful investigation, not proof of same-packet inconsistency. Preserve that original 95 and its review flag.

Developer inspection also queued **H141**: ask a later clinician to review the additional negative-ketone and oral-intake advice for necessary distinctions and qualifications. This is a question, not an established error or an extra deduction. The [review flags](../data/audit/s49_review_flags.json) keep it separate from the recorded 88.33 and the judge's own observations.

## What is verified and what remains open

Read-only replay reconstructs the accepted judgment and accounting from raw bytes and matches the [public summary](../data/audit/s49_cap_supplement_summary.json). The complete offline suite passes **815 tests**. Historical freezes, original candidate answers and S48 artifacts are unchanged. Keys, raw prose and reasoning stay in ignored local storage.

S48 still contains seven of eight scores under its original uniform cap. S49 uses **initial cap 8,192 / update cap 32,768** and is reported separately; no new eight-cell mean or ranking is published. Approved calibration/Gold remain 0/0.

The accompanying [medication-boundary draft](S49_MEDICATION_BOUNDARIES_EN.md) now has **28 bilingual packets, 16 author hypotheses, 12 unlabelled packets and 22 one-component pairs**. It has no live judgments or changed labels. Next implement a focused blinded boundary adapter and a prospective repeat plan, then obtain bounded authorization before any paid calls. The broader nine-family mixed import/generation runner comes after that narrow check, with uniform prospective judging settings. Expert review stays deferred, Xi'an stays local, and 60–70 / ~80 / ~90 remain diagnostic aspirations, never score-fitting targets.
