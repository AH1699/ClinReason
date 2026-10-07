# Case review records

Store append-only case-content review records here when qualified reviewers begin work. Prefer the CLI-generated template because it binds the review to the exact case content hash:

```bash
python -m benchmark.cli --config config/benchmark.json review-template \
  HC-GC-TRIAGE-001-EN \
  --review-type clinical \
  --reviewer-id reviewer_clinical_01 \
  --role clinician \
  --qualification-scope "Relevant verified clinical scope" \
  --jurisdiction-scope global_core \
  --output data/reviews/development/HC-GC-TRIAGE-001-EN.clinical.json
```

The generated record defaults to `decision=revise` and is not an approval. The reviewer must complete every applicable check, disclose conflicts, document requested changes, and set the final decision. Validate all records and inspect gate status with:

```bash
python -m benchmark.cli --config config/benchmark.json validate-reviews
python -m benchmark.cli --config config/benchmark.json review-status
```

Recommended layout:

```text
data/reviews/development/     Reviews visible to benchmark authors
data/reviews/adjudication/    Resolution records for documented disagreements
```

Hidden Gold labels should not be committed to this repository. Keep them in a separately access-controlled store and reference only opaque review IDs in release manifests.

Review records are immutable. If a reviewer revises a decision, add a new record with a unique ID and `supersedes_review_id`; do not edit or delete the original. The latest valid record from the same reviewer for the same case version and review type controls that reviewer’s current decision.

Do not mark a case `clinician_validated` merely because a file exists here. Only a valid `approve` decision can clear a gate. `approve_with_changes`, `revise`, `reject`, and `needs_specialist` remain unresolved until a later valid approval. Apply the charter’s independence, qualification, conflict-disclosure, required-change, and adjudication rules before promotion.
