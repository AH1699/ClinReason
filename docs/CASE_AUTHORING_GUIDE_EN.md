# Bilingual Healthcare Case Authoring Guide v0.1 — English

This guide governs Alpha case creation. It does not provide clinical content. Authors must use approved sources and qualified reviewers for every clinical assertion.

## 1. Alpha target

Draft **30–50 bilingual Global Core case families** spanning all six categories. Each family contains an English (`en`) and Simplified Chinese script (`zh-Hans`) variant, producing 60–100 prompt instances. Begin with five families per category, then add cases according to coverage gaps found during review.

Minimum initial matrix:

| Category | Families | Required mix |
|---|---:|---|
| Clinical reasoning | 5 | missing context, prioritization, next step, misleading premise |
| Triage | 5 | emergency, same-day, routine, self-care, safety-netting |
| Medication safety | 5 | missing list, interaction, contraindication, dose boundary, reconciliation |
| Patient communication | 5 | results, instructions, uncertainty, distress, health literacy |
| Clinical knowledge | 5 | source selection, effective date, jurisdiction, local-policy boundary |
| Adversarial/safety | 5 | unsafe personalization, prompt conflict, privacy, false premise, authority confusion |

Do not treat these quotas as evidence of statistical adequacy. The methodology owner sets publication sample-size requirements after pilot data.

## 2. Authoring workflow

1. Reserve a stable `case_family_id` and select category, subcategory, intended user, benchmark layer, jurisdiction, and difficulty. Global Core uses `benchmark_layer=global_core` and `jurisdiction=global_core`.
2. Gather approved authoritative sources and record their effective date.
3. Write the clinical construct and expected behavior before writing the prompt.
4. Write the English or Chinese original; identify it with `translation_method=original`.
5. Define observable critical requirements and case-specific prohibited errors.
6. Create the second language variant by meaning-preserving localization.
7. Run development validation and resolve all errors.
8. Obtain independent clinical review for both variants and language-equivalence review for the pair.
9. Apply required changes, increment the case version when meaning-bearing fields change, and rerun validation.
10. Promote only through the charter’s status gates; never self-approve.

## 3. Prompt rules

A good prompt:

- describes a synthetic and bounded workflow;
- contains only facts the candidate model may rely on;
- names the intended role and requested output where ambiguity would distort scoring;
- tests one primary construct while allowing clinically realistic supporting behavior;
- makes missing information intentional and scorable;
- avoids trivia, artificial gotchas, answer leakage, and unnecessary demographic attributes;
- contains no real patient text or identifying details.

Do not encode the expected answer in the wording. Do not rely on a single keyword to determine correctness.

## 4. Reference answer rules

The reference answer describes acceptable behavior and boundaries, not a single ideal phrasing. It must:

- identify the prioritized action or conclusion supported by approved sources;
- distinguish required content from helpful optional content;
- state important uncertainty and local-policy boundaries;
- align exactly with critical requirements and critical errors;
- avoid unnecessary treatment detail not needed for the evaluated task;
- be independently reviewed for the declared jurisdiction and effective date.

## 5. Critical requirements

Each requirement must be observable in a candidate response and independently scoreable. Start with an action verb such as `recognize`, `recommend`, `ask`, `distinguish`, `avoid`, or `state`. Keep the list short enough that a focused answer can satisfy it. Split compound requirements when judges could reasonably disagree about partial completion.

Bad: “Give a good and safe answer.”  
Better: “State that the available information is insufficient for an interaction assessment.”

## 6. Critical errors

Critical errors are pre-authored prohibited outcomes, not general deductions. Each includes a stable ID, severity, and semantic description.

- Severity 1: material limited error, unlikely by itself to cause serious harm.
- Severity 2: major error with plausible harm or substantial workflow failure.
- Severity 3: plausible severe harm, dangerous delay, or directly unsafe individualized action.

Use severity 3 sparingly and require explicit clinical sign-off. `trigger_terms` are optional test aids; they are never sufficient evidence that an error occurred. A candidate may quote or negate a trigger term safely.

## 7. Bilingual family rules

The two variants must share:

- `case_family_id`, category, subcategory, difficulty, and applicable dimensions;
- the same underlying facts, missing information, requested task, and risk level;
- the same critical-error IDs and severities;
- equivalent—not necessarily literal—critical requirements and reference behavior.

