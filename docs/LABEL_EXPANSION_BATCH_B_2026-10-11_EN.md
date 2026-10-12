# Global Core Alpha expansion, batch B — 2026-10-11

This batch adds 12 original synthetic bilingual families (`-004` and `-005` in each category), moving the configured Alpha from 18 families / 36 prompts to **30 families / 60 prompts**, five families per category. Each EN/ZH-HANS pair is one clinical scenario, not two independent cases. The original 36 rows remain unchanged. All references, requirements, critical errors, and family-level analytic labels are **AI-authored provisional drafts**, not clinical ground truth. No patient-level data or commercial sample case was imported.

| Category | New families | Distinct construct | Main public evidence |
|---|---|---|---|
| Triage | TRIAGE-004/005 | Timely non-emergency workup for persistent cough; postpartum emergency warning signs | [WHO tuberculosis](https://www.who.int/news-room/fact-sheets/detail/tuberculosis), [WHO pre-eclampsia](https://www.who.int/news-room/fact-sheets/detail/pre-eclampsia), [ACOG postpartum warning signs](https://www.acog.org/womens-health/experts-and-stories/the-latest/3-conditions-to-watch-for-after-childbirth) |
| Medication safety | MEDSAFE-004/005 | Duplicate active ingredient in incompletely labelled products; possible unknown child ingestion | [WHO nonproprietary names](https://www.who.int/publications/i/item/who-emp-rht-tsn-2018-02), [MedlinePlus poisoning first aid](https://medlineplus.gov/ency/article/007579.htm) |
| Patient communication | COMMS-004/005 | Negative result with worsening symptoms; conflicting discharge dates and teach-back | [MedlinePlus lab interpretation](https://medlineplus.gov/lab-tests/how-to-understand-your-lab-results/), [AHRQ teach-back](https://www.ahrq.gov/teamstepps-program/curriculum/communication/tools/teachback.html) |
| Clinical reasoning | REASON-004/005 | Reliability of a single home measurement; positive predictive value in an explicitly hypothetical cohort | [WHO hypertension](https://www.who.int/news-room/fact-sheets/detail/hypertension), [NIH health risks](https://newsinhealth.nih.gov/2016/10/understanding-health-risks) |
| Clinical knowledge | KNOW-004/005 | Relative versus absolute risk; conditional antibiotic appropriateness | [NIH health risks](https://newsinhealth.nih.gov/2016/10/understanding-health-risks), [WHO antibiotic guidance](https://www.who.int/europe/news/item/05-02-2019-keep-antibiotics-working-limit-their-use-this-flu-season) |
| Adversarial safety | ADV-004/005 | Claimed authority suppressing transient-neurologic escalation; unauthorized third-party record publication | [CDC stroke signs](https://www.cdc.gov/stroke/signs-symptoms/index.html), [WHO health-AI privacy principles](https://www.who.int/news/item/28-06-2021-who-issues-first-global-report-on-ai-in-health-and-six-guiding-principles-for-its-design-and-use) |

The source registry in [`public_sources.json`](../data/evidence/public_sources.json) records each source's narrow support and limitations. A source supporting a general safety principle does **not** validate our exact wording, urgency boundary, critical-error severity, or Chinese equivalence. The numerical keys are internal arithmetic checks: `9 / (9 + 99) = 8.33%`; `20/1000 − 10/1000 = 1 percentage point`. Neither is an estimate for a real disease or treatment.

## Open quality gates

- Clinical reviewers must inspect every new answer key and error trigger, especially severity-3 postpartum, poisoning, and transient-neurologic rules. Global Core must not assume a universal emergency number, poison center, screening interval, medicine dose, or legal regime.
- A qualified bilingual healthcare reviewer must compare each Chinese prompt and label against its English pair. The machine-translation flag is intentionally retained even where wording was edited in drafting.
- Methodology review must test whether numeric cases genuinely discriminate reasoning rather than memorized phrases, whether generic safety language can earn too much credit, and whether answer variants are fairly judged.
- The 30-family milestone is **coverage scaffolding**, not enough for a reliable category ranking or “expert clinician” claim. These remain single-turn patient-facing cases; multi-turn reasoning, multimorbidity, professional workflows, and a hidden clinician-reviewed Gold Set are still absent.

See [the living human-review queue](CLINICAL_REVIEW_HANDOFF_EN.md) for assignable decisions, and [the coverage roadmap](COVERAGE_ROADMAP_EN.md) for the next track.
