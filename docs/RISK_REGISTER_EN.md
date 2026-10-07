# Healthcare/Clinics Benchmark Risk Register v0.1 — English

Status: **active draft**  
Review cadence: at each dataset or rubric release, after any safety incident, and at least quarterly during active use.

Scale: likelihood and impact are `Low`, `Medium`, or `High`. Residual risk is reassessed only after evidence shows the controls work. Owners are roles until named people are assigned.

| ID | Risk | Likelihood | Impact | Preventive controls | Detection and response | Owner | Residual target | Status |
|---|---|---|---|---|---|---|---|---|
| R-001 | Clinically wrong reference answer or critical-error label | Medium | High | Authoritative sources; independent qualified review; versioned case review | Adjudication; quarantine affected family; invalidate impacted runs | Clinical safety lead | Low | Open |
| R-002 | Under-triage or unsafe medication behavior is missed by automated judges | Medium | High | Case-specific critical errors; two diverse judges; human Gold labels | Measure critical-error sensitivity; mandatory review on disagreement; red-team sampling | Clinical safety lead | Low | Open |
| R-003 | English and Chinese variants are not equivalent | High | High | Shared family policy; independent language review; matched facts and gates | Pair-consistency lint; bilingual adjudication; exclude mismatched pair | Language lead | Low | Open |
| R-004 | Chinese wording is linguistically correct but inappropriate for the selected care context | Medium | High | Decide locale and intended user; use locale-qualified reviewers | Locale audit; user comprehension study before external claim | Language lead | Low | Open |
| R-005 | Protected or identifiable health information enters cases, prompts, or logs | Low | High | Synthetic-only alpha; author checklist; provider and retention policy | Automated/manual scan; quarantine; incident process; deletion under policy | Privacy/security owner | Low | Open |
| R-006 | Judge favors its own model family, verbosity, style, or refusals | High | Medium | Blind identities; diverse judges; fixed prompt; balanced response styles | Gold calibration; self-preference, verbosity, and refusal-bias studies | Evaluation lead | Medium | Open |
| R-007 | Provider/model drift makes scores irreproducible | High | Medium | Pin snapshots where possible; store returned versions, dates, prompts, parameters | Repeat sentinel set; compare drift; label limited reproducibility | Evaluation lead | Medium | Open |
| R-008 | Dataset leakage or near-duplicates inflate performance | Medium | High | Family-level partitions; hidden Gold Set; access controls | Duplicate/semantic-similarity audit; regenerate contaminated items | Benchmark lead | Low | Open |
| R-009 | Small or imbalanced sample produces misleading ranking | High | Medium | Category/language quotas; minimum counts; preregister primary metrics | Bootstrap intervals; subgroup reporting; suppress unstable rank claims | Methodology owner | Medium | Open |
| R-010 | Average score hides a severe safety failure | Medium | High | Severity-3 hard fail; separate critical-error reporting; category macro scores | Release gate checks; block publication on unresolved severe failures | Clinical safety lead | Low | Controlled in scaffold |
| R-011 | Sources or guidelines become outdated | Medium | High | Source effective date; update owner; jurisdiction metadata | Scheduled currency review; withdraw/quarantine stale families | Clinical safety lead | Low | Open |
| R-012 | Authors tune cases or judge prompts against hidden Gold labels | Medium | High | Role separation; restricted Gold access; immutable review records | Access audit; holdout refresh; invalidate compromised set | Benchmark lead | Low | Open |
| R-013 | Reviewers lack the required specialty, jurisdiction, or language competence | Medium | High | Qualification-scope records; assignment rules; conflicts disclosed | Audit assignments; specialist escalation; re-review | Clinical safety lead | Low | Open |
| R-014 | API credentials, proprietary prompts, or raw outputs leak | Low | High | Environment-only secrets; no credentials in config/SQLite; least privilege | Secret scanning; revoke/rotate; incident response | Privacy/security owner | Low | Open |
| R-015 | Users interpret benchmark scores as authorization for clinical deployment | Medium | High | Prominent use restrictions; unvalidated labels; no deployment claim | Review external communications; correct or retract misleading claims | Release approver | Low | Open |
| R-016 | Schema-valid cases remain ambiguous or unscorable | High | Medium | Observable requirements; pilot review; authoring guide | Judge disagreement analysis; ambiguity log; revise or exclude | Benchmark lead | Medium | Open |
| R-017 | Trigger-term heuristics are mistaken for semantic safety evaluation | Medium | High | Label trigger terms as mock aids; require semantic judge/human review | Audit implementation and reports; prohibit production claims from mock scores | Evaluation lead | Low | Controlled in docs |
| R-018 | Changes break score comparability without clear versioning | Medium | Medium | Semantic versioning; content hashes; immutable manifests | Release diff and migration review; prohibit cross-major comparison | Benchmark lead | Low | Partly controlled |

## Immediate risk actions

1. Name the benchmark, clinical safety, language, privacy/security, and methodology owners.
2. Resolve intended-user, population, and global Simplified-Chinese style decisions; select jurisdiction packs separately.
3. Approve a source hierarchy and reviewer-qualification matrix.
4. Define an incident/quarantine process before any real provider call.
5. Set Alpha quotas and preregister the primary safety and quality metrics.
6. Reassess R-001 through R-006 after the first ten bilingual families are reviewed.

## Risk acceptance rule

Only the accountable owner may propose acceptance. High-impact residual risk requires written approval from the clinical safety lead and release approver. A risk marked `Open` cannot be treated as controlled merely because no incident has yet occurred.
