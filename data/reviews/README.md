# Case review records

Store append-only case-content review records here when qualified reviewers begin work. Use `data/templates/case-review.template.json` and validate records against `schemas/case-review.schema.json`.

Recommended layout:

```text
data/reviews/development/     Reviews visible to benchmark authors
data/reviews/adjudication/    Resolution records for documented disagreements
```

Hidden Gold labels should not be committed to this repository. Keep them in a separately access-controlled store and reference only opaque review IDs in release manifests.

Do not mark a case `clinician_validated` merely because a file exists here. Apply the charter’s independence, qualification, conflict-disclosure, required-change, and adjudication rules first.
