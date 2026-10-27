# Four new source-backed reasoning families

Batch Q adds **four original bilingual families / eight two-turn conversations**. The public draft inventory is now **133 families**: 125 registered development families plus eight standalone O/P/Q families. The target remains at least 500 distinct families, leaving **367** additional drafts. Nothing was added to the default benchmark or the completed S58 panel.

These cases are designed to test evidence integration, competing explanations and treatment trade-offs. Their difficulty is **not yet measured**. All clinical and bilingual labels remain provisional; no paid model calls or scores were produced.

## What the new cases test

| Family | Clinical problem | What changes in the second turn |
|---|---|---|
| MEDSAFE-021 | New muscle symptoms during repeated IV iron treatment | Persistent low phosphate and low vitamin D require treatment reassessment without abandoning continuing anaemia care |
| REASON-026 | A worsening postoperative wound | Trauma-associated worsening raises an inflammatory alternative, while infection and urgent surgical assessment remain possible |
| REASON-027 | Mild hypercalcemia with conflicting investigations | A negative gene panel and equivocal scan must be weighed against longstanding/family findings before an irreversible decision |
| TRIAGE-025 | New bruising and isolated prolonged aPTT | Initial mixing-test correction must not delay urgent care for an expanding hematoma and falling haemoglobin |

The patient questions ask what to make of the evidence or do next; they do not name the desired diagnosis or offer an obviously wrong friend's answer to reject. Rare-disease terminology is not mandatory where an accurate plain-language explanation performs the same function.

The calcium case deliberately tests restraint. If primary hyperparathyroidism is ultimately confirmed, age under 50 can itself support a surgical indication; the label must not require stones or fractures first. The present reason to clarify matters before surgery is diagnostic uncertainty, not age or lack of complications. [Fifth International Workshop, recommendations 5.1.4 and 6](https://jsbmr.umin.jp/guide/pdf/Bilezikian-2022-Evaluation-and-management-of-primar.pdf).

## Where the cases and answers are

| Artifact | Contents |
|---|---|
| [Cases](../data/multiturn/batch_q_cases.json) | Eight conversations; initial/update requirements and proposed critical errors |
| [Exact-case anchors](../config/multiturn_criterion_anchors_batch_q_v1.json) | 28 requirement positions, with met/partial/missed boundaries and acceptable equivalents |
| [Reference answers and contrasts](../data/multiturn/batch_q_contrasts_v1.json) | Eight initial references; eight strong, eight single-component-omission and eight affirmative unsafe update examples |
| [Source mappings](../data/multiturn/batch_q_provenance.json) | Every requirement bound to the case hashes, a source location, support type and unresolved review questions |
| [Offline audit](../scripts/audit_batch_q.py) / [saved result](../data/audit/s59_batch_q_authoring.json) | Structural checks, 24 judge-packet hashes and bounded source/identity overlap checks |

The strong update reference is the joined `safe_components`. The partial version deletes exactly the component identified by `partial_omitted_requirement_index`; `materialize()` implements this without changing the remaining text. That construction is reproducible, but does not prove that the omitted idea is absent by implication or establish a numeric score. The unsafe examples are separate affirmative foils, not matched single-error experiments.

Each family has three initial and four update requirements: **28 positions / 56 bilingual instances**. Both source mappings and anchors fail validation if the case content changes. Critical-error triggers require affirmative harmful advice; a missing sentence is not automatically the same error.

## Evidence and overlap

Public actual reports supply mechanisms, not imported patients or ready-made answer keys:

- IV iron: [Fang et al.](https://onlinelibrary.wiley.com/doi/10.1002/jgh3.12150), with separate [MHRA safety guidance](https://www.gov.uk/drug-safety-update/ferric-carboxymaltose-ferinject-risk-of-symptomatic-hypophosphataemia-leading-to-osteomalacia-and-fractures).
- Postoperative wound: [Wanner et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC7595358/), checked against [Japanese dermatology guidance](https://onlinelibrary.wiley.com/doi/10.1111/1346-8138.16845), [BAD patient information](https://www.bad.org.uk/pils/pyoderma-gangrenosum) and [IDSA infection guidance](https://www.idsociety.org/practice-guideline/skin-and-soft-tissue-infections/).
- Calcium differential: [Mobarak et al.](https://www.frontiersin.org/journals/surgery/articles/10.3389/fsurg.2020.00030/full), with [PARAT 2021](https://publications.aston.ac.uk/id/eprint/45969/1/eje-21-1044.pdf) and the Fifth Workshop above.
- Acquired bleeding disorder: [Gicart et al.'s PubMed abstract](https://pubmed.ncbi.nlm.nih.gov/32459605/), with [2025 BSH/UKHCDO guidance](https://onlinelibrary.wiley.com/doi/full/10.1111/bjh.70200) and [international recommendations](https://haematologica.org/article/view/9931).

Three report narratives were inspected; the fourth report was available here as an abstract only. The invented mixing-test sequence comes from independent guidance, not unseen case details. The PARAT and Fifth Workshop sections were checked in public PDF copies; the PDF workflow recovered source text when canonical HTML failed. No source narrative, image, chart, rare patient trajectory, Xi’an record or purchased raw data was copied into these prompts.

The audit inspected **152 existing family/file entries** across public development, calibration-candidate and confirmation containers, including Alpha JSONL. It found no matching report identifier or normalized source URL. This is a bounded bibliographic check, not proof of independence or lack of training contamination. The provenance file separately flags related refeeding, iron-deficiency, necrotizing-infection, endocrine-testing and hematology families, including two reserved-set relationships, for conservative future split grouping.

Exact timing, error severity and some patient-facing applications remain author judgments. The source ledger separates these from directly supported principles. The IDSA page links a correction whose text was unavailable; its relevance remains in the review queue. Global labels do not mandate a national referral number, formulary or replacement dose.

## Verification and review queue

- **25 focused tests passed**, covering case/label hashes, source coverage, status/privacy boundaries, exact omissions, report aliases, numeric EN/ZH fact alignment and candidate-only prompt exposure.
- **1,068 full-suite tests passed** in 654.794 seconds. The final O/P/Q/catalog subset also passed all 41 checks. All 496 local Markdown link targets in changed documentation resolve.
- The S57 frozen snapshot remains unchanged. The saved S58 report and numeric rules were not edited.
- [H149–H152](CLINICAL_REVIEW_HANDOFF_EN.md) record clinical/bilingual questions for the four families. H148 and all earlier questions remain open.

These checks do not validate clinical correctness, semantic independence, language equivalence or model difficulty. Approved calibration and Gold remain **0/0**. The documentation workflow keeps current counts separate from historical run results and the Chinese notes are written for Chinese readers, not mechanically mirrored prose.

## Next step

Prepare an **offline, opt-in O/P/Q pilot manifest** across the eight standalone families: balance difficult interpretation with restraint, select exact case/anchor versions, isolate initial-turn evidence, and specify the report and spending policy before proposing any paid run. Resolve source sufficiency and control-design gaps in that preparation; do not silently register all drafts or reuse S58 approval.

Continue expansion alongside this readiness work. Preserve S58's three repeat-boundary questions and medication hold without another automatic single-case diagnostic. The lower-tier 60–70, average around 80 and premium around 90 bands remain diagnostic aspirations, not quotas to enforce through labels or weights. Expert review remains deferred, not waived.
