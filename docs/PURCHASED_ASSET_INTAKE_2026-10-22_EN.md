# Raw-data handoff and case-building workflow

This is the revised handoff for the data team. **The team acquires and delivers raw, linkable material. ClinReason does the privacy checks, extraction, case writing, draft answers, evidence mapping and bilingual work.** The data team does not need to create benchmark questions or labels. The first batch is a **target of about 30 distinct clinical episodes**, not 30 PDFs and not 30 ready-to-score cases. Fewer complete episodes are more useful than many disconnected pages.

## What we need from the data team

Look for records that show a decision unfolding over time. A useful episode has the initial presentation, relevant tests and medicines, follow-up notes, and an outcome or discharge note. Aim for a mix of urgent and non-urgent situations, medication problems and diagnostic uncertainty. Prefer episodes in which new information changes the sensible next step; at least two meaningful time points are ideal. Do not select only rare or dramatic final diagnoses. We will decide which benchmark category and question, if any, each episode supports.

For each episode, provide the **original files as received**, grouped together. PDFs and scans are acceptable; searchable text, CSV, JSON or FHIR exports are even better when available. Keep lab values, units, reference ranges, medication details and chronological order intact. Include the later outcome if available, but do not turn the material into a question or tell us what the “correct” answer is.

Add a small file index so we can understand the bundle without guessing. Each row should say: a new episode ID, file path, document type (for example admission note, lab report or discharge note), language, approximate sequence or relative time, and whether the source says it is already de-identified (`yes`, `no` or `unknown`). If a file belongs to several visits for the same person, mark the linkage. A short `README.md` can explain abbreviations, units, missing files or unusual source formats. Do not put patient names or source medical-record numbers in the index.

That is the whole data-team handoff. **No answer labels, translations, guideline research, manual OCR, privacy report or case formatting are requested from the team.** If some of those already exist, send them as optional context, clearly separated from the raw records; we will still verify them ourselves.

## Simple delivery layout

```text
raw_batch_001/
  README.md                 optional notes about the collection and file formats
  file_index.csv            one row per file; links files to the same episode
  records/
    EP001/                  all original files for episode 1
    EP002/                  all original files for episode 2
    ...
```

`file_index.csv` is the only requested table. Recommended columns: `episode_id, file_path, document_type, language, sequence_or_relative_time, deid_status, notes`. A source dataset that already comes as tables can stay in CSV/JSON/FHIR rather than being converted to PDFs; put the tables under `records/` and explain their patient/encounter linkage in the index or README. Use UTF-8 for the index and text files. Preserve original source files, rather than merging them into one giant PDF. Send the bundle through the agreed secure local handoff, **not** via chat, email, Git or a model API.

For example, one index row could say `EP001,records/EP001/admission.pdf,admission note,zh-Hans,first,unknown,`. It describes the file; it does **not** contain the patient's name or any answer label.

## What ClinReason will do after receiving a batch

| Stage | Our work | What comes out |
|---|---|---|
| 1. Inventory | Count episodes, hash files, detect duplicates, check linkage and chronological gaps. | An intake report and a list of files needing clarification. |
| 2. Privacy pass | Check source claims of de-identification; inspect text, OCR, PDF metadata and images for remaining names, IDs, exact dates, locations and unusual identifying combinations. Remove or generalize identifiers while preserving clinically important intervals. Recheck the resulting text and images. | A local de-identified working copy and a recorded privacy decision. If identification risk remains, the episode stays on hold; it is not sent to external models. |
| 3. Clinical extraction | OCR scans where needed and build a structured timeline of symptoms, negatives, history, medicines, vitals, test results, interventions and outcomes. Keep page-level links and original units; manually verify facts that will affect an answer. | An evidence-linked episode summary, still not a benchmark case. |
| 4. Case and answer drafting | Pick a decision time, hide all later facts from the candidate prompt, and write an original patient-facing or professional scenario. Draft an acceptable answer range, observable must-do requirements, serious prohibited errors and uncertainty. Actual care and final diagnosis are not automatically the correct answer. | Separate English/Chinese draft questions and answer labels. |
| 5. Evidence and quality checks | Check every answer requirement against independent, current clinical guidance or drug information; review source overlap, difficulty, bilingual meaning and leakage between development/calibration/hidden groups. Run schema and benchmark validation. | Source-to-answer map, QA record and review queue. |
| 6. Later approval | Qualified clinical, language and methods reviewers assess the draft. | Only reviewed cases can advance beyond draft; no automatic Gold promotion. |

The privacy pass is our responsibility, but it is **not a promise that automated redaction alone proves anonymity**. We will keep raw and intermediate files local and restricted. A case with unresolved identity risk or an unclear permitted processing path remains on hold until the appropriate privacy decision is made. We will not expose raw scans or original clinical text to candidate or judge APIs. This reflects the need to inspect free text and images as well as obvious ID fields; see [HHS technical de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html) and [China's Personal Information Protection Law](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm) for context.

**Where outputs go:** raw material and OCR/de-identification intermediates stay in ignored, restricted local storage. Only a privacy-cleared, newly authored draft and its provenance can be proposed for the benchmark dataset. Existing [single-turn](../schemas/case.schema.json) and [multi-turn](../schemas/multiturn-pilot.schema.json) schemas are conversion targets, not formats the data team must prepare. An episode and all its language variants remain in one split to prevent leakage. No real patient text is copied into the public Alpha.

## Starting with the three folders already here

- `ClinicalDataXiAn` is the first processing pilot. Its 50 image-only PDFs (90 pages) appear to represent **one linked hospital episode**, not 50 cases. We should inventory, group, OCR and run the privacy pass locally before drafting a decision-point question. The admission, progress, laboratory, other-report, surgery, pathology and discharge files are the useful sequence; consent and risk forms may provide context but are less likely to become question facts.
- `2.Usmle world step2` has 68 PDFs (about 57,687 pages). Its case-style questions may help us find hard reasoning patterns and coverage gaps, but copied or lightly paraphrased items can be familiar to models. If we use them, we will deduplicate, write genuinely new prompts and independently verify answer labels.
- `4.Usmle world step1` has 283 PDFs plus eight archives (about 51,166 PDF pages). It is lower priority for patient-facing decision cases; it can help with a basic-science coverage map.

This batch has **not** been converted into cases or sent to a model. The raw `purchasedAssets/` folder remains Git-ignored. The [S23 scoring-boundary hold](S23_OFFLINE_SCORING_BOUNDARIES_2026-10-22_EN.md) is unaffected; acquired records cannot by themselves settle disputed scoring ratings.
