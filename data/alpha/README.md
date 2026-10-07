# Alpha authoring workspace

Place the working bilingual Alpha dataset at `data/alpha/healthcare_cases.jsonl` when authoring begins. Do not copy the six legacy examples into the Alpha unchanged: they are English-only infrastructure fixtures with no clinical validation or sources.

Recommended workflow:

1. Resolve the open decisions in the bilingual benchmark charter.
2. Duplicate `data/templates/case.template.json` into one JSONL row per language variant.
3. Use one `case_family_id` for the matching `en` and `zh-Hans` rows.
4. Global Core rows use `benchmark_layer=global_core`, `jurisdiction=global_core`, and jurisdiction-neutral wording.
5. Keep new cases at `status=draft` and `metadata.clinician_validated=false` until review is complete.
6. Store append-only review records separately using `data/templates/case-review.template.json`.
7. Run development validation during authoring:

   ```bash
   python -m benchmark.cli --config config/benchmark.json validate-data \
     --cases data/alpha/healthcare_cases.jsonl
   ```

8. Run `--release-ready` only after all review and governance gates are satisfied.

Do not commit provider credentials, real patient data, or hidden Gold labels to this directory.
