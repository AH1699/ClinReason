# Healthcare/Clinic LLM Benchmark Design v0.1

Status: planning scaffold; not clinically validated  
Audience: product, evaluation, engineering, clinical safety, and governance teams  
Positioning: frontier LLM-as-a-judge first; hybrid after calibration; optional distilled open-source evaluator only when justified

## 1. Executive decision

Start with a small, high-quality benchmark evaluated by two diverse frontier-model judges and sampled human review. The scarce resource is trustworthy domain judgment—not inference. Use the first cycles to refine cases, rubric anchors, and adjudication. After a human-labeled Gold Set exists, route easy/high-agreement items to a cheaper evaluator and reserve frontier judges plus experts for risky or ambiguous items. Distill an open-source evaluator only when volume, privacy, reproducibility, or unit economics justify its training and maintenance cost.

The v0.1 architecture separates:

1. a sector-neutral evaluation engine;
2. healthcare-specific case content and critical-error policy;
3. candidate-model adapters;
4. judge-model adapters;
5. immutable run/version metadata;
6. human review and adjudication.

This makes a later finance or legal module a content-and-policy extension rather than a rewrite.

## 2. Purpose and non-goals

### Purpose

- Measure whether an LLM response is correct, safe, appropriately escalated, complete, relevant, understandable, and calibrated for clinic workflows.
- Expose failure modes hidden by medical multiple-choice tests, especially dangerous delay, unsupported personalization, invented policies, and weak uncertainty handling.
- Support repeatable comparisons across models and versions.
- Generate high-quality labels that can later calibrate routing or train a smaller evaluator.

### Non-goals for v0.1

- Clinical deployment, certification, or proof of safety.
- Automated diagnosis or treatment recommendations.
- Claims of population-wide medical competence.
- Training an evaluator or candidate model.
- Use of real PHI/PII.
- A public leaderboard before validation, contamination review, and statistical analysis.

## 3. Intended-use statement

The benchmark evaluates text-model behavior in simulated healthcare/clinic workflows. It is for research, quality assurance, and model selection under documented conditions. It is not a clinical decision-support system and its examples are not medical advice. Passing a benchmark does not establish clinical safety, regulatory compliance, or fitness for a specific use.

Every release must state jurisdiction, intended user, supported languages, evaluated model snapshots, known exclusions, validation status, and effective dates of source guidance.

## 4. Operating principles

- **Safety dominates style.** A polished answer with a dangerous disposition fails.
- **Case-level requirements are explicit.** Judges compare against observable requirements and prohibited errors, not vague impressions.
- **Do not reward verbosity.** Completeness means necessary coverage without harmful excess.
- **Separate model failure from case failure.** Ambiguous or outdated cases can be excluded during adjudication.
- **Version everything.** Cases, dataset, rubric, prompts, models, parameters, code, and source guidance are independently identifiable.
- **Human authority remains explicit.** Automated judges triage review effort; they do not certify clinical correctness.
- **Report uncertainty.** Publish confidence intervals and coverage, not only a single leaderboard number.

## 5. Benchmark composition

The target MVP is 300–500 cases. Recommended initial allocation:

| Category | Target share | Core behavior |
|---|---:|---|
| Clinical reasoning | 20% | Gather evidence, prioritize plausible explanations, select safe next steps |
| Triage and escalation | 20% | Choose urgency, destination, timing, and safety-netting |
| Medication safety | 15% | Interactions, contraindications, missing context, dosing boundaries |
| Patient communication | 15% | Plain-language explanation, empathy, teach-back, actionable guidance |
| Clinical knowledge | 15% | Guideline-grounded knowledge with jurisdiction and date awareness |
| Adversarial/safety | 15% | Conflicting instructions, unsafe requests, false premises, prompt injection |

Balance each category by difficulty, care setting, task form, demographic context, language, answer length, and whether abstention or clarification is correct. Suggested format mix is roughly 80% open-ended scenarios and 20% objective/structured items. A separate hidden Gold Set should cover high-risk and boundary cases disproportionately.

## 6. System architecture

```text
versioned cases -> candidate adapter -> stored response
                                      -> judge A --\
                                      -> judge B ----> aggregation/gating -> report
                                      -> pairwise ----/
                                               |
                                    review triggers -> expert adjudication
                                               |
                                         locked Gold Set
```

SQLite is sufficient for the MVP. Store normalized identifiers and JSON payloads so schemas can evolve. Keep raw provider responses in access-controlled object storage for production; the scaffold stores parsed payloads only. Batch/API execution, dashboards, and distributed queues are deliberately out of scope.

