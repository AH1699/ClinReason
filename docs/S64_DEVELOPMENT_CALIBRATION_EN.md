# S64: scoring repair prototype, next gates and two new case families

Updated October 27, 2026, America/New_York. **Offline work only: zero new provider calls or model scores.** S62 remains closed; its approval and unspent allowance cannot be reused. S36 arithmetic, historical labels and results are unchanged.

## How far are we from finishing calibration?

There are two different finish lines. We can stabilize a **provisional development scoring version** while expert review is deferred. We cannot finish **clinical calibration** without independent clinical and bilingual judgments and a reserved, untouched evaluation set. Approved calibration/Gold are still **0/0**. A case-count target or another clean engineering run cannot close that gap.

| Gate | Current evidence | What closes the gate |
|---|---|---|
| Scoring calculation and audit trail | Deterministic S36 arithmetic, stage isolation, missing/interval handling and replay work | Preserve regression checks; no numerical retuning planned |
| Judge output reliability | S63 stopped at three quotation-format failures; S64 has a working offline reference prototype | A separately versioned live feasibility test must demonstrate valid, relevant reference selection and acceptable request size |
| Candidate completion | Both MiniMax APIs worked, then exhausted an 8,192-token completion budget | Prospectively test a larger bounded budget; document completion, reasoning usage and visible answers without substituting missing results |
| Broader development consistency | S63 has 39/64 first scores; six full repeats all belong to one family. Earlier S58 had one provisional-pass change | Complete a prospectively fixed bilingual multi-family study; inspect criterion, safety, pass-boundary and repeat differences, with missing denominators retained |
| Clinical calibration and release claims | No independent approved answer ratings or approved Gold | Later blinded expert/source/bilingual adjudication, justified acceptance thresholds and held-out evaluation |

**Planning estimate, not a promise:** after the offline work, budget for two further empirical batches if they pass: (1) a small feasibility batch, then (2) one broader confirmation batch. A failure may require another version; do not report a completion percentage or guarantee a date. Expert scheduling is a separate dependency. Case expansion continues throughout, so engineering failures do not freeze the entire project.

The first future feasibility proposal is **12 judge requests** (three previously problematic source packets plus three valid controls, each twice under the new contract) and **four candidate requests** (one fixed two-turn case per MiniMax model). These would be new diagnostic observations, not replacements for old missing judgments. Selection, privacy checks, prices, payload limits, cost policy, stop conditions and code freeze must be completed before fresh approval. This document is not a runnable protocol or spending authorization.

Before broader confirmation, predeclare coverage and acceptable evidence-format, repeat-vector, pass-boundary and safety-control behavior. Do not choose success thresholds after seeing the next results. A complete run can still fail a consistency gate. Independent human agreement and unsafe false-pass rates cannot be inferred from AI agreement.

The owner's approximate **60–70 / around 80 / around 90** lower/mid/premium aspiration remains documented. It is a difficulty diagnostic, never a reason to curve scores, penalize correct answers or change labels after observing a model.

## Implemented evidence-reference prototype

[S64 implementation](../scripts/evidence_refs_s64.py) supplies a lossless catalog of saved assistant-text chunks. The judge would return the first and last chunk IDs of one continuous range, plus the exact packet hash. The local validator reconstructs the source text itself. It never trusts judge-written quotations, offsets or replacement catalogs.

- IDs bind the packet, assistant turn, exact source text and character offsets. Any packet/answer/anchor change invalidates old references.
- Initial criteria can use only the initial answer. Update criteria can use only the update answer. Update observations can cite either answer, but never bridge turns.
- Unknown, reversed, cross-turn, malformed and legacy quotation fields are rejected. Existing required-evidence and literal absence exceptions remain unchanged.
- The resolved judgment passes through unchanged S36 validation and arithmetic. Criterion statuses, error severities, uncertainty intervals and observation requirements are not rewritten.
- The complete transcript remains visible within its stage. A source-valid reference can still be irrelevant or too broad; this prototype does **not** validate clinical reasoning or evidence relevance.

The [read-only exercise](../scripts/audit_evidence_refs_s64.py) replays the closed S62 journal before checking **96 accepted control packets and all three rejected judgment packets**. Mechanically authored all-unclear fixtures test source resolution; they are not new AI judgments. The three original replies remain format-rejected and the journal hash is unchanged. [Public structural result](../data/audit/s64_evidence_reference_prototype.json) exports no answer or judge text. Unit tests also compare unchanged arithmetic over all 36 existing bilingual control-stage packets, including met/partial/missed/unclear and configured critical errors.

This is **not wired into the live runner**. Provider schema compatibility and live ID-selection reliability are untested. Request size is a real open issue: the complete prototype input/catalog/schema/instructions for the three affected packets serialize to 33,372, 60,149 and 34,113 Unicode characters. These are **not token counts** and not like-for-like comparisons with the old packet alone. Minimize duplicated schema/catalog metadata and verify the intended token budget before any call; the old 16,000-input-token accounting assumption cannot be carried over unchecked.

