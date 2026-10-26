# Approval bound runner and two new case families

This checkpoint adds a separately versioned runner for the nine-family panel and two new bilingual case drafts. The runner is tested with simulated responses, not a new provider experiment. A **$10 monitored-spending stop threshold and at most 452 requests** are proposed for the next run; no approval has been created or consumed outside tests.

## What the runner now enforces

[The runner](../scripts/mixed_live_s54.py) binds the exact code, historical dependencies, roster, labels, reporting policy and pricing to a prospective snapshot. Its live entry point requires a fresh approval with a specific run UUID and protocol hash. The approval must explicitly cover paid calls, disclosure to Google/MiniMax, the reporting policy and possible last-request overrun. A plain “go ahead”, an old allowance or a prepared snapshot is not this approval.

An exclusive local record consumes the approval before credentials are read or a connection is opened. Reusing that approval or reopening a run fails. Before each exchange, the entry point rechecks the protocol, approval expiry and pricing age. Both approval validity and pricing freshness are bounded to 24 hours. The local operator records actual human authorization; this is not cryptographic identity verification or protection against a malicious user who edits the program.

Requests and attempt records are saved before transmission. Raw bytes are saved before interpretation. HTTP errors cannot become answers even when their bodies resemble valid answers. Unknown cost/delivery stops the run; known-cost invalid content closes that model's lane. There are no retries, redirects or resume. Read-only replay recomputes accepted content/accounting and retains interrupted tails. A complete captured reply remains inspectable after a subsequent result-write failure, without another attempt or duplicate unknown-charge count.

The state computation reuses frozen S51 behavior, but live journals do **not** claim to be offline fixtures. Keys are only read from local `.env.local`; raw captures and consumed approvals stay in ignored private `work/s54-*` directories. No Xi'an records, purchased question text or private clinical material enter this panel.

## Proposed paid scope

The [proposal](../config/mixed_live_s54_v1.json), bound in a [prospective freeze](../config/mixed_live_s54_frozen_v1.json), preserves four candidates—Gemini 3.5 Flash-Lite, Gemini 3.8 Flash, MiniMax M3.1 Flash and MiniMax M3—with Gemini 3.8 Flash judging. Grok remains unavailable, not zero-scored. It retains all **72 conversations / 144 answer stages**, reuses 16 verified saved stages and permits up to **128 generation + 36 controls + 144 first judgments + 144 repeats = 452 new calls**. The inherited control gate runs before development judgments; it may prevent them even after candidate generation has occurred.

The $10 amount is a proposed stop threshold based on recorded token-cost estimates, **not an invoice, hard ceiling or promise that the whole panel will finish**. The last request may exceed it. Unknown usage stops immediately rather than becoming zero cost. No old spending budget or authorization carries over.

Official pages were checked at **2026-10-26 01:01 UTC** (October 25 in New York). Standard input/output prices per million tokens still match the estimator: Gemini Flash-Lite **$0.30/$2.50**, Gemini Flash **$0.75/$3.75**; MiniMax M3.1 Flash **$0.15/$0.60**, M3 **$0.30/$1.20**. M3's observed `default` response to an explicit-standard request remains an unverified tier; the existing monitoring convention uses higher **$0.45/$1.80** priority rates. No cache discount is assumed. [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [MiniMax pricing](https://platform.minimax.io/docs/pricing/overview).

The S53 reporting policy stays intact: eight medication conversations are raw diagnostics only, missing is not zero, repeats stay separate, and no pooled model averages or rankings are permitted. This experiment would test workflow and case-level behavior; it would not finish scoring calibration or validate the desired 60–70 / about 80 / about 90 bands.

## New cases and answer labels

Batch P adds **two distinct standalone families / four language variants**, not more Batch O wording controls.

| Family | New decision | Source and limitation |
|---|---|---|
| `HC-MT-REASON-025` | Both platelet samples contain clumps. A higher citrate value does not settle the true count or establish recovery; continue verification without starting treatment from unreliable numbers. | [Nagler et al. actual case report](https://link.springer.com/article/10.1186/1472-6890-14-19) supplies the interference mechanism; [Croatian laboratory recommendations](https://hrcak.srce.hr/en/321333) support method review. No single national counting procedure is mandatory. |
| `HC-MT-TRIAGE-024` | Stable clinic elevation conflicts first with an unchecked home monitor, then with validated normal ambulatory readings. Avoid both overtreatment and a permanent no-risk guarantee. | [Nyvad et al. PubMed abstract](https://pubmed.ncbi.nlm.nih.gov/31455097/) provides setting-effect inspiration only; [USPSTF guidance](https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/hypertension-in-adults-screening) supports confirmation. The report's extreme case and adverse outcome are not generalized. |

These are original synthetic conversations, not reconstructed patients. The blood-pressure family adds a routine-to-routine triage control. Its difficulty is intentionally not assumed to be expert-level: restraint and appropriate reassurance need coverage alongside harder cases. The platelet family adds unresolved specimen validity and a misleading numerical trend; empirical difficulty remains unmeasured.

- [Prompts and required behaviors](../data/multiturn/batch_p_cases.json)
- [Exact-case scoring boundaries](../config/multiturn_criterion_anchors_batch_p_v1.json)
- [Four initial answers and twelve strong/partial/unsafe update examples](../data/multiturn/batch_p_contrasts_v1.json)
- [Source-to-requirement and privacy notes](../data/multiturn/batch_p_provenance.json)

Every requirement has a source locator and an explicit author-inference boundary. Safety-net and severity choices remain provisional; sources do not automatically validate them. Chinese was composed as natural conversation, with professional bilingual review still pending. Partial answers omit one declared component; unsafe foils are not claimed to be single-component experiments. H145/H146 track later clinical and language questions. No source images, patient identifiers or purchased Step 2 wording were copied. The blood-pressure report was available as an abstract only; free access is not treated as a reuse license.

Registered development stays **125 families / 250 variants**. Standalone O and P now total **four families / eight variants**, outside the frozen panel and default registry. Reserved confirmation and calibration drafts remain separate; approved calibration/Gold stay **0/0**. Historical scores and case files were not changed.

## Verification and next decision

The full offline suite passed **962 tests**. All **30 new focused tests** also passed after the final replay/accounting checks, covering the complete 452-request simulated run, approval and pricing rejection, single-use consumption, interruption/accounting and the case package. S51's saved readiness summary matches an actual private-bank recheck with all 16 imported stages. Historical freezes and original Batch O hashes remain unchanged.

Next, inspect the frozen proposal and obtain explicit bounded approval if the owner wants the paid panel. Refresh the price evidence and refreeze if its 24-hour window has elapsed. No professional review is needed merely to continue draft authoring; it remains mandatory before clinical validation or public comparative claims. Continue distinct public-report/Step-2-informed case authoring and prepare a new authoring catalog without modifying historical run inputs.

Safe offline commands:

```sh
python3 -m scripts.audit_batch_p
python3 -m scripts.mixed_live_s54 snapshot
python3 -m unittest tests.test_mixed_live_s54 tests.test_batch_p -q
```

The snapshot command is read-only and does not create approval. A future `run` needs an explicit freeze, approval record and matching run ID; do not fabricate those from this document.