### Provider abstraction

Candidate adapters accept a case and return text plus usage/latency metadata. Judge adapters accept a case, response, and rubric and return a schema-constrained judgment. Pairwise evaluation is optional. Provider-specific authentication, request formatting, retries, and structured-output repair live behind these interfaces.

## 7. Evaluation flow

1. Validate and freeze the case version.
2. Create a run manifest with all model/prompt/parameter/code versions.
3. Generate candidate answers under identical case presentation and controlled decoding.
4. Blind model identity from judges where technically possible.
5. Obtain two independent absolute judgments from diverse model families/providers.
6. Aggregate dimension scores by median and renormalize weights over applicable dimensions.
7. Apply critical-error rules after the raw score.
8. Calculate confidence and review triggers.
9. Send disagreements, hard failures, low-confidence cases, and a random audit sample to qualified humans.
10. Lock adjudicated labels separately from development data.
11. Report category results, safety failures, uncertainty, and exclusions alongside the overall score.

## 8. Judge strategy roadmap

### Stage A — frontier judges

The target design uses two strong, diverse judges with a strict JSON schema and low-variance settings **where the selected API supports them**. The current Gemini pilot sends no temperature or seed and uses only one judge; it does not meet that target. Benefits are fast iteration and high instruction understanding. Risks include provider drift, self-preference, verbosity bias, shared blind spots, and cost. Mitigate with pinned snapshots where available, blind identities, independent calls, actual request-parameter logs, Gold Set calibration, and expert sampling.

### Stage B — hybrid routing

After Gold Set calibration, use a cheaper model or deterministic checks for low-risk, high-confidence cases. Route to frontier judges when the small evaluator is uncertain, cases are high risk, output parsing fails, judges disagree, or a critical error may exist. Continue random human audits to detect drift.

Example routing policy:

- deterministic validation for schema and exact requirements;
- low-cost evaluator when calibrated confidence is at least 0.85 and no safety flag appears;
- two frontier judges for safety-sensitive or uncertain cases;
- human adjudication for unresolved critical errors, material disagreement, or sampled audits.

### Stage C — optional distilled/open evaluator

Train only when there is a sufficiently large, diverse, adjudicated label set and a stable rubric. Preserve train/calibration/test isolation at the case-family level. Evaluate calibration, subgroup errors, critical-error recall, distribution shift, and robustness—not just correlation with teacher scores. The distilled model must never be evaluated only against its own teacher.

Decision triggers may include sustained volume, privacy/on-premises requirements, a need for immutable evaluator weights, and demonstrated total-cost savings after engineering and maintenance.

## 9. Cost controls

- Develop on 30–50 cases, calibrate on about 100, and run the full set only after prompt/rubric freeze.
- Cache by hash of case, response, judge model snapshot, rubric, and judge prompt.
- Use concise reference answers and requirement lists.
- Rejudge only affected cases when a case or rubric component changes.
- Use two judges on safety-relevant cases; use calibrated sampling for low-risk regression checks.
- Track tokens, latency, retries, parse failures, and cost per response/judgment.
- Keep human effort focused on Gold Set creation, disagreements, critical errors, and random audits.

Do not reduce cost by using a single uncalibrated judge or by silently replacing a model snapshot.

## 10. Human validation and Gold Set

### Required clinician workflow

Each healthcare case must be reviewed by at least two appropriately scoped clinicians. Review includes prompt realism, reference answer, requirements, critical errors and severity, rubric applicability, jurisdiction, source quality, and effective date. A third qualified adjudicator resolves material disagreement. Reviewers should not see model identity.

### Gold Set construction

1. Define eligibility and exclusion criteria before selection.
2. Sample across categories, risk, difficulty, language, and protected-context slices.
3. Avoid near-duplicate leakage between development and Gold Set partitions.
4. Obtain independent human scores and critical-error labels.
5. Adjudicate disagreements and document the rationale.
6. Measure agreement before adjudication; set launch thresholds in advance.
7. Lock case content, labels, and hashes; restrict access.
8. Refresh on a scheduled cadence or when guidelines materially change.

Suggested pre-release thresholds to finalize with the clinical lead: critical-error sensitivity of the automated judge at least 0.95 on the Gold Set; weighted agreement with adjudicated human dimension scores at least 0.80; and no unresolved severity-3 labeling dispute. These are planning proposals, not validated standards.

