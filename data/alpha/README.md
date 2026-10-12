# Global Core Alpha authoring workspace

The configured draft dataset is [`global_core_cases.jsonl`](global_core_cases.jsonl): **30 bilingual families / 60 prompts** as of 2026-10-11, five families per category. The original 36 rows were not revised during this batch. [`family_labels.json`](family_labels.json) classifies every family by competency, reasoning operation, anticipated failure mode, and complexity factor without changing those case hashes or the scoring rubric. These are analytic labels, not human-validated ground truth.

All rows are synthetic, patient-facing, `status=draft`, and `clinician_validated=false`. The Chinese variants remain `machine_translation_unreviewed`. No real patient data, paid catalog samples, or copied external benchmark questions belong in this file. The earlier `-003` families are described in [batch A](../../docs/LABEL_EXPANSION_2026-10-11_EN.md), and the `-004/-005` families in [batch B](../../docs/LABEL_EXPANSION_BATCH_B_2026-10-11_EN.md); public-source options and reuse cautions are in [the source inventory](../../docs/PUBLIC_DATASET_SOURCES_EN.md).

A [separate multi-turn pilot](../multiturn/README.md) now contains four additional draft families; its cases and scores are **not** included in the 30-family/60-prompt single-turn Alpha.

Authoring steps:

1. Follow the [case authoring guide](../../docs/CASE_AUTHORING_GUIDE_EN.md), including source provenance and meaning-preserving bilingual pairing.
2. Add one JSONL row per language, sharing a stable `case_family_id`. Use `benchmark_layer=global_core`, `jurisdiction=global_core`, and jurisdiction-neutral wording.
3. Keep new cases at draft status. Meaning-changing edits to an existing case require a version bump and renewed review.
4. Add a family-level entry to `family_labels.json` and source mapping to [`public_sources.json`](../evidence/public_sources.json). Treat both as provisional until expert review.
5. Validate and inspect the review queue:

   ```bash
   python3 -m benchmark.cli --config config/benchmark.json validate-data
   python3 -m benchmark.cli --config config/benchmark.json dataset-status
   python3 -m unittest discover -s tests -q
   ```

Do not commit provider credentials, real patient data, or hidden Gold labels. This Alpha must not be used to claim clinical competence, model safety certification, or a public ranking.