## MiniMax budget review

Recorded S62 failures used 8,156/8,190 and 8,191/8,192 reasoning/completion tokens respectively. Almost no room remained for visible answers. MiniMax's current [parameter documentation](https://platform.minimax.io/docs/api-reference/text-openai-api) confirms that thinking uses the completion limit and recommends `max_completion_tokens` for new integrations. M3.1 Flash requires thinking; its effort setting defaults to `max` and can be reduced. M3 has different thinking controls. These facts explain a configuration limit, not a model-quality score.

**Prospective engineering choice:** first test a 32,768 completion-token ceiling for each MiniMax candidate, retaining adaptive thinking and Flash's explicit `max` effort to isolate the budget change. This is an author proposal, not a documented provider recommendation or a guarantee of completion. Do not send both old and new cap fields. Keep a paid-run stop threshold and no automatic retries; do not use unlimited output. Recheck supported fields, model identity, service tier and rates before freezing the new protocol. If effort is changed later, label it a separate configuration instead of silently replacing results.

Equal numerical limits do not guarantee equal compute across providers. Report model/configuration, visible output, reasoning usage, completion status, cost and language separately. Keep the visible-answer-only conversation protocol; do not introduce provider thinking into the judge or alter history mid-run. Any future different history policy requires its own version.

## Batch R: authoring continues independently

Public inventory is now **135 families / 270 language variants**: 125 registered plus ten standalone O/P/Q/R drafts. **365 additional families** remain to the 500-family draft target. Registration, calibration and clinical approval have not changed.

| Family | Decision-changing mechanism | Review hold |
|---|---|---|
| REASON-028 | Lipemic low sodium versus normal direct measurement/tonicity; avoid treating the artifact while retaining care for severe triglycerides | H153 |
| MEDSAFE-022 | Possible ACE-inhibitor bowel swelling despite long use/no facial swelling; interpret withdrawal improvement without a dangerous home rechallenge | H154 |

These are original synthetic cases inspired by the published reports of [Hashem et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC11663367/) and [Pirzada et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC10676215/), with article-level attribution licenses checked. No source patient, image, unique timeline or treatment regimen was copied. The [provenance](../data/authoring/batch_r_provenance.json) separates supporting evidence from author inference; the ACE imaging/withdrawal uncertainty items still need independent corroboration. Related existing sodium/lab-artifact and longstanding-drug GI families are explicitly listed for later split grouping. No empirical difficulty claim is made.

Deliverables: [four bilingual conversations](../data/authoring/batch_r_cases.json), [exact-case anchors](../config/multiturn_criterion_anchors_batch_r_v1.json), [reference/omission/unsafe examples](../data/authoring/batch_r_contrasts_v1.json) and 14 source-mapped criterion positions. Four initial references and 12 update examples remain unscored. “Safe” is an author profile name, not clinical certification. Chinese text was composed for equivalent meaning; the inherited `machine_translation_unreviewed` enum conservatively retains the review hold.

New drafts live in `data/authoring/` so historical directory scans and frozen experiment inputs do not change. The discovery catalog includes them; the default benchmark runner does not. The [batch checker](../scripts/audit_batch_r.py) checks hashes, bilingual coverage, source mappings, control bindings and visible report identifiers against 188 existing family/file pairs. It does not prove semantic independence, privacy of arbitrary future raw assets or clinical correctness.

## Next execution order

1. Reduce prototype request duplication, check provider-compatible schema and bind a fresh offline transport rehearsal. Finish a small, approval-ready feasibility protocol; no extra case selection from observed scores.
2. After separate approval, run the bounded feasibility batch. If it fails, publish the failure and decide whether to revise the contract or keep the provisional scorer limited; do not automatically loop on paid diagnostics.
3. If it passes, freeze the broader consistency batch and its acceptance criteria before running. Keep Batch R authoring separate from that fixed panel.
4. Continue case expansion and the clinical question register. Later, adjudicate and evaluate on held-out material before claiming completed clinical calibration.

Verification completed: **1,191 offline tests passed** in 682.930 seconds, including 20 new reference/audit/case tests. All 512 checked local Markdown links resolve. The first full run caught S41's directory-wide module freeze; the new prototype was moved to the experimental scripts area without changing the historical freeze, then the full suite passed. S41/S57/S60/S61/S62 snapshots remain intact. Batch R's public audit reproduces, and all 24 R control-stage packets build under the new offline reference contract. No clinical judgment or paid call follows from these checks.

Local checks: `python3 -m unittest tests.test_evidence_refs_s64 tests.test_audit_evidence_refs_s64 tests.test_batch_r tests.test_authoring_catalog`; `python3 -m scripts.audit_batch_r`; `python3 -m scripts.authoring_catalog --summary`. Private keys, raw journals, Xi’an and purchased records stay local and excluded from Git.