## 11. Governance, privacy, and security

- Use synthetic or properly de-identified cases in v0.1; prohibit PHI by policy and automated scanning.
- Apply data minimization, access control, retention limits, encryption, and audit logs before real data is considered.
- Record conflicts of interest and reviewer qualification scope.
- Maintain a case withdrawal process for flawed, outdated, or contaminated items.
- Treat candidate outputs as potentially unsafe content and judge rationales as untrusted model output.
- Protect hidden cases against leakage; rotate compromised items.
- Complete applicable legal, privacy, security, and regulatory review before deployment or publication.

## 12. Reporting

Report at minimum:

- sample size and coverage by category;
- mean/median absolute score with bootstrap confidence intervals;
- pass rate and severity-2/3 critical-error rate;
- dimension and category scores;
- human-review rate and judge-disagreement rate;
- excluded/quarantined cases and reasons;
- model and judge snapshots, prompts, rubric, dataset, and code versions;
- latency and cost, when measured;
- limitations and validation status.

Avoid rank claims when intervals overlap materially. Do not average away a severe safety failure. Pairwise ranking may supplement, but never replace, absolute safety criteria.

## 13. MVP phases before deployment

### Phase 0 — charter and controls (week 1)

Define intended use, benchmark layers, users, exclusions, risk taxonomy, data rules, clinical lead, decision rights, and release criteria. The v0.2 Alpha begins with `jurisdiction=global_core`; local jurisdictions are added as separate packs. Output: approved benchmark charter and risk register.

### Phase 1 — specification and 30–50-case alpha (weeks 2–3)

Finalize taxonomy, anchors, schemas, authoring guide, source policy, and review forms. Clinicians review the alpha set. Output: rubric v0.2, adjudicated alpha cases, known-ambiguity log.

### Phase 2 — technical alpha and judge calibration (weeks 3–5)

Implement real provider adapters, schema validation, retries, cost logs, blinding, and run manifests. Compare two frontier judges with human labels; test bias and prompt sensitivity. Output: calibration report and frozen judge prompt candidate.

### Phase 3 — 300–500-case MVP and Gold Set (weeks 5–9)

Author and dual-review cases; adjudicate and partition by case family. Lock a hidden Gold Set. Output: dataset v0.9, Gold Set v0.1, data sheet, inter-rater analysis.

### Phase 4 — pre-deployment validation (weeks 9–11)

Run candidate models, perform repeatability and sensitivity checks, bootstrap intervals, subgroup/failure analysis, security/privacy review, and red-team tests. Output: validation report and go/no-go decision.

### Phase 5 — limited pilot, not clinical use (weeks 12+)

Use the benchmark for internal model selection only. Monitor judge drift, costs, guideline changes, and leakage. Start hybrid routing only if Gold Set performance supports it.

No phase authorizes clinical deployment. That requires a separate product safety and regulatory process.

## 14. Extension to finance and legal

Reuse the case, response, judgment, review, score, run, and version schemas. Replace domain taxonomy, authoritative-source policy, expert qualifications, critical-error catalog, and dimension names where needed. For finance, add suitability, numerical accuracy, timeliness, and market-data provenance. For legal, add jurisdiction, authority hierarchy, procedural posture, citation validity, and unauthorized-practice boundaries. Keep the core 0–4 anchor philosophy and critical-error gating so cross-sector operations remain consistent without pretending scores are directly comparable.

## 15. Open decisions

- Global Core workflow boundary and criteria for selecting later jurisdiction packs.
- Languages in the validated release.
- Exact human agreement metrics and launch thresholds.
- Public vs private cases and leaderboard policy.
- Reference-source hierarchy and guideline refresh cadence.
- Whether category weights should reflect prevalence, risk, or a fixed balanced panel.
- Vendor/model snapshot availability and data-retention terms.
- Ownership, license, and external publication policy.

## 16. Pre-deployment exit checklist

- [ ] Intended-use and exclusion statements approved.
- [ ] Every released case clinician-validated and source-dated.
- [ ] Gold Set locked, separated, and independently adjudicated.
- [ ] Judge calibration meets predefined thresholds.
- [ ] Critical-error recall and false-negative review completed.
- [ ] Reproducibility manifest generated for every run.
- [ ] Privacy, security, legal, and clinical governance reviews completed.
- [ ] Statistical uncertainty and limitations included in reports.
- [ ] Rollback, case withdrawal, and guideline-refresh processes tested.
- [ ] No output is described as medical advice or clinical certification.
