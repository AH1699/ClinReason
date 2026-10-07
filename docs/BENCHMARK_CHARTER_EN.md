# Healthcare/Clinics Benchmark Charter v0.1 — English

Status: **draft for approval**  
Date: 2026-10-06  
Applies to: SectorBench Healthcare/Clinics Alpha

This charter defines what the benchmark is allowed to measure and how it may be used. It is an evaluation-governance document, not medical guidance or authorization for clinical deployment.

## 1. Mission

Measure whether general-purpose and healthcare-oriented language models can respond safely, correctly, and clearly in synthetic clinic-facing workflows. The benchmark prioritizes harmful-failure detection over leaderboard optimization and supports controlled internal model selection, research, and evaluator calibration.

## 2. Intended use

Allowed during the alpha:

- internal research and engineering evaluation;
- comparison of candidate-model behavior on fixed synthetic cases;
- calibration of automated judges against independent expert labels;
- study of English/Simplified Chinese performance parity;
- development of case-authoring, review, scoring, and audit methods.

Any external score claim requires the release gates in section 10. Alpha results must be labeled `unvalidated`.

## 3. Prohibited and excluded use

The benchmark must not be used to:

- provide medical advice, diagnosis, treatment, or patient-specific triage;
- deploy or authorize a model in a live clinical workflow;
- replace clinical, legal, privacy, security, or regulatory review;
- rank clinicians, patients, facilities, or demographic groups;
- train on, upload, or retain protected health information;
- claim broad clinical competence from the included workflow scope;
- publish model rankings before expert validation and calibration are complete.

## 4. Initial scope

| Item | Alpha decision |
|---|---|
| Sector | Healthcare |
| Workflow | Outpatient/clinic-facing informational assistance |
| Data | Synthetic only; no PHI/PII |
| Languages | English (`en`) and Simplified Chinese (`zh-CN`) |
| Evaluation unit | Bilingual case family with one independently reviewed variant per language |
| Categories | Clinical reasoning, triage, medication safety, patient communication, clinical knowledge, adversarial/safety |
| Scoring | Absolute 0–4 rubric plus critical-error gating; pairwise ranking is optional and secondary |
| Use stage | Research/evaluation only; no clinical use |

Out of alpha scope: multimodal inputs, EHR integration, autonomous actions, tool execution, longitudinal care, model training, and real patient records.

## 5. Decisions required before case validation

These items are deliberately unresolved and block promotion beyond `draft`:

1. **Jurisdiction:** select the clinical-policy jurisdiction and local-policy boundary.
2. **Target users:** choose whether prompts emulate staff-facing, patient-facing, or both workflows, and tag them distinctly.
3. **Population:** specify adult-only or approved pediatric/pregnancy subscopes with qualified reviewers.
4. **Chinese locale:** confirm whether `zh-CN` cases target mainland terminology, US Chinese-speaking clinic communication, or another context.
5. **Authoritative sources:** approve source hierarchy, currency window, and update cadence.
6. **Reviewer qualifications:** approve scope matching and conflict-disclosure rules.
7. **Release thresholds:** approve agreement, critical-error sensitivity, sample-size, and uncertainty requirements.

The benchmark lead records decisions. The clinical safety lead approves items 1, 3, 5, 6, and 7. The language lead approves item 4.

## 6. Bilingual design rule

A case family represents one clinical construct. Its English and Chinese variants must preserve the same facts, task, risk level, applicable dimensions, and critical-error policy. Translation need not be literal, but localization must not change difficulty or expected clinical behavior. Each language variant receives independent language and clinical review. Case families remain within one development or Gold partition to prevent leakage.

## 7. Data and privacy rules

- Use synthetic or fully de-identified content approved by the privacy owner; alpha defaults to synthetic only.
- Do not include names, dates of birth, addresses, record numbers, contact details, or free text copied from clinical records.
- Credentials stay in environment variables and never enter cases, logs, SQLite, or version manifests.
- Raw provider outputs require an approved retention period and access policy before real API execution.
- Any suspected sensitive content is quarantined and excluded from runs pending review.

## 8. Roles and decision rights

| Role | Accountability |
|---|---|
| Benchmark lead | Scope, versions, release manifest, change control |
| Clinical safety lead | Clinical scope, safety taxonomy, reviewer eligibility, final safety decisions |
| Case author | Draft and revise cases; cannot independently approve own case |
| Independent clinical reviewer | Validate clinical facts, reference behavior, requirements, errors, and sources |
| Language reviewer | Validate meaning, terminology, accessibility, and cross-language equivalence |
| Adjudicator | Resolve documented disagreements; cannot erase raw reviews |
| Privacy/security owner | Data rules, provider review, retention, secrets, incident response |
| Release approver | Verifies all gates and signs the release record |

One person may hold multiple roles in an early project, but author and independent approver must remain distinct for released cases.

## 9. Change control

Changes to a case prompt, reference answer, critical requirement, critical error, language meaning, or source interpretation require a new case version and renewed affected reviews. Taxonomy, weights, gates, intended use, or incompatible schema changes require a major benchmark version. Completed run records are immutable.

## 10. Alpha and release gates

### Alpha entry

- charter decisions are recorded;
- 30–50 case families are drafted across all six categories;
- both language variants pass development validation;
- no real patient data is present;
- review assignments are documented.

### Clinician-validated promotion

- case has authoritative sources and effective date;
- independent qualified reviewer approves clinical content;
- language reviewer approves each localized variant;
- critical requirements are observable and critical errors are pre-specified;
- all required changes are resolved and recorded.

### Gold/release promotion

- dual clinical review plus adjudication is complete;
- family is assigned wholly to one partition;
- judge calibration thresholds are met on hidden labels;
- no unresolved severity-3 dispute remains;
- privacy/security and release checklists are signed;
- known limitations and uncertainty are published with any result.

## 11. Approval record

| Role | Name or pseudonymous ID | Decision | Date |
|---|---|---|---|
| Benchmark lead | TBD | Pending | TBD |
| Clinical safety lead | TBD | Pending | TBD |
| Language lead | TBD | Pending | TBD |
| Privacy/security owner | TBD | Pending | TBD |

Until this table is approved, the charter and all cases remain draft/unvalidated.
