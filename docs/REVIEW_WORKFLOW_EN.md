# Case Review Workflow v0.2 — English

This workflow turns expert review into auditable release evidence. It supports clinical and bilingual quality control; it does not automate clinical judgment or certify a benchmark by itself.

## 1. Review gates

For the current Alpha policy, every case requires one valid independent clinical approval. Every translated variant also requires one valid language-equivalence approval. These are minimum development gates, not a final Gold Set standard. Gold construction should use dual independent review and adjudication under a separately approved protocol.

An approval counts only when the record:

- targets an existing case ID and exact semantic version;
- contains the canonical SHA-256 hash of the unchanged reviewable case content;
- uses a reviewer role permitted for the review type;
- is independent of the recorded case author;
- completes the checks required for that review type;
- explicitly records `conflict_disclosed=false`; a disclosed conflict does not count as an independent approval;
- has `decision=approve` and no unresolved required changes;
- passes `validate-reviews` without an error.

The presence of a file, a named reviewer, or `approve_with_changes` does not clear a gate.

## 2. Roles and allowed review types

| Review type | Allowed roles | Minimum approval checks |
|---|---|---|
| Clinical | clinician, pharmacist, domain expert | prompt, reference, requirements, critical errors, sources, and scope |
| Language equivalence | language reviewer, domain expert | language equivalence and scope |
| Methodology | domain expert, adjudicator | requirements, critical errors, and scope |
| Adjudication | adjudicator | scope plus written resolution |

The project must verify real qualifications outside the repository. Role labels are audit metadata, not credential verification.

## 3. Create a content-bound record

Generate the record from the configured dataset rather than copying the static example:

```bash
python -m benchmark.cli --config config/benchmark.json review-template \
  HC-GC-TRIAGE-001-EN \
  --review-type clinical \
  --reviewer-id reviewer_clinical_01 \
  --role clinician \
  --qualification-scope "Verified scope relevant to this case" \
  --jurisdiction-scope global_core \
  --output data/reviews/development/HC-GC-TRIAGE-001-EN.clinical.json
```

The generated file is deliberately non-approved. The reviewer evaluates the case, completes the checks, records conflicts and notes, and selects a decision. If reviewable content changes—even without a version change—the stored hash becomes stale and the review cannot clear a gate. Meaning-bearing changes must also increment the case version. Lifecycle fields that are updated only after approval—status, validation flags, reviewer IDs, translation-review state, and change rationale—are excluded from the hash so controlled promotion does not invalidate its own evidence.

The generated `conflict_disclosed` value is `null`. The reviewer must set it to `false` to declare no conflict or `true` to disclose a conflict. A conflicted approval is rejected by validation.

## 4. Decisions

- `approve`: all required checks pass and no required changes remain.
- `approve_with_changes`: the listed changes are mandatory; the gate remains open.
- `revise`: material revision is needed before re-review.
- `reject`: the case should not proceed in its current construct.
- `needs_specialist`: the current reviewer cannot safely resolve the question within their scope.

Requested changes should be observable and specific. Do not encode sensitive reviewer identity or patient information in the record.

## 5. Append-only corrections

Never edit a completed record. Create a new record with a new ID and set `supersedes_review_id` to the earlier review. For the same reviewer, case version, and review type, the chronologically latest valid record controls that reviewer’s current decision. The original remains part of the audit trail.

When reviewers disagree, preserve each independent record and add an adjudication record. Adjudication must explain the resolution; it must not erase the disagreement.

An active `approve_with_changes`, `revise`, `reject`, or `needs_specialist` decision from any clinical or language reviewer keeps that case's corresponding gate open, even when another reviewer approves. A later review from the same reviewer can supersede that decision after the issue is resolved.

## 6. Prepare reviewer packets

```bash
python -m benchmark.cli --config config/benchmark.json export-review-packets
```

This writes 12 bilingual family packets and an assignment manifest under `work/reviewer_packets/` for the current Alpha. Each packet includes both prompts, expected behavior, critical requirements and errors, source references, author IDs, and content hashes. The manifest has empty reviewer ID fields for assignment. The command requires a clean development validation result, refuses to overwrite existing output, and refuses to export Gold cases. Keep the packets under controlled access when actual reviewers are assigned; they contain reference answers.

## 7. Validate and monitor

```bash
python -m benchmark.cli --config config/benchmark.json validate-reviews
python -m benchmark.cli --config config/benchmark.json review-status
```

`validate-reviews` checks structure, timestamps, duplicate IDs, supersession references, case identity/hash, independence, role authorization, and decision consistency. `review-status` calculates effective approvals and lists the clinical and language queues. Use `--format json` for automation.

Review validation is separate from dataset validation:

```bash
python -m benchmark.cli --config config/benchmark.json validate-data
python -m benchmark.cli --config config/benchmark.json validate-data --release-ready
```

Release-ready CLI validation first checks the case structure and lifecycle fields, then verifies current review evidence. It requires all active clinical and language gates to be complete, `metadata.reviewer_ids` to include the clinical approvers, and `metadata.translation_reviewer_id` to name an approving language reviewer for translated variants. Use `--reviews PATH` to check a separate review directory. The standalone `validate_dataset()` library function checks only dataset structure and metadata; use the CLI for the combined release check.

Passing review gates makes a case eligible for controlled promotion; it does not mutate case metadata or status. An accountable maintainer must verify required changes are resolved, update reviewer IDs and translation metadata, advance status/version as appropriate, and rerun both validation systems.

## 8. Promotion checklist

- [ ] Reviewers' qualifications and conflicts were verified outside the repository.
- [ ] Clinical approval exists for each exact case revision.
- [ ] Language-equivalence approval exists for every translated variant.
- [ ] All requested changes were resolved in a new case version where required.
- [ ] Any disagreement has an append-only adjudication record.
- [ ] `validate-reviews` and development `validate-data` both pass.
- [ ] Case metadata accurately names reviewers and translation method.
- [ ] Release-ready validation passes before inclusion in a release manifest.