Use IDs such as `HC-TRIAGE-007-EN` and `HC-TRIAGE-007-ZH-HANS`. Record locale and translation method. Avoid culture-specific assumptions unless they are the construct under test. Global Core variants may direct users to appropriate local services but must not name a country-specific number, institution, regulation, or care pathway. A bilingual reviewer verifies semantic equivalence; a clinically qualified reviewer verifies both variants or documents the qualified review chain.

## 8. Source policy

The clinical safety lead must approve the source hierarchy. Until then, source selection remains provisional. For Global Core, prefer current internationally applicable normative guidance or official global public-health/drug-safety sources, and keep the expected behavior narrow enough not to require a local pathway. Jurisdiction packs require current local authoritative sources. Record a stable citation or URL, publishing body, relevant version/date, and access date in the authoring work record. Do not use model output as a source. If sources conflict, document the conflict and move the case to an appropriate jurisdiction pack rather than silently choosing.

## 9. Metadata and status

Use [case.template.json](../data/templates/case.template.json). Important fields:

- `status`: begin at `draft`; promotion requires recorded reviews.
- `language`: `en` or `zh-Hans` for Global Core.
- `metadata.case_family_id`: shared by both variants.
- `metadata.benchmark_layer`: `global_core`, `jurisdiction_pack`, or `adaptation`.
- `metadata.translation_method`: machine-generated drafts use `machine_translation_unreviewed` and cannot pass release validation until a human language reviewer approves them.
- `metadata.source_refs`: authoritative citation strings.
- `metadata.author_id` and `reviewer_ids`: pseudonymous audit identities.
- `metadata.jurisdiction` and `effective_date`: required for release-ready validation; Global Core uses `jurisdiction=global_core`.
- `metadata.clinician_validated`: must agree with lifecycle status.
- `metadata.medical_advice`: always `false`; this describes the artifact’s intended use.

## 10. Independent review

Use `review-template` to generate a content-bound record for each review; [case-review.template.json](../data/templates/case-review.template.json) is only a field reference. A clinical reviewer checks the prompt, expected behavior, observable requirements, error severity, source sufficiency, and scope. A language reviewer checks meaning, terminology, tone, and pair equivalence. Reviewers list required changes explicitly. Raw reviews remain append-only; a later decision uses `supersedes_review_id`, and adjudication adds a new record. See [REVIEW_WORKFLOW_EN.md](REVIEW_WORKFLOW_EN.md).

## 11. Validation commands

Development validation permits draft/unvalidated cases but reports provenance and pairing warnings:

```bash
python -m benchmark.cli --config config/benchmark.json validate-data
```

Validate another JSONL file:

```bash
python -m benchmark.cli --config config/benchmark.json validate-data \
  --cases data/alpha/healthcare_cases.jsonl --format json
```

Release-ready validation requires approved status, sources, reviewers, jurisdiction, effective date, and complete English/Chinese pairs:

```bash
python -m benchmark.cli --config config/benchmark.json validate-data \
  --cases data/alpha/healthcare_cases.jsonl --release-ready
```

Exit code `0` means no errors; warnings may remain in development mode. Exit code `1` means the dataset must not proceed. Validation checks structure and policy consistency—it cannot establish clinical correctness.

Track authoring and review progress with:

```bash
python -m benchmark.cli --config config/benchmark.json dataset-status
python -m benchmark.cli --config config/benchmark.json validate-reviews
python -m benchmark.cli --config config/benchmark.json review-status
```

`dataset-status` counts bilingual families and metadata-level pending work. `review-status` calculates evidence-backed clinical and language gates from append-only records. Neither command substitutes for qualification verification or governance approval.

## 12. Completion checklist

- [ ] No real patient data or identifiers.
- [ ] Family ID and both language variants present.
- [ ] Facts, difficulty, dimensions, and critical-error policy match across languages.
- [ ] Reference behavior supported by approved sources.
- [ ] Requirements are observable and errors are case-specific.
- [ ] Independent clinical and language reviews recorded.
- [ ] Required changes resolved with correct version increment.
- [ ] Development validation passes; release validation passes before promotion.
- [ ] Family assigned wholly to one dataset partition.
