# Data-team acquisition brief — plain-language version

**The goal:** bring us real clinical evidence from which we can *draft* challenging bilingual benchmark cases. We need complete, permissioned clinical stories and a proposed answer key—not a pile of PDFs or copied exam questions. This is a request for a **30-episode pilot**, not a purchase authorization or a claim that 30 cases will be ready to score.

## What to acquire first

Ask for **30 different patient episodes**: 10 with an evolving triage decision, 10 with a medication-safety decision, and 10 with a diagnostic-reasoning decision. An episode is one person's linked care journey; its admission note, tests, operation note and discharge summary still count as **one** episode. At least 20 episodes should have two meaningful moments when the right next action might change.

Choose a mix of ordinary and serious outcomes. Look for cases where the model must weigh changing symptoms, competing explanations, missing information, test results that do not neatly agree, other illnesses, or multiple medicines. A rare diagnosis alone does not make a good case. Include age groups and pregnancy/postpartum settings only where the team can obtain the right permissions and later specialist review.

For each episode, ask the supplier for four things:

1. **Proof we may use it.** The actual owner of the material must permit our intended commercial benchmark use. The permission should say whether we may adapt cases, translate them into English and Chinese, show them to reviewers, send de-identified prompts to named model providers, and publish prompts, labels or results. Ask for restrictions, expiry and deletion terms. A reseller invoice or ordinary exam-bank subscription is not enough evidence of these rights.
2. **A privacy-cleared record.** The data controller should de-identify the record and document how it checked names, dates, free text, scans and embedded images. It must approve the planned processing and transfer route. Keep original identifiers and the identity crosswalk with the controller; do not send them to us. Use relative time such as “six hours after arrival” in the delivered record.
3. **A linked timeline, not just scans.** Summarize what was known at each moment: symptoms and important negatives; relevant history, allergies and medicines; vital signs; tests with values, units and reference ranges; imaging/pathology interpretations; treatments; and later outcome. Mark uncertain or missing facts. Keep the original units and, if helpful, add standardized units beside them. Each extracted fact should point back to a source document and page; manually check OCR facts used to write the answer key.
4. **A proposed question and answer key.** For each decision moment, show exactly what the tested model would see *then*. Keep later tests, diagnosis and outcome hidden until a later turn. State the safe range of acceptable answers, a short list of observable must-do actions, serious actions the model must avoid, and plausible alternatives. Link each proposed answer requirement to an independent, current guideline or drug label. What the treating team actually did is part of the record, **not automatically the correct answer**.

Please draft both English and Simplified Chinese versions, preserving the same facts and risk level. Mark all answer keys **draft**. Clinical, language and methods reviewers will decide later whether any key can be approved; machine translation alone is not approval.

## Delivery layout

One folder is enough. These are the files we want; the names are suggestions, so a team with an existing export format can map it to the same contents.

```text
delivery/
  README.md                 how this batch was prepared; column/field explanations
  permissions.csv           one row per source: owner, permission proof, allowed uses, limits
  episodes.jsonl            one row per patient episode: de-identified linked timeline
  decision_points.jsonl     one row per proposed question/turn and language: facts visible then
  answer_labels.jsonl       separate draft answer key for each question/turn and language
  evidence.csv              each must-do answer requirement and the source supporting it
  review_status.csv         rights, privacy, OCR, clinical and language check status
  privacy_report.pdf        de-identification method, reviewer and remaining restrictions
  source_docs/               original records; send separately by an approved secure route
```

**How to choose a format:** use UTF-8 CSV for simple tables (it opens in Excel) and UTF-8 JSONL for records with a changing timeline or several facts per case (one complete record per line). If labs or medicines are too large to keep clearly in `episodes.jsonl`, add `observations.csv` and `medications.csv` with the same episode IDs. Include a data dictionary in `README.md`. Use stable, made-up IDs to link files; do not use patient, hospital or original document IDs as case IDs. The prompts in `decision_points.jsonl` must never include `answer_labels.jsonl` content or facts learned only later.

For every entry in `permissions.csv`, record at least the source, original rightsholder/data controller, written-proof location, allowed commercial/adaptation/translation/model-API/publication uses, geographic scope, expiry and restrictions. Use **yes / no / unknown** for each use; `unknown` means **hold**. For each label, record the decision-point ID, language, acceptable answer, must-do actions, serious errors, evidence IDs, unresolved questions and review status. For each evidence item, record publisher, title, version/date, link or DOI, relevant section, applicable population/jurisdiction and limitations. This lets us convert accepted drafts into the project's [case schema](../schemas/case.schema.json) or [multi-turn schema](../schemas/multiturn-pilot.schema.json) without losing provenance.

## What we can do with the three folders already here

- **`ClinicalDataXiAn`: start here for a *single* pilot episode after permission and privacy clearance.** Its 50 image-only PDFs (90 pages) appear to be one linked hospital journey, not 50 independent cases. The most useful documents to join are `入院记录.pdf`, `病程记录.pdf`, `其他报告单*.pdf`, `常规化验报告单*.pdf`, `手术记录单*.pdf`, `病理报告.pdf` and `出院记录_死亡记录.pdf`. OCR and verify them inside the approved environment; send only the cleared, structured extract.
- **`2.Usmle world step2`: possible later source, subject to actual rightsholder permission.** It has 68 PDFs (about 57,687 pages / 16 GB). `Cardiovascular.pdf` contains case-style material; `UW - Objectives - System - ALL.pdf` is useful as a topic list. Some files are screenshots. Do not copy or paraphrase questions into this benchmark while rights remain unverified.
- **`4.Usmle world step1`: lower priority.** It has 283 PDFs and eight archives (about 51,166 PDF pages / 14 GB). If rights are established, use it to check basic-science topic coverage rather than to populate patient-facing cases.

No rights paperwork was found inside these folders. That does not prove the team's purchase is invalid, but we need evidence that the grantor can license *these* files for *these* uses. Some exam files show redistribution indicators; [standard UWorld terms](https://www.uworld.com/terms_conditions.aspx) restrict commercial copying. The Xi'an scans have blank ID fields but also exact dates and image content, so blank fields alone do not establish anonymity. Have a qualified privacy/legal reviewer address the applicable rules, including [China's Personal Information Protection Law](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm). [HHS de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html) is a useful technical reference, not a substitute for China-law review.

**Acceptance rule:** do not put raw scans or purchased questions into `data/alpha/`, Git, or candidate/judge model APIs. One episode enters internal case authoring only after permission, privacy, deduplication, OCR, decision-time leakage and source-to-answer checks pass. It is still a draft until qualified review. The raw `purchasedAssets/` folder is Git-ignored; this scan imported no purchased content and changed no scores. The [S23 scoring-boundary hold](S23_OFFLINE_SCORING_BOUNDARIES_2026-10-22_EN.md) remains in effect.
